import os
import threading

from app import app, sync_loop, sync_once


bind = f"{os.getenv('APP_HOST', '0.0.0.0')}:{os.getenv('APP_PORT', '8000')}"
workers = int(os.getenv("GUNICORN_WORKERS", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = 60


def post_worker_init(worker):
    sync_once()
    threading.Thread(target=sync_loop, daemon=True).start()
