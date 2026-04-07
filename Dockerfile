FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建数据与日志目录
RUN mkdir -p /app/data /app/logs

# 运行 bot
CMD ["python", "main.py"]
