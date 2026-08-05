FROM python:3.11-slim

WORKDIR /app

# 安装依赖
RUN pip install prometheus-client psutil docker

# 复制Exporter脚本
COPY app_exporter.py /app/

# 暴露端口
EXPOSE 9101

# 启动Exporter
CMD ["python", "/app/app_exporter.py"]