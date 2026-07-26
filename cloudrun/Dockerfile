FROM python:3.11-slim

WORKDIR /app

# 安装依赖（使用清华镜像加速，利用 Docker 层缓存）
COPY cloudrun/requirements.txt .
COPY alembic.ini .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && rm -rf /root/.cache/pip

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# 复制应用代码
COPY cloudrun/ cloudrun/

# 设置权限
RUN chown -R appuser:appuser /app

USER appuser

WORKDIR /app/cloudrun

EXPOSE 8080

# 生产模式: gunicorn（2 worker + 超时120s）
CMD ["sh", "-c", "case \"$DATABASE_URL\" in postgresql://*|postgresql+psycopg2://*) ;; *) echo 'DATABASE_URL must be a PostgreSQL URL in production' >&2; exit 1 ;; esac; alembic -c /app/alembic.ini upgrade head && exec gunicorn -w 2 -b 0.0.0.0:8080 --timeout 120 --access-logfile - app:app"]
