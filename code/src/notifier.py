
import logging
from typing import Optional
from dataclasses import dataclass
from .config import Config

logger = logging.getLogger(__name__)

@dataclass
class AlertMessage:
    title: str
    content: str
    level: str = "INFO"  # INFO, WARNING, ERROR

class NotificationManager:
    """
    通知管理器
    """
    
    @staticmethod
    def send(message: AlertMessage):
        """
        发送通知 (本地日志 + 邮件/Push)
        """
        
        # 1. 记录日志
        if message.level == "ERROR":
            logger.error(f"[ALERT] {message.title} - {message.content}")
        elif message.level == "WARNING":
            logger.warning(f"[ALERT] {message.title} - {message.content}")
        else:
            logger.info(f"[ALERT] {message.title} - {message.content}")
        
        # 2. 发送邮件 (如果配置了)
        if Config.SMTP_USER and Config.EMAIL_TO:
            try:
                import smtplib
                from email.mime.text import MIMEText
                
                msg = MIMEText(message.content, 'plain', 'utf-8')
                msg['Subject'] = f"[TQQQ-Strategy] {message.title}"
                msg['From'] = Config.SMTP_USER
                msg['To'] = Config.EMAIL_TO
                
                with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
                    server.starttls()
                    server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                    server.send_message(msg)
                
                logger.info("Email sent successfully.")
                
            except Exception as e:
                logger.error(f"Failed to send email: {e}")
        
        # 3. 桌面通知 (可选)
        try:
            from plyer import notification
            notification.notify(
                title=message.title,
                message=message.content[:256],  # 截断
                app_name="TQQQ Strategy",
                timeout=10
            )
        except ImportError:
            pass  # 忽略
        except Exception:
            pass
