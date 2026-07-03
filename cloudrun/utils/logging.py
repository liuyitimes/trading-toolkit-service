import logging
import json
from datetime import datetime

class JsonFormatter(logging.Formatter):
    """JSON格式的日志格式化器"""
    def format(self, record):
        log_data = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'line': record.lineno,
        }
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)
        return json.dumps(log_data, ensure_ascii=False)

def setup_logging(app=None):
    """配置结构化日志"""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    
    if app:
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
    
    # 通用 logger
    logger = logging.getLogger('trading_toolkit')
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger