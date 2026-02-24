
#!/usr/bin/env python3
"""
TQQQ 自动交易策略 - 本地运行入口
"""
import sys
import os

# 将 src 目录添加到路径，确保可以正确 import
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from src.scheduler import run_scheduler
from src.config import Config

if __name__ == "__main__":
    print("Starting TQQQ Auto-Trader System...")
    print(f"Log Directory: {Config.LOG_DIR}")
    print(f"Data Directory: {Config.DATA_DIR}")
    print(f"Scheduled Time: {Config.SCHEDULE_TIME}")
    
    run_scheduler()
