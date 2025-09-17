#!/bin/bash
# 启动定时任务调度器

echo "📦 安装依赖包..."
pip install -r requirements.txt

echo "🚀 启动定时任务调度器..."
python scheduler.py
