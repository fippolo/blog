import os

from app import start_sync


bind = f"{os.getenv('APP_HOST', '0.0.0.0')}:{os.getenv('APP_PORT', '8000')}"
workers = int(os.getenv("GUNICORN_WORKERS", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = 60


def post_worker_init(worker):
    start_sync()
