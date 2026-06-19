"""
gunicorn.conf.py — Production configuration for 30 concurrent users.

Architecture:
  - 4 workers × 4 threads = 16 concurrent request slots at any moment
  - Each Groq/Supabase call is I/O-bound, so thread utilisation is high
  - Worker recycling (max_requests) prevents slow memory leaks over time

Run locally:
    gunicorn -c gunicorn.conf.py app:app

On Render / Railway:
    Update startCommand in render.yaml → gunicorn -c gunicorn.conf.py app:app
"""

import multiprocessing

# ── Workers & Threads ────────────────────────────────────────────────────────
# Rule of thumb for I/O-bound apps: workers = (2 × CPU cores) + 1
# Threads per worker multiplies effective concurrency without extra RAM.
# 4 workers × 4 threads = 16 concurrent slots → comfortably handles 30 users
# whose requests are mostly waiting on Groq / Supabase (I/O).
workers     = 4
threads     = 4
worker_class = "gthread"   # multi-threaded sync worker — ideal for I/O-bound Flask

# ── Timeouts ─────────────────────────────────────────────────────────────────
# LLM calls can take 10-25 s; give plenty of headroom.
timeout      = 120          # seconds before a worker is killed
keepalive    = 5            # keep-alive connections (seconds) between requests

# ── Worker recycling (memory leak prevention) ─────────────────────────────────
max_requests          = 500     # restart worker after this many requests
max_requests_jitter   = 50      # stagger restarts so not all workers cycle at once

# ── Binding ──────────────────────────────────────────────────────────────────
bind = "0.0.0.0:5000"

# ── Logging ──────────────────────────────────────────────────────────────────
accesslog  = "-"   # stdout
errorlog   = "-"   # stdout
loglevel   = "info"

# ── Graceful restart ─────────────────────────────────────────────────────────
graceful_timeout = 30
