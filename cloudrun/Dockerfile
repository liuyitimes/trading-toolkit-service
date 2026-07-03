FROM python:3.11-slim

WORKDIR /app

# 安装依赖（使用清华镜像加速）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用代码
COPY . .

EXPOSE 8080

# 开发模式: python app.py
# 生产模式: gunicorn
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "--timeout", "120", "app:app"]
