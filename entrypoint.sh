#!/bin/bash

# 使用挂载卷中的JMeter路径
JMETER_PATH="/opt/apache-jmeter-5.6.3/bin/jmeter"
SLA_JAR_PATH="/opt/apache-jmeter-5.6.3/lib/ext/jmeter-sla-report-1.0.5-jar-with-dependencies.jar"

# 启动应用
python JTP/run_platform.py
