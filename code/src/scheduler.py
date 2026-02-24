
import schedule
import time
import logging
import signal
import sys
from .config import Config
from .strategy_engine import StrategyEngine
from .notifier import NotificationManager, AlertMessage

# Setup Logging
Config.setup_logging()
logger = logging.getLogger("Scheduler")

def job():
    """
    定时任务入口
    """
    logger.info("Running scheduled job...")
    try:
        engine = StrategyEngine()
        engine.run()
    except Exception as e:
        logger.exception(f"Job failed with error: {e}")
        NotificationManager.send(AlertMessage(
            title="任务执行失败",
            content=f"每日任务异常终止: {str(e)}",
            level="ERROR"
        ))

def run_scheduler():
    """
    启动调度器
    """
    logger.info(f"Scheduler started. Task scheduled at {Config.SCHEDULE_TIME} daily.")
    
    # 每天定点执行
    schedule.every().day.at(Config.SCHEDULE_TIME).do(job)
    
    # 启动时先运行一次检查 (可选，方便调试)
    # job()
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user.")
            break
        except Exception as e:
            logger.error(f"Scheduler loop error: {e}")
            time.sleep(60)

def signal_handler(sig, frame):
    logger.info('Gracefully shutting down...')
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    run_scheduler()
