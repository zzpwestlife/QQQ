
import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from .config import Config
from .data_fetcher import DataFetcher
from .notifier import NotificationManager, AlertMessage

logger = logging.getLogger(__name__)

@dataclass
class MarketState:
    """
    市场状态快照
    """
    date: str
    price_qqq: float
    price_tqqq: float
    ma200: float
    ma20: float
    prev_ma20: float
    ath_price: float
    drawdown: float
    vol_ma: float
    vol_qqq: float
    is_top_signal: bool
    state_label: str
    risk_off_days: int
    pending_buy: bool
    pending_target_q: float
    pending_target_t: float

class StrategyEngine:
    """
    核心策略逻辑 (Ported from code/tqqq.py)
    """
    
    def __init__(self, state_file: str = "strategy_state.json"):
        self.state_file = state_file
        self.state = MarketState(
            date=str(date.today()),
            price_qqq=0.0,
            price_tqqq=0.0,
            ma200=0.0,
            ma20=0.0,
            prev_ma20=0.0,
            ath_price=0.0,
            drawdown=0.0,
            vol_ma=0.0,
            vol_qqq=0.0,
            is_top_signal=False,
            state_label="INIT",
            risk_off_days=0,
            pending_buy=False,
            pending_target_q=0.0,
            pending_target_t=0.0
        )
        self.load_state()

    def load_state(self):
        """
        加载上次运行的状态
        """
        try:
            import json
            if not os.path.exists(self.state_file):
                logger.info("No state file found, initializing new state.")
                return
            
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                self.state = MarketState(**data)
            logger.info(f"Loaded state: {self.state.state_label}, Last run: {self.state.date}")
        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    def save_state(self):
        """
        保存当前状态
        """
        try:
            import json
            from dataclasses import asdict
            with open(self.state_file, 'w') as f:
                json.dump(asdict(self.state), f, indent=4)
            logger.info("State saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def run(self):
        """
        执行每日策略逻辑
        """
        logger.info("Starting strategy execution...")
        
        # 1. 获取数据
        df_qqq = DataFetcher.fetch_data(Config.SYMBOL_QQQ, period="2y")
        df_tqqq = DataFetcher.fetch_data(Config.SYMBOL_TQQQ, period="3mo")
        
        if df_qqq is None or df_qqq.empty or df_tqqq is None or df_tqqq.empty:
            NotificationManager.send(AlertMessage(
                title="数据获取失败",
                content="无法获取 QQQ 或 TQQQ 的历史数据，策略中止。",
                level="ERROR"
            ))
            return

        # 2. 计算指标
        # 确保数据按日期排序
        df_qqq.sort_index(inplace=True)
        
        # 获取最新一天的收盘数据 (通常是昨收，或者是盘后获取的当日收盘)
        # 注意：如果是在盘中运行，Yahoo Finance 可能返回的是最新的实时价格作为当天的 Close
        current_date = df_qqq.index[-1].strftime('%Y-%m-%d')
        
        # 防止重复运行 (同一天只运行一次)
        if self.state.date == current_date and self.state.state_label != "INIT":
            logger.info(f"Strategy already run for date {current_date}. Skipping.")
            # Uncomment below if you want to force run for testing
            # pass 
            pass

        close_qqq = float(df_qqq['close'].iloc[-1])
        open_qqq = float(df_qqq['open'].iloc[-1])
        vol_qqq = float(df_qqq['volume'].iloc[-1])
        close_tqqq = float(df_tqqq['close'].iloc[-1])
        
        # MA 计算
        ma200_series = df_qqq['close'].rolling(window=Config.MA_LONG_WINDOW).mean()
        ma20_series = df_qqq['close'].rolling(window=Config.MA_SHORT_WINDOW).mean()
        
        if len(ma200_series) < 1 or pd.isna(ma200_series.iloc[-1]):
            logger.warning("Not enough data for MA200")
            return

        ma200 = float(ma200_series.iloc[-1])
        ma20 = float(ma20_series.iloc[-1])
        prev_ma20 = float(ma20_series.iloc[-2]) if len(ma20_series) > 1 else ma20
        
        # Vol MA 计算
        vol_ma_series = df_qqq['volume'].rolling(window=Config.VOL_WINDOW).mean()
        vol_ma = float(vol_ma_series.iloc[-1]) if len(vol_ma_series) > 0 else 0.0
        
        # ATH 计算 (过去 252 天最高价)
        # 注意：这里需要包括当天吗？代码逻辑是先判断 close > ath 再更新 ath，这里简化为历史最高
        # 原始代码逻辑：_init_ath_price 是遍历过去 252 天。这里直接用 rolling max
        recent_high = df_qqq['high'].rolling(window=Config.ATH_LOOKBACK_DAYS).max().iloc[-1]
        
        # 更新 ATH (如果当前价格创新高)
        if close_qqq > self.state.ath_price:
            self.state.ath_price = close_qqq
        # 如果历史最高价比如说是 400，但 self.state.ath_price 是 0 (初始化)，则使用 recent_high
        if self.state.ath_price == 0.0:
            self.state.ath_price = float(recent_high)
            
        # Drawdown
        drawdown = (close_qqq / self.state.ath_price) - 1.0
        
        # 3. 核心逻辑判断
        # (1) T+1 买入执行 check
        if self.state.pending_buy:
            logger.info("Executing Pending Buy (T+1)...")
            NotificationManager.send(AlertMessage(
                title="【T+1 买入执行】",
                content=f"资金已结算。执行买入计划：QQQ {self.state.pending_target_q:.0%}, TQQQ {self.state.pending_target_t:.0%}。\n"
                        f"请登录券商账户手动买入。",
                level="INFO"
            ))
            self.state.pending_buy = False
            self.state.pending_target_q = 0.0
            self.state.pending_target_t = 0.0
            # 这里 return 吗？原策略是 return 的，因为 T+1 买入当天不进行新的信号判断（避免频繁交易）
            # 但如果 T+1 买入后市场剧变呢？原策略选择“执行买入”后直接 return。
            self.state.date = current_date
            self.save_state()
            return

        # (2) 逃顶信号 check
        is_top_signal = False
        if close_qqq >= self.state.ath_price * Config.HIGH_ZONE_THRESHOLD:
            if vol_qqq > vol_ma * Config.VOL_FACTOR:
                if close_qqq < open_qqq:  # 收阴线
                    is_top_signal = True
        
        # (3) 状态机流转
        next_state = self.state.state_label
        
        # 状态判定逻辑
        if is_top_signal:
            next_state = "TOP_ESCAPE"
        elif close_qqq < ma200:
            if drawdown <= -0.30:
                next_state = "ZONE_DESPAIR_TQQQ"
            elif drawdown <= -0.10:
                if close_qqq > ma20:
                    next_state = "ZONE_BATTLE_ATTACK"
                else:
                    next_state = "ZONE_BATTLE_DEFEND"
            else:
                next_state = "BEAR_CASH"
        else:
            if drawdown < -0.10:
                next_state = "ZONE_BATTLE_ATTACK"
            else:
                next_state = "NORMAL"

        # (4) Anti-V 过滤 (Risk Off Days)
        # 更新 risk_off_days 计数
        if self.state.state_label in ["BEAR_CASH", "ZONE_BATTLE_DEFEND", "TOP_ESCAPE"]:
            self.state.risk_off_days += 1
        else:
            self.state.risk_off_days = 0
            
        # 过滤逻辑
        risk_off_list = ["BEAR_CASH", "ZONE_BATTLE_DEFEND", "TOP_ESCAPE"]
        risk_on_list = ["ZONE_BATTLE_ATTACK", "NORMAL"]
        blocked = False
        blocked_reasons = []

        if self.state.state_label in risk_off_list and next_state in risk_on_list:
            if self.state.risk_off_days < 2:  # Min Risk Off Days
                blocked = True
                blocked_reasons.append(f"冷静期未满足 ({self.state.risk_off_days} < 2)")
            
            if ma20 <= prev_ma20:
                blocked = True
                blocked_reasons.append("MA20 斜率未向上")
        
        if blocked:
            logger.info(f"Signal blocked: {next_state} -> {self.state.state_label}. Reasons: {blocked_reasons}")
            NotificationManager.send(AlertMessage(
                title="【反转过滤】信号延迟",
                content=f"原始信号: {next_state}，但触发过滤: {'; '.join(blocked_reasons)}。保持当前状态: {self.state.state_label}。",
                level="WARNING"
            ))
            next_state = self.state.state_label

        # (5) 确定目标仓位
        tg_q = 0.0
        tg_t = 0.0
        
        if next_state == "ZONE_DESPAIR_TQQQ":
            tg_q, tg_t = 0.0, 0.99
        elif next_state == "ZONE_BATTLE_ATTACK":
            tg_q, tg_t = 0.0, 0.99
        elif next_state == "ZONE_BATTLE_DEFEND":
            tg_q, tg_t = 0.99, 0.0
        elif next_state == "BEAR_CASH":
            tg_q, tg_t = 0.0, 0.0
        elif next_state == "TOP_ESCAPE":
            tg_q, tg_t = 0.90, 0.0
        elif next_state == "NORMAL":
            tg_q, tg_t = 0.45, 0.45

        # (6) 触发交易信号
        if next_state != self.state.state_label:
            logger.info(f"State Change: {self.state.state_label} -> {next_state}")
            NotificationManager.send(AlertMessage(
                title=f"【信号触发】{self.state.state_label} -> {next_state}",
                content=f"状态变更！\n"
                        f"日期: {current_date}\n"
                        f"QQQ: {close_qqq:.2f}, MA200: {ma200:.2f}, MA20: {ma20:.2f}\n"
                        f"操作建议: 卖出当前持仓，目标仓位 QQQ {tg_q:.0%}, TQQQ {tg_t:.0%}。\n"
                        f"请今日执行卖出，等待明日买入 (T+1)。",
                level="INFO"
            ))
            
            # 标记 T+1
            self.state.pending_buy = True
            self.state.pending_target_q = tg_q
            self.state.pending_target_t = tg_t
            
        elif next_state == "NORMAL":
            # 再平衡逻辑 (简化版，仅提示)
            # 由于没有持仓市值数据，这里只能提示用户自行检查
            pass

        # 4. 更新状态
        self.state.date = current_date
        self.state.price_qqq = close_qqq
        self.state.price_tqqq = close_tqqq
        self.state.ma200 = ma200
        self.state.ma20 = ma20
        self.state.prev_ma20 = prev_ma20
        self.state.vol_qqq = vol_qqq
        self.state.vol_ma = vol_ma
        self.state.state_label = next_state
        self.state.drawdown = drawdown
        
        self.save_state()
        logger.info("Strategy run completed.")

if __name__ == "__main__":
    import os
    engine = StrategyEngine()
    engine.run()
