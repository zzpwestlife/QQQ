
import math
import logging
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

# --- Enums ---
class AlgoStrategyType(Enum):
    SECURITY = auto()

class BarType(Enum):
    D1 = auto()

class DataType(Enum):
    CLOSE = auto()
    OPEN = auto()
    HIGH = auto()
    LOW = auto()
    VOLUME = auto()

class OrderSide(Enum):
    BUY = auto()
    SELL = auto()

class OrderStatus(Enum):
    FILLED_ALL = auto()
    CANCELLED_ALL = auto()
    FAILED = auto()
    DELETED = auto()
    SUBMITTED = auto()

class OrdType(Enum):
    MKT = auto()
    LMT = auto()

class TimeInForce(Enum):
    DAY = auto()

class THType(Enum):
    RTH = auto()

class TSType(Enum):
    RTH = auto()

class Currency(Enum):
    USD = auto()
    HKD = auto()

class TimeZone(Enum):
    MARKET_TIME_ZONE = auto()

# --- Classes ---
class Contract:
    def __init__(self, symbol):
        self.symbol = symbol
    def __str__(self):
        return self.symbol
    def __repr__(self):
        return self.symbol
    def __eq__(self, other):
        if isinstance(other, Contract):
            return self.symbol == other.symbol
        return False
    def __hash__(self):
        return hash(self.symbol)

@dataclass
class Order:
    order_id: str
    symbol: Contract
    qty: int
    side: OrderSide
    price: float  # Executed price
    status: OrderStatus
    timestamp: pd.Timestamp

class MockContext:
    def __init__(self, df_qqq, df_tqqq, initial_capital=100000.0, commission_rate=0.0005, slippage=0.0005):
        self.df_qqq = df_qqq
        self.df_tqqq = df_tqqq
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_rate = commission_rate
        self.slippage = slippage  # Percentage slippage
        self.current_date = None
        self.positions: Dict[str, int] = {"US.QQQ": 0, "US.TQQQ": 0}
        self.orders: List[Order] = []
        self.next_order_id = 1
        self.portfolio_history = []
        self.signals_history = []
        self.last_signal = None

    def get_price(self, symbol, field='close', offset=0):
        # symbol: Contract object or string
        sym_str = symbol.symbol if isinstance(symbol, Contract) else symbol
        
        if "QQQ" in sym_str and "TQQQ" not in sym_str:
            df = self.df_qqq
        elif "TQQQ" in sym_str:
            df = self.df_tqqq
        else:
            return None
        
        # Current date index
        try:
            loc = df.index.get_loc(self.current_date)
            # Offset is backward looking (select=1 is today, select=2 is yesterday)
            # tqqq.py logic: select=1 means current bar (most recent closed bar if backtesting on Close)
            # In backtest loop, 'current_date' is 'today'. So select=1 is today.
            target_loc = loc - (offset - 1)
            if target_loc < 0:
                return None
            
            val = df.iloc[target_loc][field]
            if pd.isna(val):
                return None
            return float(val)
        except KeyError:
            return None
        except IndexError:
            return None

    def get_data_slice(self, symbol, field, length):
        sym_str = symbol.symbol if isinstance(symbol, Contract) else symbol
        if "QQQ" in sym_str and "TQQQ" not in sym_str:
            df = self.df_qqq
        elif "TQQQ" in sym_str:
            df = self.df_tqqq
        else:
            return []
            
        try:
            loc = df.index.get_loc(self.current_date)
            start_loc = loc - length + 1
            if start_loc < 0:
                start_loc = 0
            # Return list
            return df.iloc[start_loc : loc + 1][field].tolist()
        except:
            return []

    def execute_order(self, symbol, qty, side):
        sym_str = symbol.symbol
        price = self.get_price(symbol, 'open', 1) # Executing at Open of *current* bar?
        # Actually, tqqq.py places market orders. In backtest, we usually execute at Close of current bar or Open of NEXT bar.
        # Since tqqq.py logic runs 'handle_data', usually meant for 'on_bar_close' or periodic check.
        # If it runs at close, market orders fill at close (or next open).
        # Let's assume fills at CLOSE of current bar for simplicity in daily bars, or NEXT OPEN.
        # Given T+1 logic:
        # Day T: Signal -> Sell. (Executes today? Or tomorrow?)
        # tqqq.py says: "place_market".
        # If running daily after close, order fills next open.
        # If running daily before close, order fills close.
        # Let's assume fills at CLOSE price of current day (simulating MOC or immediate execution).
        price = self.get_price(symbol, 'close', 1)
        
        if price is None or price <= 0:
            return
        
        # Apply slippage
        if side == OrderSide.BUY:
            exec_price = price * (1 + self.slippage)
        else:
            exec_price = price * (1 - self.slippage)
            
        # Value
        value = exec_price * qty
        commission = max(1.0, value * self.commission_rate) # Min 1 USD
        
        if side == OrderSide.BUY:
            cost = value + commission
            if self.cash >= cost:
                self.cash -= cost
                self.positions[sym_str] += qty
                self.orders.append(Order(str(self.next_order_id), symbol, qty, side, exec_price, OrderStatus.FILLED_ALL, self.current_date))
                self.next_order_id += 1
            else:
                # Adjust qty if not enough cash? tqqq.py has 'max_qty_to_buy_on_cash' logic, but here we execute what's passed
                pass
        elif side == OrderSide.SELL:
            revenue = value - commission
            if self.positions[sym_str] >= qty:
                self.positions[sym_str] -= qty
                self.cash += revenue
                self.orders.append(Order(str(self.next_order_id), symbol, qty, side, exec_price, OrderStatus.FILLED_ALL, self.current_date))
                self.next_order_id += 1

    def update_portfolio(self):
        val_qqq = self.positions["US.QQQ"] * (self.get_price("US.QQQ", 'close', 1) or 0)
        val_tqqq = self.positions["US.TQQQ"] * (self.get_price("US.TQQQ", 'close', 1) or 0)
        total_value = self.cash + val_qqq + val_tqqq
        self.portfolio_history.append({
            'date': self.current_date,
            'cash': self.cash,
            'qqq_val': val_qqq,
            'tqqq_val': val_tqqq,
            'total_value': total_value,
            'qqq_qty': self.positions["US.QQQ"],
            'tqqq_qty': self.positions["US.TQQQ"]
        })

# --- Global API Mocks ---
# These will be injected into the strategy namespace
context: MockContext = None

def set_context(ctx):
    global context
    context = ctx

def declare_strategy_type(type): pass
def declare_trig_symbol(): pass
def alert(title, content): 
    # logging.info(f"ALERT: {title} - {content}")
    pass

def bar_close(symbol, bar_type, select, session_type):
    return context.get_price(symbol, 'close', select)

def bar_open(symbol, bar_type, select, session_type):
    return context.get_price(symbol, 'open', select)

def bar_high(symbol, bar_type, select, session_type):
    return context.get_price(symbol, 'high', select)

def bar_volume(symbol, bar_type, select, session_type):
    return context.get_price(symbol, 'volume', select)

def ma(symbol, period, bar_type, data_type, select, session_type):
    # Calculate MA on the fly or using rolling window
    # select=1 means current bar. window=period.
    # Need history of length (period + select - 1)
    data = context.get_data_slice(symbol, 'close', period + select - 1)
    if len(data) < period:
        return None
    # If select=1, use last 'period' items
    # If select=2, use items from -(period+1) to -1
    end_idx = len(data) - (select - 1)
    start_idx = end_idx - period
    if start_idx < 0:
        return None
    
    subset = data[start_idx:end_idx]
    if not subset:
        return None
    return sum(subset) / len(subset)

def rsi(symbol, period, bar_type, data_type, select, session_type):
    # RSI implementation
    # Need period + select + lookback for calculation
    # Standard RSI requires previous average gain/loss, which implies recursive calc or long history
    # Simple approximation using rolling window
    lookback = period * 5 # Get enough data
    data = context.get_data_slice(symbol, 'close', lookback + select)
    if not data or len(data) < period + 1:
        return 50.0 # Default neutral
    
    # Trim to relevant end
    end_idx = len(data) - (select - 1)
    if end_idx < period + 1:
        return 50.0
        
    prices = data[:end_idx]
    # We need to calculate RSI for the last point
    # Use pandas for efficiency if possible, but data is list
    # Convert to series
    s = pd.Series(prices)
    delta = s.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi_val = 100 - (100 / (1 + rs))
    
    val = rsi_val.iloc[-1]
    if np.isnan(val):
        return 50.0
    return float(val)

def vol(symbol, period, select=1):
    # Annualized Volatility
    # select=1 means current window
    data = context.get_data_slice(symbol, 'close', period + select)
    if not data or len(data) < period + 1:
        return 0.0
        
    end_idx = len(data) - (select - 1)
    prices = data[:end_idx]
    s = pd.Series(prices)
    ret = s.pct_change().dropna()
    # Take last 'period' returns
    if len(ret) < period:
        return 0.0
    
    ret_window = ret.tail(period)
    # Annualize
    return float(ret_window.std() * np.sqrt(252))


def request_orderid(symbol, status, start, end, time_zone):
    return [] # Always empty for backtest (instant fill)

def order_status(orderid):
    return OrderStatus.FILLED_ALL

def position_holding_qty(symbol):
    sym_str = symbol.symbol
    return context.positions.get(sym_str, 0)

def available_qty(symbol):
    sym_str = symbol.symbol
    return context.positions.get(sym_str, 0)

def position_market_cap(symbol):
    qty = position_holding_qty(symbol)
    price = bar_close(symbol, None, 1, None)
    if price:
        return qty * price
    return 0.0

def net_asset(currency):
    # Approximate
    val_qqq = position_market_cap(Contract("US.QQQ"))
    val_tqqq = position_market_cap(Contract("US.TQQQ"))
    return context.cash + val_qqq + val_tqqq

def place_market(symbol, qty, side, time_in_force):
    context.execute_order(symbol, qty, side)

def max_qty_to_buy_on_cash(symbol, order_type, price, order_trade_session_type):
    # Calculate max qty based on current cash
    price = bar_close(symbol, None, 1, None)
    if not price or price <= 0:
        return 0
    # Add buffer for commission/slippage
    available_cash = context.cash * 0.99 
    return int(available_cash / price)

# --- Base Class ---
class StrategyBase:
    def initialize(self): pass
    def handle_data(self): pass
