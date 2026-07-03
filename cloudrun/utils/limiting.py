import time
import threading
from functools import wraps
from flask import request
from utils.response import api_error, ErrorCode

class RateLimiter:
    """简单的内存限流器"""
    def __init__(self):
        self._counters = {}
        self._lock = threading.Lock()
    
    def is_allowed(self, key, max_requests, window_seconds=60):
        """检查是否允许请求"""
        now = time.time()
        with self._lock:
            if key not in self._counters:
                self._counters[key] = []
            # 清理过期的请求记录
            self._counters[key] = [t for t in self._counters[key] if now - t < window_seconds]
            if len(self._counters[key]) >= max_requests:
                return False
            self._counters[key].append(now)
            return True

rate_limiter = RateLimiter()

def limit(max_requests, window=60):
    """限流装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            key = f"{request.remote_addr}:{f.__name__}"
            if not rate_limiter.is_allowed(key, max_requests, window):
                return api_error(*ErrorCode.RATE_LIMITED)
            return f(*args, **kwargs)
        return decorated_function
    return decorator