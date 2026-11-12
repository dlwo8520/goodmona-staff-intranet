import os

bind = '0.0.0.0:' + os.getenv('PORT', '8000')
workers = 1
worker_class = 'gthread'
threads = 4
timeout = 60
graceful_timeout = 30
# POST search bodies and URL query strings must never enter an access log.
accesslog = None
errorlog = '-'
capture_output = False
