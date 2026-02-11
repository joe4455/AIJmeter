# 使用最小的Alpine基础镜像
FROM python:3.10-alpine

# 添加维护者信息
LABEL maintainer="JTP Test Platform"

# 安装必要的系统依赖
RUN apk add --no-cache \
    openjdk11-jre-headless \
    bash \
    curl \
    tzdata \
    && rm -rf /var/cache/apk/* \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone

# 设置环境变量
ENV JMETER_HOME=/opt/apache-jmeter-5.6.3
ENV PATH=$JMETER_HOME/bin:$PATH
ENV PYTHONPATH=/app

# 创建工作目录
WORKDIR /app

# 复制所有文件到容器中
COPY . /app/

# 将JMeter目录移动到正确位置
RUN mv /app/apache-jmeter-5.6.3 /opt/apache-jmeter-5.6.3/ || true

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露端口
EXPOSE 5000

# 设置启动脚本
ENTRYPOINT ["bash", "/app/entrypoint.sh"]
