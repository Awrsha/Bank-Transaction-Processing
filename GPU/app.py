from flask import Flask, jsonify, request, render_template
import sqlite3
import queue
import threading
import time
import logging
from collections import deque
import concurrent.futures
import numpy as np
import pycuda.driver as cuda
import pycuda.autoinit
from pycuda.compiler import SourceModule

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

MAX_QUEUE_SIZE = 100000  # اگه گارت گرافیک خوبه اینو بیشتر کن
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

cuda_code = """
__global__ void process_transactions(int *card_numbers, int *amounts, int *balances, int *results, int n)
{
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n)
    {
        int new_balance = balances[idx] + amounts[idx];
        if (new_balance >= 0)
        {
            balances[idx] = new_balance;
            results[idx] = 1;
        }
        else
        {
            results[idx] = 0;
        }
    }
}
"""

mod = SourceModule(cuda_code)
process_transactions_gpu = mod.get_function("process_transactions")

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

def process_transactions_batch():
    batch_size = 10000  # اگه بالایی رو زیاد کردی اینم به صورت نسبی باهاش زیاد کن
    while True:
        batch = []
        start_time = time.time()
        
        while len(batch) < batch_size and not transaction_queue.empty():
            try:
                transaction = transaction_queue.get_nowait()
                batch.append(transaction)
            except queue.Empty:
                break
        
        if not batch:
            time.sleep(0.1)
            continue
        
        card_numbers = np.array([int(t[0].replace(' ', '')) for t, _, _ in batch], dtype=np.int32)
        amounts = np.array([t[1] for t, _, _ in batch], dtype=np.int32)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(card_numbers))
        cursor.execute(f"SELECT card_number, balance FROM users WHERE card_number IN ({placeholders})", 
                       [str(cn) for cn in card_numbers])
        balances_dict = {row['card_number']: row['balance'] for row in cursor.fetchall()}
        conn.close()
        
        balances = np.array([balances_dict.get(str(cn), 0) for cn in card_numbers], dtype=np.int32)
        results = np.zeros_like(card_numbers)
        
        process_transactions_gpu(
            cuda.In(card_numbers), cuda.In(amounts), cuda.InOut(balances), cuda.Out(results),
            np.int32(len(batch)),
            block=(256, 1, 1), grid=((len(batch) + 255) // 256, 1)
        )
        
        conn = get_db_connection()
        cursor = conn.cursor()
        for i, (card_number, amount, start_time) in enumerate(batch):
            if results[i] == 1:
                cursor.execute("UPDATE users SET balance = ? WHERE card_number = ?", 
                               (int(balances[i]), str(card_numbers[i])))
                cursor.execute("INSERT INTO transactions (card_number, amount, success) VALUES (?, ?, 1)", 
                               (str(card_numbers[i]), amount))
                with lock:
                    if amount > 0:
                        transaction_counts['deposits'] += 1
                    else:
                        transaction_counts['withdrawals'] += 1
            else:
                cursor.execute("INSERT INTO transactions (card_number, amount, success) VALUES (?, ?, 0)", 
                               (str(card_numbers[i]), amount))
                with lock:
                    transaction_counts['insufficient_funds'] += 1
            
            with lock:
                transaction_times.append(time.time() - start_time)
        
        conn.commit()
        conn.close()

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

transaction_thread = threading.Thread(target=process_transactions_batch)
transaction_thread.daemon = True
transaction_thread.start()

balance_thread = threading.Thread(target=update_average_balance)
balance_thread.daemon = True
balance_thread.start()

if __name__ == '__main__':
    app.run(debug=False)