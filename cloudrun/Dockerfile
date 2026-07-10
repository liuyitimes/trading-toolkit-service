FROM python:3.11-slim

WORKDIR /app

# 安装依赖（使用清华镜像加速，利用 Docker 层缓存）
COPY cloudrun/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && rm -rf /root/.cache/pip

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# 复制应用代码
COPY cloudrun/ .

# 设置权限
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

# 生产模式: gunicorn（2 worker + 超时120s）
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "--timeout", "120", "--access-logfile", "-", "app:app"]
