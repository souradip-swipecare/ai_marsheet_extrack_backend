"""
Production deployment configuration for concurrent request handling
Optimized for 2-core, 4GB RAM system with async FastAPI
"""

# Gunicorn configuration
# https://docs.gunicorn.org/en/stable/settings.html

import multiprocessing
import os

# Server Socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker Processes - Optimized for concurrent async requests
# For async workers (UvicornWorker), recommended: 2-4x CPU cores
workers = int(os.getenv("WORKERS", 4))  # 4 async workers for 2 cores
worker_class = "uvicorn.workers.UvicornWorker"  # Async ASGI worker
worker_connections = 1000  # Max concurrent connections per worker
max_requests = 1000  # Restart workers after 1000 requests (prevent memory leaks)
max_requests_jitter = 50  # Add randomness to prevent all workers restarting at once
timeout = 120  # Workers timeout after 2 minutes
graceful_timeout = 30  # Graceful shutdown timeout
keepalive = 5  # Keep-alive connections

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"  # Log to stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process Naming
proc_name = "marksheet-extraction-api"

# Server Mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (for production with certificates)
# keyfile = None
# certfile = None

def post_fork(server, worker):
    """Called after worker fork"""
    server.log.info(f"Worker spawned (pid: {worker.pid})")

def pre_fork(server, worker):
    """Called before worker fork"""
    pass

def pre_exec(server):
    """Called before exec"""
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    """Called when server is ready"""
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    """Called when worker receives SIGINT"""
    worker.log.info(f"Worker received INT or QUIT signal (pid: {worker.pid})")

def worker_abort(worker):
    """Called when worker receives SIGABRT"""
    worker.log.info(f"Worker received SIGABRT signal (pid: {worker.pid})")
