from locust import HttpUser, task, between
import random
import subprocess
import webbrowser
import time

class WebsiteUser(HttpUser):
    wait_time = between(0.05, 0.2)

    @task(10)
    def perform_transaction(self):
        card_number = f"6219 8619 {random.randint(0, 9999):04d} 8640"
        amount = random.randint(-5000, 5000)
        self.client.post("/transaction", json={'card_number': card_number, 'amount': amount})

    @task(2)
    def get_metrics(self):
        self.client.get("/metrics")

    @task(1)
    def visit_homepage(self):
        self.client.get("/")

def run_locust():
    subprocess.Popen(["locust", "-f", __file__])

def open_browser():
    url = "http://localhost:8089"
    webbrowser.open(url, new=2)

if __name__ == "__main__":
    run_locust()
    time.sleep(5)
    open_browser()