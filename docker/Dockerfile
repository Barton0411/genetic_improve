# Dockerfile for Genetic Improve Application
FROM python:3.9-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    xfce4 \
    xfce4-terminal \
    wget \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# 安装noVNC
RUN wget https://github.com/novnc/noVNC/archive/refs/tags/v1.3.0.tar.gz \
    && tar -xzf v1.3.0.tar.gz \
    && mv noVNC-1.3.0 /opt/noVNC \
    && rm v1.3.0.tar.gz

# 安装websockify
RUN wget https://github.com/novnc/websockify/archive/refs/tags/v0.10.0.tar.gz \
    && tar -xzf v0.10.0.tar.gz \
    && mv websockify-0.10.0 /opt/websockify \
    && rm v0.10.0.tar.gz

# 设置工作目录
WORKDIR /app

# 复制应用文件
COPY . /app/
COPY requirements.txt /app/

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制supervisor配置
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 暴露端口
EXPOSE 6080

# 启动supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]