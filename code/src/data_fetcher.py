
import yfinance as yf
import pandas as pd
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class DataFetcher:
    """
    负责从 Yahoo Finance 获取历史数据
    """
    
    @staticmethod
    def fetch_data(symbol: str, period: str = "2y", interval: str = "1d") -> Optional[pd.DataFrame]:
        """
        获取 OHLCV 数据
        :param symbol: 标的代码 (如 "QQQ")
        :param period: 历史数据长度 (如 "2y", "5y", "max")
        :param interval: K线周期 (如 "1d")
        :return: DataFrame or None
        """
        try:
            logger.info(f"Fetching data for {symbol} (period={period}, interval={interval})...")
            
            # 使用 yfinance 下载数据
            df = yf.download(
                tickers=symbol,
                period=period,
                interval=interval,
                progress=False,
                threads=True,
                ignore_tz=True  # 忽略时区，简化处理
            )
            
            if df.empty:
                logger.warning(f"No data returned for {symbol}")
                return None
            
            # 清理列名 (yfinance 可能返回 MultiIndex)
            if isinstance(df.columns, pd.MultiIndex):
                # 尝试扁平化，取第一级
                try:
                    df.columns = df.columns.droplevel(1)
                except Exception:
                    pass
            
            # 确保列名规范化
            df.rename(columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
                "Adj Close": "adj_close"
            }, inplace=True)
            
            # 简单校验
            required_cols = ["close", "high", "volume"]
            if not all(col in df.columns for col in required_cols):
                logger.error(f"Missing required columns in data for {symbol}: {df.columns}")
                return None

            # 处理缺失值
            df.dropna(subset=["close"], inplace=True)
            
            logger.info(f"Successfully fetched {len(df)} records for {symbol}. Last date: {df.index[-1]}")
            return df
            
        except Exception as e:
            logger.exception(f"Error fetching data for {symbol}: {e}")
            return None

    @staticmethod
    def get_latest_price(symbol: str) -> float:
        """
        获取最新收盘价 (用于盘中或盘后快速检查)
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            if hasattr(info, "last_price"):
                return float(info.last_price)
            
            # Fallback to history
            hist = ticker.history(period="1d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
            return 0.0
        except Exception as e:
            logger.error(f"Error getting latest price for {symbol}: {e}")
            return 0.0
