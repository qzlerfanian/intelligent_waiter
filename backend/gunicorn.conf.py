import multiprocessing
import os

bind = "0.0.0.0:8000"
workers = int(os.getenv("WEB_CONCURRENCY", min(multiprocessing.cpu_count() * 2 + 1, 8)))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = 60
graceful_timeout = 30
keepalive = 5
max_requests = 2000
max_requests_jitter = 200
accesslog = "-"
errorlog = "-"
capture_output = True
