FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装依赖并利用 Docker 层缓存
COPY cloudrun/requirements.txt .
COPY alembic.ini .
RUN pip install --no-cache-dir -r requirements.txt \
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
# 启动前先校验数据库协议，再执行 Alembic 迁移；任一阶段失败即终止启动，
# 避免带错误结构或错误驱动的实例对外提供服务。
# 允许 postgresql:// 与历史别名 postgres://（运行期由 utils.dburl 补齐为
# postgresql+psycopg2://），以及显式声明 psycopg2 的形式。
CMD ["sh", "-c", "case \"$DATABASE_URL\" in postgresql://*|postgres://*|postgresql+psycopg2://*) ;; *) echo 'DATABASE_URL must be a PostgreSQL URL in production' >&2; exit 1 ;; esac; python -c 'import os; from utils.dburl import normalize_database_url; print(\"alembic target:\", normalize_database_url(os.environ[\"DATABASE_URL\"]).split(\"@\")[-1])' && alembic -c /app/alembic.ini upgrade head && exec gunicorn -w 2 -b 0.0.0.0:8080 --timeout 120 --access-logfile - app:app"]
