from flask import Flask, jsonify, request, render_template
import sqlite3
import queue
import threading
import time
import logging
from collections import deque
import concurrent.futures

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

MAX_QUEUE_SIZE = 10000
transaction_queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
average_balance_history = deque(maxlen=100)
transaction_counts = {
    'deposits': 0,
    'withdrawals': 0,
    'insufficient_funds': 0,
    'error': 0,
    'queue_full': 0
}
locust_requests = 0
lock = threading.Lock()
transaction_times = deque(maxlen=1000)
queue_size_history = deque(maxlen=100)

def get_db_connection():
    conn = sqlite3.connect('users.db', timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/metrics', methods=['GET'])
def metrics():
    global locust_requests, queue_size_history
    with lock:
        current_queue_size = transaction_queue.qsize()
        queue_size_history.append(current_queue_size)
        metrics_data = {
            'transaction_counts': dict(transaction_counts),
            'total_requests': locust_requests,
            'average_balance_history': list(average_balance_history),
            'transaction_times': list(transaction_times),
            'queue_size_history': list(queue_size_history),
            'current_queue_size': current_queue_size
        }
    return jsonify(metrics_data)

@app.route('/transaction', methods=['POST'])
def transaction():
    global locust_requests
    data = request.json
    card_number = data.get('card_number')
    amount = data.get('amount')
    
    if card_number is None or amount is None:
        return jsonify({'status': 'error', 'message': 'Invalid input'}), 400

    with lock:
        locust_requests += 1
    
    try:
        transaction_queue.put_nowait((card_number, amount, time.time()))
        return jsonify({'status': 'queued', 'message': 'Transaction queued for processing'}), 202
    except queue.Full:
        with lock:
            transaction_counts['queue_full'] += 1
        return jsonify({'status': 'error', 'message': 'Queue is full, please try again later'}), 503

def process_transactions():
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        while True:
            try:
                card_number, amount, start_time = transaction_queue.get(timeout=1)
                executor.submit(process_single_transaction, card_number, amount, start_time)
            except queue.Empty:
                time.sleep(0.1)
            except Exception as e:
                logging.error(f"Error processing transaction: {str(e)}")

def process_single_transaction(card_number, amount, start_time):
    max_retries = 5
    retry_count = 0

    while retry_count < max_retries:
        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT balance FROM users WHERE card_number = ?", (card_number,))
                user = cursor.fetchone()
                
                if user:
                    new_balance = user['balance'] + amount
                    if new_balance < 0:
                        cursor.execute("INSERT INTO transactions (card_number, amount, success) VALUES (?, ?, 0)", (card_number, amount))
                        with lock:
                            transaction_counts['insufficient_funds'] += 1
                        return
                    
                    cursor.execute("UPDATE users SET balance = ? WHERE card_number = ?", (new_balance, card_number))
                    cursor.execute("INSERT INTO transactions (card_number, amount, success) VALUES (?, ?, 1)", (card_number, amount))
                    
                    with lock:
                        if amount > 0:
                            transaction_counts['deposits'] += 1
                        else:
                            transaction_counts['withdrawals'] += 1
                        transaction_times.append(time.time() - start_time)
                    return
                else:
                    cursor.execute("INSERT INTO transactions (card_number, amount, success) VALUES (?, ?, 0)", (card_number, amount))
                    with lock:
                        transaction_counts['error'] += 1
                    return
        except sqlite3.Error as e:
            logging.error(f"Database error: {str(e)}")
            retry_count += 1
            time.sleep(0.2 * retry_count)
        finally:
            conn.close()

    logging.error(f"Failed to process transaction after {max_retries} attempts: card_number={card_number}, amount={amount}")

def update_average_balance():
    while True:
        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT AVG(balance) as avg_balance FROM users")
                result = cursor.fetchone()
                if result and result['avg_balance'] is not None:
                    with lock:
                        average_balance_history.append(result['avg_balance'])
        except sqlite3.Error as e:
            logging.error(f"Error updating average balance: {str(e)}")
        finally:
            conn.close()
        time.sleep(1)

transaction_thread = threading.Thread(target=process_transactions)
transaction_thread.daemon = True
transaction_thread.start()

balance_thread = threading.Thread(target=update_average_balance)
balance_thread.daemon = True
balance_thread.start()

if __name__ == '__main__':
    app.run(debug=False)