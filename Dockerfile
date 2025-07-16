FROM python:3.9-slim

WORKDIR /app

# 完全使用腾讯云镜像源
RUN echo "deb https://mirrors.cloud.tencent.com/debian/ bookworm main" > /etc/apt/sources.list && \
    echo "deb https://mirrors.cloud.tencent.com/debian/ bookworm-updates main" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.cloud.tencent.com/debian-security bookworm-security main" >> /etc/apt/sources.list

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 升级pip并使用清华大学PyPI镜像源安装Python依赖
RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn && \
    pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn

# 复制应用代码和静态文件
COPY app.py .
COPY static/ ./static/

# 创建上传目录
RUN mkdir -p /app/uploads

# 设置环境变量
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# 暴露端口
EXPOSE 5001

# 启动命令
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "4", "app:app"] 