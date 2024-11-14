from python import Python
from threading import Thread, Lock
from collections.thread import ThreadSafeQueue
from memory.unsafe import Pointer
from sqlite import SQLite3
from time import sleep
from atomic import AtomicInt

struct TransactionMetrics:
    var deposits: AtomicInt
    var withdrawals: AtomicInt
    var insufficient_funds: AtomicInt
    var errors: AtomicInt
    var queue_full: AtomicInt
    
    fn __init__(inout self):
        self.deposits = AtomicInt(0)
        self.withdrawals = AtomicInt(0)
        self.insufficient_funds = AtomicInt(0)
        self.errors = AtomicInt(0)
        self.queue_full = AtomicInt(0)

struct Transaction:
    var card_number: String
    var amount: Int
    var timestamp: Float64
    
    fn __init__(inout self, card_number: String, amount: Int, timestamp: Float64):
        self.card_number = card_number
        self.amount = amount
        self.timestamp = timestamp

@value
struct CircularBuffer[T: AnyType, size: Int]:
    var data: StaticTuple[T, size]
    var head: Int
    var count: Int
    
    fn __init__(inout self):
        self.data = StaticTuple[T, size]()
        self.head = 0
        self.count = 0
    
    fn push(inout self, value: T):
        let idx = (self.head + self.count) % size
        self.data[idx] = value
        if self.count < size:
            self.count += 1
        else:
            self.head = (self.head + 1) % size

struct TransactionProcessor:
    var queue: ThreadSafeQueue[Transaction]
    var metrics: TransactionMetrics
    var avg_balance_history: CircularBuffer[Float64, 100]
    var transaction_times: CircularBuffer[Float64, 1000]
    var db_path: String
    var worker_count: Int
    
    fn __init__(inout self, db_path: String, max_queue_size: Int, worker_count: Int):
        self.queue = ThreadSafeQueue[Transaction](max_queue_size)
        self.metrics = TransactionMetrics()
        self.avg_balance_history = CircularBuffer[Float64, 100]()
        self.transaction_times = CircularBuffer[Float64, 1000]()
        self.db_path = db_path
        self.worker_count = worker_count
    
    fn process_transaction(self, transaction: Transaction) raises:
        let db = SQLite3(self.db_path)
        try:
            db.execute("BEGIN TRANSACTION")
            
            # Use prepared statements for better performance
            let balance_stmt = db.prepare("SELECT balance FROM users WHERE card_number = ? FOR UPDATE")
            balance_stmt.bind_text(1, transaction.card_number)
            
            if let row = balance_stmt.step():
                var balance = row.column_int(0)
                let new_balance = balance + transaction.amount
                
                if new_balance >= 0:
                    let update_stmt = db.prepare("UPDATE users SET balance = ? WHERE card_number = ?")
                    update_stmt.bind_int(1, new_balance)
                    update_stmt.bind_text(2, transaction.card_number)
                    update_stmt.step()
                    
                    if transaction.amount > 0:
                        self.metrics.deposits.increment()
                    else:
                        self.metrics.withdrawals.increment()
                    
                    let duration = now() - transaction.timestamp
                    self.transaction_times.push(duration)
                else:
                    self.metrics.insufficient_funds.increment()
            else:
                self.metrics.errors.increment()
            
            db.execute("COMMIT")
        except:
            db.execute("ROLLBACK")
            self.metrics.errors.increment()
        finally:
            db.close()
    
    fn worker_thread(self):
        while True:
            try:
                if let transaction = self.queue.try_pop():
                    self.process_transaction(transaction)
                else:
                    sleep(0.001) # Short sleep to prevent busy waiting
            except:
                continue
    
    fn start(self):
        # Start worker threads
        for _ in range(self.worker_count):
            Thread.start(fn(): self.worker_thread())
        
        # Start balance history update thread
        Thread.start(fn(): self.update_average_balance())
    
    fn update_average_balance(self):
        while True:
            try:
                let db = SQLite3(self.db_path)
                let row = db.execute("SELECT AVG(balance) FROM users").fetch_one()
                if row:
                    self.avg_balance_history.push(row[0])
                db.close()
            except:
                continue
            sleep(1.0)

# Flask integration using Python interop
fn create_app():
    let py = Python.import_module("flask")
    let app = py.Flask(__name__)
    
    let processor = TransactionProcessor("users.db", 10000, 20)
    processor.start()
    
    @app.route("/transaction", methods=["POST"])
    fn handle_transaction():
        let request = py.request
        let data = request.get_json()
        
        let card_number = data["card_number"]
        let amount = data["amount"]
        
        let transaction = Transaction(card_number, amount, now())
        
        try:
            processor.queue.try_push(transaction)
            return {"status": "queued", "message": "Transaction queued for processing"}, 202
        except:
            processor.metrics.queue_full.increment()
            return {"status": "error", "message": "Queue is full"}, 503
    
    return app

fn main() raises:
    let app = create_app()
    app.run(host="0.0.0.0", port=5000, threaded=True)