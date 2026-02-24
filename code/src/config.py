
# 配置管理
import os
import logging
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Config:
    # 交易标的
    SYMBOL_QQQ: str = "QQQ"
    SYMBOL_TQQQ: str = "TQQQ"
    
    # 策略参数
    MA_LONG_WINDOW: int = 200
    MA_SHORT_WINDOW: int = 20
    VOL_WINDOW: int = 60
    VOL_FACTOR: float = 2.0
    HIGH_ZONE_THRESHOLD: float = 0.95
    ATH_LOOKBACK_DAYS: int = 252
    
    # 运行设置
    DATA_DIR: str = os.path.join(os.getcwd(), "code", "data")
    LOG_DIR: str = os.path.join(os.getcwd(), "code", "logs")
    SCHEDULE_TIME: str = "16:30"  # 美股收盘后 (美东时间 16:00 -> 本地时间需换算，这里假设用户会根据时区调整)
    MAX_RETRIES: int = 3
    RETRY_DELAY_SEC: int = 60
    
    # 邮件通知 (可选，需在 .env 配置)
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    EMAIL_TO: str = os.getenv("EMAIL_TO", "")

    # 日志级别
    LOG_LEVEL: int = logging.INFO

    @classmethod
    def setup_logging(cls):
        if not os.path.exists(cls.LOG_DIR):
            os.makedirs(cls.LOG_DIR)
        
        log_file = os.path.join(cls.LOG_DIR, "strategy.log")
        logging.basicConfig(
            level=cls.LOG_LEVEL,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
