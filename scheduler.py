#!/usr/bin/env python3
"""
定时任务调度器
每天北京时间上午10点和中午12点执行论文收集和翻译任务
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
        ("python llm_process.py", "批量翻译论文"),
        ("python cleanup_empty_papers.py", "清理空日度JSON"),
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
    logger.info("📅 任务时间: 每天北京时间 10:00 和 12:00")
    
    # 设置定时任务 - 北京时间10:00和12:00对应的UTC时间
    # 北京时间比UTC快8小时，所以北京时间10:00 = UTC 02:00，北京时间12:00 = UTC 04:00
    schedule.every().day.at("02:00").do(daily_task)  # UTC 02:00 = 北京时间 10:00
    schedule.every().day.at("04:00").do(daily_task)  # UTC 04:00 = 北京时间 12:00
    
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
            
            # 显示距离下次任务的时间
            next_run = schedule.next_run()
            if next_run:
                # 获取当前UTC时间（不带时区信息，与schedule库保持一致）
                now = datetime.utcnow()
                time_until_next = next_run - now
                
                # 转换为北京时间显示
                beijing_next_run = next_run.replace(tzinfo=pytz.UTC).astimezone(beijing_tz)
                beijing_now = now.replace(tzinfo=pytz.UTC).astimezone(beijing_tz)
                
                # 计算剩余时间
                total_seconds = int(time_until_next.total_seconds())
                if total_seconds < 0:
                    total_seconds = 0  # 防止负数时间
                
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                
                logger.info(f"⏰ 当前时间: {beijing_now.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")
                logger.info(f"📅 下次任务: {beijing_next_run.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")
                logger.info(f"⏳ 距离下次执行还有: {hours}小时 {minutes}分钟 {seconds}秒")
                logger.info("-" * 40)
            
            time.sleep(60)  # 每分钟检查一次
    except KeyboardInterrupt:
        logger.info("👋 接收到停止信号，正在退出...")
    except Exception as e:
        logger.error(f"❌ 调度器运行异常: {str(e)}")

if __name__ == "__main__":
    main()
