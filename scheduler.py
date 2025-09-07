#!/usr/bin/env python3
"""
定时任务调度器
每天北京时间上午10点和下午2点执行论文收集和翻译任务
"""

import schedule
import time
import subprocess
import logging
import os
import sys
from datetime import datetime
import pytz

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# 设置北京时区
beijing_tz = pytz.timezone('Asia/Shanghai')

def run_command(command, description):
    """执行命令并记录结果"""
    try:
        logger.info(f"开始执行: {description}")
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True,
            timeout=3600  # 1小时超时
        )
        
        if result.returncode == 0:
            logger.info(f"✅ {description} 执行成功")
            if result.stdout:
                logger.info(f"输出: {result.stdout.strip()}")
        else:
            logger.error(f"❌ {description} 执行失败")
            logger.error(f"错误信息: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"❌ {description} 执行超时")
        return False
    except Exception as e:
        logger.error(f"❌ {description} 执行异常: {str(e)}")
        return False
    
    return True

def daily_task():
    """每日定时任务"""
    beijing_time = datetime.now(beijing_tz)
    logger.info(f"🚀 开始执行每日任务 - 北京时间: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 确保在正确的工作目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    logger.info(f"工作目录: {script_dir}")
    
    # 任务执行步骤
    steps = [
        ("python daily_paper_collector.py", "收集每日论文"),
        ("python translate_batch.py", "批量翻译论文"),
        ("git add -A", "添加所有变更到暂存区"),
        ("git commit -m 'Auto update: daily papers and translations'", "提交变更"),
        ("git push", "推送到远程仓库")
    ]
    
    success_count = 0
    for command, description in steps:
        if run_command(command, description):
            success_count += 1
        else:
            logger.error(f"任务失败，停止后续执行")
            break
    
    logger.info(f"📊 任务完成统计: {success_count}/{len(steps)} 步骤成功执行")
    logger.info("=" * 50)

def check_git_status():
    """检查Git状态"""
    try:
        result = subprocess.run("git status --porcelain", shell=True, capture_output=True, text=True)
        if result.stdout.strip():
            logger.info("检测到未提交的变更")
        else:
            logger.info("工作目录干净，无需提交")
    except Exception as e:
        logger.warning(f"检查Git状态失败: {str(e)}")

def main():
    """主函数"""
    logger.info("🎯 论文收集定时任务调度器启动")
    logger.info("📅 任务时间: 每天北京时间 10:00 和 14:00")
    
    # 设置定时任务 - 北京时间10:00和14:00
    schedule.every().day.at("02:00").do(daily_task)  # UTC 02:00 = 北京时间 10:00
    schedule.every().day.at("06:00").do(daily_task)  # UTC 06:00 = 北京时间 14:00
    
    # 显示下次执行时间
    next_run = schedule.next_run()
    if next_run:
        beijing_next_run = next_run.replace(tzinfo=pytz.UTC).astimezone(beijing_tz)
        logger.info(f"⏰ 下次执行时间: {beijing_next_run.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")
    
    # 检查当前Git状态
    check_git_status()
    
    # 主循环
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    except KeyboardInterrupt:
        logger.info("👋 接收到停止信号，正在退出...")
    except Exception as e:
        logger.error(f"❌ 调度器运行异常: {str(e)}")

if __name__ == "__main__":
    main()
