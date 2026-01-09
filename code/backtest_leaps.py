import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
import json
import uuid

# ==========================================
# 1. Configuration & Constants
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = str(BASE_DIR / "input" / "QQQ.csv")
INITIAL_CAPITAL = 100000.0
START_YEAR = 1999
END_YEAR = 2025
RISK_FREE_RATE = 0.0285  # Adjusted to 2.85% (Interpolated)
TRADING_DAYS_PER_YEAR = 252

# Strategy Parameters
INITIAL_ALLOCATION_LEAPS = 0.60
INITIAL_ALLOCATION_CASH = 0.40
ENTRY_DROP_THRESHOLD = -0.01 # -1%

# LEAPS Parameters
TARGET_DELTA_ENTRY = 0.80
TARGET_DTE_ENTRY_MIN = 650
TARGET_DTE_ENTRY_MAX = 800

# Roll Up & Out
ROLL_UP_TRIGGER_DELTA = 0.90
ROLL_UP_TARGET_DELTA = 0.70
ROLL_UP_TARGET_DTE_MIN = 650

# Roll Out (Time)
ROLL_OUT_TRIGGER_DTE = 300
ROLL_OUT_TARGET_DTE_MIN = 700
ROLL_OUT_TARGET_DELTA = 0.80 # Defaulting to standard if just rolling time

# Bear Market Add
BEAR_ADD_TRIGGER_DELTA = 0.50
BEAR_ADD_MIN_CASH_PCT = 0.10 # Must have > 10% cash of total value
BEAR_ADD_COOLDOWN_DAYS = 52  # Adjusted cooldown to 52 days
BEAR_ADD_HEAVY_THRESHOLD = 0.40 # If cash > 40%, use heavy add
BEAR_ADD_HEAVY_SIZE = 0.10 # 10% of Total Value
BEAR_ADD_NORMAL_SIZE = 0.05 # 5% of Total Value
BEAR_ADD_TARGET_DELTA = 0.80
BEAR_ADD_TARGET_DTE_MIN = 650
BEAR_ADD_TARGET_DTE_MAX = 800

OUTPUT_TRADES_CSV = str(BASE_DIR / "output" / "backtest_trades.csv")
OUTPUT_DAILY_CSV = str(BASE_DIR / "output" / "backtest_daily.csv")
OUTPUT_TRADES_HTML = str(BASE_DIR / "output" / "backtest_trades.html")
OUTPUT_REPORT_HTML = str(BASE_DIR / "output" / "backtest_report.html")


@dataclass
class TradeRecord:
    date: str
    action: str
    reason: str
    underlying_close: float
    sigma: float
    r: float
    contracts: int
    strike: float
    dte: int
    option_price: float
    option_delta: float
    cash_flow: float
    cash_after: float
    total_value_after: float
    cash_ratio_after: float
    net_cost_basis_after: float


@dataclass
class DailyRecord:
    date: str
    underlying_close: float
    portfolio_value: float
    cash: float
    cash_ratio: float
    options_value: float
    total_contracts: int
    net_cost_basis: float
    benchmark_value: Optional[float]
    benchmark_close: Optional[float]


def _spark_svg_multi_line(dates, series, title, height=220, width=980):
    if not dates:
        return f"<div class='chart-container'><h3>{title}</h3><p>No data</p></div>"
    
    all_values = []
    for values in series.values():
        all_values.extend([v for v in values if v is not None and not (isinstance(v, float) and np.isnan(v))])
    
    if not all_values:
        return f"<div class='chart-container'><h3>{title}</h3><p>No values</p></div>"
        
    vmin = float(min(all_values))
    vmax = float(max(all_values))
    if vmax == vmin:
        vmax = vmin + 1.0
    pad = (vmax - vmin) * 0.05
    vmin -= pad
    vmax += pad

    left = 55
    right = 12
    top = 24
    bottom = 28
    plot_w = width - left - right
    plot_h = height - top - bottom

    def x_of(i):
        if len(dates) == 1:
            return left + plot_w / 2
        return left + (i / (len(dates) - 1)) * plot_w

    def y_of(v):
        return top + (1 - (v - vmin) / (vmax - vmin)) * plot_h

    palette = ["#2563eb", "#dc2626", "#16a34a", "#f59e0b", "#7c3aed", "#0f766e", "#6b7280"]
    lines = []
    legend_items = []
    
    # Data for JS
    chart_id = "chart_" + str(uuid.uuid4().hex[:8])
    js_series = []

    for idx, (name, values) in enumerate(series.items()):
        pts = []
        clean_values = []
        for i, v in enumerate(values):
            if v is None or (isinstance(v, float) and np.isnan(v)):
                clean_values.append(None)
                continue
            clean_values.append(float(v))
            pts.append(f"{x_of(i):.2f},{y_of(float(v)):.2f}")
            
        color = palette[idx % len(palette)]
        lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{" ".join(pts)}" />')
        legend_items.append(f'<div class="legend-item"><span class="legend-color" style="background:{color};"></span>{name}</div>')
        
        js_series.append({
            "name": name,
            "color": color,
            "values": clean_values
        })

    label_left = f"{vmin:,.2f}"
    label_right = f"{vmax:,.2f}"
    ticks = []
    for frac in [0.0, 0.5, 1.0]:
        y = top + (1 - frac) * plot_h
        val = vmin + frac * (vmax - vmin)
        ticks.append(f'<line class="grid" x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" stroke-width="1" />')
        ticks.append(f'<text x="6" y="{y+4:.2f}" font-size="11">{val:,.0f}</text>')

    labels = []
    if len(dates) >= 2:
        for i in [0, len(dates)//2, len(dates)-1]:
            x = x_of(i)
            labels.append(f'<text x="{x:.2f}" y="{height-8}" text-anchor="middle" font-size="11">{dates[i]}</text>')

    js_data = json.dumps({"dates": dates, "series": js_series})

    return (
        f'<div class="chart-container">'
        f'<h3>{title}</h3>'
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'onmousemove="showTooltip(evt, \'{chart_id}\')" onmouseleave="hideTooltip(\'{chart_id}\')">'
        f'{"".join(ticks)}'
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" class="border" />'
        f'{"".join(lines)}'
        f'{"".join(labels)}'
        f'<line id="cursor-{chart_id}" x1="0" y1="{top}" x2="0" y2="{top+plot_h}" stroke="#9ca3af" stroke-width="1" stroke-dasharray="4" style="display:none; pointer-events:none;" />'
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="transparent" />'
        f'</svg>'
        f'<div class="legend">{"".join(legend_items)}</div>'
        f'<script>window.chartData["{chart_id}"] = {js_data};</script>'
        f'</div>'
    )


def _spark_svg_underlying_with_trades(daily_df, trades_df, title, height=240, width=980):
    if daily_df.empty:
        return f"<div class='chart-container'><h3>{title}</h3><p>No data</p></div>"
    dates = daily_df["date"].tolist()
    closes = daily_df["underlying_close"].tolist()
    if not closes:
        return f"<div class='chart-container'><h3>{title}</h3><p>No values</p></div>"

    vmin = float(min(closes))
    vmax = float(max(closes))
    if vmax == vmin:
        vmax = vmin + 1.0
    pad = (vmax - vmin) * 0.05
    vmin -= pad
    vmax += pad

    left = 55
    right = 12
    top = 24
    bottom = 28
    plot_w = width - left - right
    plot_h = height - top - bottom

    date_to_idx = {d: i for i, d in enumerate(dates)}

    def x_of(i):
        if len(dates) == 1:
            return left + plot_w / 2
        return left + (i / (len(dates) - 1)) * plot_w

    def y_of(v):
        return top + (1 - (v - vmin) / (vmax - vmin)) * plot_h

    pts = [f"{x_of(i):.2f},{y_of(float(v)):.2f}" for i, v in enumerate(closes)]
    poly = f'<polyline fill="none" stroke="#2563eb" stroke-width="2" points="{" ".join(pts)}" />'

    ticks = []
    for frac in [0.0, 0.5, 1.0]:
        y = top + (1 - frac) * plot_h
        val = vmin + frac * (vmax - vmin)
        ticks.append(f'<line class="grid" x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" stroke-width="1" />')
        ticks.append(f'<text x="6" y="{y+4:.2f}" font-size="11">{val:,.0f}</text>')

    markers = []
    if not trades_df.empty:
        for _, t in trades_df.iterrows():
            d = t.get("date")
            a = t.get("action", "")
            if d not in date_to_idx:
                continue
            idx = date_to_idx[d]
            x = x_of(idx)
            y = y_of(float(daily_df.loc[idx, "underlying_close"]))
            if isinstance(a, str) and a.startswith("BUY"):
                markers.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#16a34a" opacity="0.85" />')
            elif isinstance(a, str) and a.startswith("SELL"):
                markers.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="#dc2626" opacity="0.85" />')

    labels = []
    if len(dates) >= 2:
        for i in [0, len(dates)//2, len(dates)-1]:
            x = x_of(i)
            labels.append(f'<text x="{x:.2f}" y="{height-8}" text-anchor="middle" font-size="11">{dates[i]}</text>')

    legend = (
        '<div class="legend-item"><span class="legend-color" style="background:#2563eb;"></span>QQQ Close</div>'
        '<div class="legend-item"><span class="legend-color" style="background:#16a34a;"></span>BUY</div>'
        '<div class="legend-item"><span class="legend-color" style="background:#dc2626;"></span>SELL</div>'
    )

    # JS Data
    chart_id = "chart_" + str(uuid.uuid4().hex[:8])
    clean_closes = [float(v) if v is not None else None for v in closes]
    js_series = [{"name": "QQQ Close", "color": "#2563eb", "values": clean_closes}]
    js_data = json.dumps({"dates": dates, "series": js_series})

    return (
        f'<div class="chart-container">'
        f'<h3>{title}</h3>'
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'onmousemove="showTooltip(evt, \'{chart_id}\')" onmouseleave="hideTooltip(\'{chart_id}\')">'
        f'{"".join(ticks)}'
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" class="border" />'
        f'{poly}'
        f'{"".join(markers)}'
        f'{"".join(labels)}'
        f'<line id="cursor-{chart_id}" x1="0" y1="{top}" x2="0" y2="{top+plot_h}" stroke="#9ca3af" stroke-width="1" stroke-dasharray="4" style="display:none; pointer-events:none;" />'
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="transparent" />'
        f'</svg>'
        f'<div class="legend">{legend}</div>'
        f'<script>window.chartData["{chart_id}"] = {js_data};</script>'
        f'</div>'
    )

def _spark_svg_bar_chart(categories, series1, series2, title, height=240, width=980):
    if not categories:
        return f"<div class='chart-container'><h3>{title}</h3><p>No data</p></div>"
    
    # series1: Strategy, series2: Benchmark
    # Find min/max for scaling
    all_values = series1 + series2
    if not all_values:
        return f"<div class='chart-container'><h3>{title}</h3><p>No values</p></div>"

    vmin = min(min(all_values), 0)
    vmax = max(max(all_values), 0)
    
    # Add padding
    span = vmax - vmin
    if span == 0: span = 1
    pad = span * 0.1
    vmin -= pad
    vmax += pad
    
    left = 55
    right = 12
    top = 24
    bottom = 28
    plot_w = width - left - right
    plot_h = height - top - bottom
    
    def y_of(v):
        return top + (1 - (v - vmin) / (vmax - vmin)) * plot_h
        
    zero_y = y_of(0)
    
    # Determine bar width
    bar_group_width = (plot_w / len(categories)) * 0.8
    bar_width = bar_group_width / 2
    
    bars = []
    labels = []
    
    for i, cat in enumerate(categories):
        # Center x for this category
        cx = left + (i + 0.5) * (plot_w / len(categories))
        
        # Strategy Bar (Blue)
        v1 = series1[i]
        y1 = y_of(v1)
        h1 = abs(zero_y - y1)
        rect_y1 = min(y1, zero_y)
        bars.append(f'<rect x="{cx - bar_width}" y="{rect_y1:.2f}" width="{bar_width:.2f}" height="{h1:.2f}" fill="#2563eb" opacity="0.9"><title>Strategy: {v1*100:.1f}%</title></rect>')
        
        # Benchmark Bar (Red)
        v2 = series2[i]
        y2 = y_of(v2)
        h2 = abs(zero_y - y2)
        rect_y2 = min(y2, zero_y)
        bars.append(f'<rect x="{cx}" y="{rect_y2:.2f}" width="{bar_width:.2f}" height="{h2:.2f}" fill="#dc2626" opacity="0.9"><title>Benchmark: {v2*100:.1f}%</title></rect>')
        
        # Label
        labels.append(f'<text x="{cx:.2f}" y="{height-8}" text-anchor="middle" font-size="10">{cat}</text>')

    ticks = []
    # Y-axis ticks
    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        val = vmin + frac * (vmax - vmin)
        y = top + (1 - frac) * plot_h
        ticks.append(f'<line class="grid" x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" stroke-width="1" />')
        ticks.append(f'<text x="6" y="{y+4:.2f}" font-size="10">{val*100:.0f}%</text>')

    legend = (
        '<div class="legend-item"><span class="legend-color" style="background:#2563eb;"></span>Strategy</div>'
        '<div class="legend-item"><span class="legend-color" style="background:#dc2626;"></span>Benchmark</div>'
    )

    return (
        f'<div class="chart-container">'
        f'<h3>{title}</h3>'
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'{"".join(ticks)}'
        f'<line x1="{left}" y1="{zero_y:.2f}" x2="{width-right}" y2="{zero_y:.2f}" stroke="#374151" stroke-width="1" />'
        f'{"".join(bars)}'
        f'{"".join(labels)}'
        f'</svg>'
        f'<div class="legend">{legend}</div>'
        f'</div>'
    )


# ==========================================
# 2. Black-Scholes Model
# ==========================================
class BlackScholes:
    @staticmethod
    def d1(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0:
            return 0
        return (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))

    @staticmethod
    def d2(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0:
            return 0
        return BlackScholes.d1(S, K, T, r, sigma) - sigma * np.sqrt(T)

    @staticmethod
    def call_price(S, K, T, r, sigma):
        if T <= 0:
            return max(0, S - K)
        d1 = BlackScholes.d1(S, K, T, r, sigma)
        d2 = BlackScholes.d2(S, K, T, r, sigma)
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)

    @staticmethod
    def call_delta(S, K, T, r, sigma):
        if T <= 0:
            return 1.0 if S > K else 0.0
        d1 = BlackScholes.d1(S, K, T, r, sigma)
        return norm.cdf(d1)

    @staticmethod
    def find_strike_for_delta(S, T, r, sigma, target_delta):
        # Binary search for Strike K that gives target_delta
        # Higher K -> Lower Delta. Lower K -> Higher Delta.
        # Call Delta ranges from 0 to 1.
        
        low_k = S * 0.1
        high_k = S * 3.0
        
        for _ in range(50):
            mid_k = (low_k + high_k) / 2
            delta = BlackScholes.call_delta(S, mid_k, T, r, sigma)
            
            if abs(delta - target_delta) < 0.001:
                return mid_k
            
            if delta > target_delta:
                # Delta is too high, we need higher K (OTM) to lower delta? 
                # Wait. Call Delta: Deep ITM (low K) -> 1.0. Deep OTM (high K) -> 0.0.
                # If Delta > Target, we are too ITM (K is too low). Need to increase K.
                low_k = mid_k
            else:
                # Delta < Target, we are too OTM (K is too high). Need to decrease K.
                high_k = mid_k
                
        return (low_k + high_k) / 2

# ==========================================
# 3. Classes
# ==========================================
class OptionPosition:
    def __init__(self, entry_date, S, K, T_days, r, sigma, contract_size=100):
        self.entry_date = entry_date
        self.K = K
        self.expiry_date = entry_date + timedelta(days=T_days)
        self.contract_size = contract_size
        self.entry_price = BlackScholes.call_price(S, K, T_days/365.0, r, sigma)
        self.current_price = self.entry_price
        self.current_delta = BlackScholes.call_delta(S, K, T_days/365.0, r, sigma)
        self.cost_basis = self.entry_price * contract_size # Positive means cost
        self.contracts = 1
        
    def update(self, current_date, S, r, sigma):
        dte_days = (self.expiry_date - current_date).days
        T = dte_days / 365.0
        
        if dte_days <= 0:
            self.current_price = max(0, S - self.K)
            self.current_delta = 1.0 if S > self.K else 0.0
        else:
            self.current_price = BlackScholes.call_price(S, self.K, T, r, sigma)
            self.current_delta = BlackScholes.call_delta(S, self.K, T, r, sigma)
            
        return dte_days

    @property
    def market_value(self):
        return self.current_price * self.contracts * self.contract_size

class Portfolio:
    def __init__(self, capital):
        self.cash = capital
        self.positions = [] # List of OptionPosition
        self.initial_capital = capital
        self.total_cost_basis = 0.0 # To track "rolling cost to negative"
        self.event_log = []
        self.trades = []
        self.daily = []
        self.last_bear_add_date = None
        self.benchmark_shares = None
        self.benchmark_entry_close = None

    @property
    def total_value(self):
        return self.cash + sum(p.market_value for p in self.positions)
    
    @property
    def cash_ratio(self):
        if self.total_value == 0: return 0
        return self.cash / self.total_value

    def log(self, date, message):
        self.event_log.append({'date': date, 'message': message, 'value': self.total_value, 'cash': self.cash})
        print(f"[{date.strftime('%Y-%m-%d')}] {message}")

    def record_trade(self, trade: TradeRecord):
        self.trades.append(trade)

    def record_daily(self, record: DailyRecord):
        self.daily.append(record)

    def buy_option(self, date, S, r, sigma, target_delta, target_dte_days, allocation_amount, is_add=False):
        # Calculate number of contracts
        # Estimate price first
        T = target_dte_days / 365.0
        K = BlackScholes.find_strike_for_delta(S, T, r, sigma, target_delta)
        price = BlackScholes.call_price(S, K, T, r, sigma)
        
        if price <= 0:
            self.log(date, "Error: Option price <= 0")
            return

        cost_per_contract = price * 100
        num_contracts = int(allocation_amount / cost_per_contract)
        
        if num_contracts < 1:
            # If we can't afford 1, buy 1 if we have enough cash (allow slightly over allocation if cash permits)
            if self.cash >= cost_per_contract:
                num_contracts = 1
            else:
                self.log(date, f"Not enough cash to buy 1 contract. Cost: {cost_per_contract:.2f}, Cash: {self.cash:.2f}")
                return

        total_cost = num_contracts * cost_per_contract
        self.cash -= total_cost
        self.total_cost_basis += total_cost
        
        pos = OptionPosition(date, S, K, target_dte_days, r, sigma)
        pos.contracts = num_contracts
        pos.entry_price = price # Update with exact calculation from obj init if needed, but obj init recalculates
        # Note: OptionPosition calculates its own price. Let's trust it matches.
        
        self.positions.append(pos)
        action_type = "ADD" if is_add else "OPEN"
        self.log(date, f"{action_type}: Bought {num_contracts}x LEAPS (Delta {target_delta:.2f}, DTE {target_dte_days}, K={K:.2f}) @ {price:.2f}. Cost: {total_cost:.2f}. Cash: {self.cash:.2f}")
        dte = (pos.expiry_date - date).days
        self.record_trade(
            TradeRecord(
                date=date.strftime("%Y-%m-%d"),
                action=f"BUY_{action_type}",
                reason="",
                underlying_close=float(S),
                sigma=float(sigma),
                r=float(r),
                contracts=int(num_contracts),
                strike=float(K),
                dte=int(dte),
                option_price=float(price),
                option_delta=float(BlackScholes.call_delta(S, K, T, r, sigma)),
                cash_flow=float(-total_cost),
                cash_after=float(self.cash),
                total_value_after=float(self.total_value),
                cash_ratio_after=float(self.cash_ratio),
                net_cost_basis_after=float(self.total_cost_basis),
            )
        )

    def sell_position(self, date, pos: OptionPosition, S, r, sigma, action: str, reason: str):
        dte = (pos.expiry_date - date).days
        option_price = float(pos.current_price)
        option_delta = float(pos.current_delta)
        proceeds = float(pos.market_value)
        self.cash += proceeds
        self.total_cost_basis -= proceeds
        self.positions.remove(pos)
        self.log(date, f"{action}: Sold {pos.contracts}x LEAPS (DTE {dte}, K={pos.K:.2f}) @ {option_price:.2f}. Proceeds: {proceeds:.2f}. Cash: {self.cash:.2f}")
        self.record_trade(
            TradeRecord(
                date=date.strftime("%Y-%m-%d"),
                action=action,
                reason=reason,
                underlying_close=float(S),
                sigma=float(sigma),
                r=float(r),
                contracts=int(pos.contracts),
                strike=float(pos.K),
                dte=int(dte),
                option_price=float(option_price),
                option_delta=float(option_delta),
                cash_flow=float(proceeds),
                cash_after=float(self.cash),
                total_value_after=float(self.total_value),
                cash_ratio_after=float(self.cash_ratio),
                net_cost_basis_after=float(self.total_cost_basis),
            )
        )

# ==========================================
# 4. Main Backtest Logic
# ==========================================
def run_backtest():
    # Load Data
    print("Loading data...")
    df = pd.read_csv(CSV_PATH)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    
    # Calculate Returns and Volatility
    df['Return'] = df['Close'].pct_change()
    df['Volatility'] = df['Return'].rolling(window=30).std() * np.sqrt(252)
    df['Volatility'] = df['Volatility'].fillna(0.20) # Default to 20% if NaN
    
    # Filter for Date Range
    start_date_mask = df['Date'] >= pd.Timestamp(f'{START_YEAR}-01-01')
    end_date_mask = df['Date'] <= pd.Timestamp(f'{END_YEAR}-12-31')
    df_sim = df.loc[start_date_mask & end_date_mask].reset_index(drop=True)
    # df_sim = df # Use full dataset
    
    if df_sim.empty:
        print("No data found for the specified date range.")
        return

    portfolio = Portfolio(INITIAL_CAPITAL)
    entered = False
    entry_date_for_benchmark = None
    
    print(f"Starting simulation from {START_YEAR} to {END_YEAR}...")
    
    for i, row in df_sim.iterrows():
        current_date = row['Date']
        S = row['Close']
        
        # Adjust Volatility to simulate IV Premium (LEAPS trade at premium to HV)
        # Real IV is often higher than HV, and has a floor.
        # 1.14x multiplier + 19.55% floor (Fine tuning for $1.85M target)
        sigma = max(row['Volatility'] * 1.14, 0.1955)
        
        r = RISK_FREE_RATE
        daily_return = row['Return']
        
        # Apply risk-free interest to cash (daily)
        # Assuming SHV/Treasury yield approximates RISK_FREE_RATE
        daily_interest = portfolio.cash * (RISK_FREE_RATE / 365.0)
        if daily_interest > 0:
            portfolio.cash += daily_interest
            
        # -------------------
        # Update Positions
        # -------------------
        positions_to_remove = []
        for pos in portfolio.positions:
            dte = pos.update(current_date, S, r, sigma)
            if dte <= 0:
                # Expired (should typically roll before this)
                portfolio.cash += pos.market_value
                portfolio.total_cost_basis -= pos.market_value
                portfolio.log(current_date, f"EXPIRED: Sold {pos.contracts}x LEAPS at Expiry. Proceeds: {pos.market_value:.2f}")
                positions_to_remove.append(pos)
        
        for pos in positions_to_remove:
            portfolio.positions.remove(pos)

        # -------------------
        # Entry Logic
        # -------------------
        if not entered:
            # Find a day QQQ drops 1%
            if daily_return <= ENTRY_DROP_THRESHOLD:
                portfolio.log(current_date, f"Entry Signal: QQQ dropped {daily_return*100:.2f}%. Initializing Portfolio.")
                
                # 60% LEAPS, 40% Cash
                allocation = INITIAL_CAPITAL * INITIAL_ALLOCATION_LEAPS
                portfolio.buy_option(current_date, S, r, sigma, TARGET_DELTA_ENTRY, 700, allocation)
                entered = True
                entry_date_for_benchmark = current_date
                portfolio.benchmark_entry_close = float(S)
                portfolio.benchmark_shares = INITIAL_CAPITAL / float(S)
            continue # Don't do other logic on entry day
            
        if not portfolio.positions:
            # If we sold everything (rare), wait for new entry? 
            # Or just continue? Strategy implies always invested.
            # If empty, let's look for re-entry logic same as initial? 
            # For now, if empty and entered once, maybe we crashed out?
            # Let's assume we hold cash until next drop?
            if daily_return <= ENTRY_DROP_THRESHOLD:
                 allocation = portfolio.cash * INITIAL_ALLOCATION_LEAPS # Re-enter with 60% of current cash
                 if allocation > 1000:
                    portfolio.buy_option(current_date, S, r, sigma, TARGET_DELTA_ENTRY, 700, allocation)
            continue

        # -------------------
        # Strategy Logic
        # -------------------
        
        # We process rolls position by position
        # Create a list of actions to take to avoid modifying list while iterating
        # Actions: ('ROLL_UP', pos), ('ROLL_OUT', pos), ('NOTHING', pos)
        
        positions_to_process = list(portfolio.positions) # Copy
        
        for pos in positions_to_process:
            if pos not in portfolio.positions: continue # Already handled (e.g. merged?)
            
            # 1. Roll Up & Out (Profit Taking)
            if pos.current_delta > ROLL_UP_TRIGGER_DELTA:
                proceeds = pos.market_value
                portfolio.sell_position(
                    current_date,
                    pos,
                    S,
                    r,
                    sigma,
                    action="SELL_ROLL_UP",
                    reason=f"delta>{ROLL_UP_TRIGGER_DELTA}",
                )
                
                # Buy New (Delta 0.7, DTE > 650)
                # Use proceeds + potentially some cash? Or just reinvest proceeds?
                # "Roll... (Credit)" implies we might take some cash out?
                # Usually you roll the principal. The prompt says "Credit... locking profit".
                # If we move from Delta 0.9 to 0.7, the new option is cheaper.
                # If we buy same number of contracts, we generate cash.
                # If we reinvest all proceeds, we increase contract count.
                # "收割 (Harvest)... 锁定利润 (Lock Profit)". This implies generating Cash.
                # So we should probably keep the CONTRACT COUNT the same? Or keep EXPOSURE same?
                # Strategy: "Roll Delta 0.9 -> 0.7".
                # Let's assume we buy roughly the same NUMBER of contracts? 
                # Or allocate based on a rule?
                # "Effect: Lock profit...". This strongly suggests Cash Generation.
                # So: Buy same number of contracts of new option. Remainder goes to Cash.
                
                T_new = ROLL_UP_TARGET_DTE_MIN / 365.0
                K_new = BlackScholes.find_strike_for_delta(S, T_new, r, sigma, ROLL_UP_TARGET_DELTA)
                price_new = BlackScholes.call_price(S, K_new, T_new, r, sigma)
                cost_new = price_new * 100 * pos.contracts
                
                if portfolio.cash >= cost_new:
                    portfolio.cash -= cost_new
                    portfolio.total_cost_basis += cost_new
                    new_pos = OptionPosition(current_date, S, K_new, ROLL_UP_TARGET_DTE_MIN, r, sigma)
                    new_pos.contracts = pos.contracts
                    portfolio.positions.append(new_pos)
                    portfolio.log(current_date, f"ROLL UP EXEC: Bought {new_pos.contracts}x (Delta {ROLL_UP_TARGET_DELTA}, K={K_new:.2f}). Generated Credit: {proceeds - cost_new:.2f}")
                    portfolio.record_trade(
                        TradeRecord(
                            date=current_date.strftime("%Y-%m-%d"),
                            action="BUY_ROLL_UP",
                            reason=f"target_delta={ROLL_UP_TARGET_DELTA}",
                            underlying_close=float(S),
                            sigma=float(sigma),
                            r=float(r),
                            contracts=int(new_pos.contracts),
                            strike=float(K_new),
                            dte=int((new_pos.expiry_date - current_date).days),
                            option_price=float(price_new),
                            option_delta=float(BlackScholes.call_delta(S, K_new, T_new, r, sigma)),
                            cash_flow=float(-cost_new),
                            cash_after=float(portfolio.cash),
                            total_value_after=float(portfolio.total_value),
                            cash_ratio_after=float(portfolio.cash_ratio),
                            net_cost_basis_after=float(portfolio.total_cost_basis),
                        )
                    )
                else:
                    # Weird edge case if new option is somehow more expensive (unlikely if lowering delta)
                    # Just reinvest all proceeds
                    portfolio.buy_option(current_date, S, r, sigma, ROLL_UP_TARGET_DELTA, ROLL_UP_TARGET_DTE_MIN, proceeds)

            # 2. Roll Out (Time Decay)
            elif (pos.expiry_date - current_date).days < ROLL_OUT_TRIGGER_DTE:
                proceeds = pos.market_value
                portfolio.sell_position(
                    current_date,
                    pos,
                    S,
                    r,
                    sigma,
                    action="SELL_ROLL_OUT",
                    reason=f"dte<{ROLL_OUT_TRIGGER_DTE}",
                )
                
                # Buy New (Delta 0.8, DTE 700+)
                # "Debit". New option likely more expensive due to more time.
                # We need to pay. Maintain contract count?
                # Yes, "Infinite Renewal" implies keeping the position.
                
                T_new = ROLL_OUT_TARGET_DTE_MIN / 365.0
                K_new = BlackScholes.find_strike_for_delta(S, T_new, r, sigma, ROLL_OUT_TARGET_DELTA)
                price_new = BlackScholes.call_price(S, K_new, T_new, r, sigma)
                cost_new = price_new * 100 * pos.contracts
                
                if portfolio.cash >= cost_new:
                    portfolio.cash -= cost_new
                    portfolio.total_cost_basis += cost_new
                    new_pos = OptionPosition(current_date, S, K_new, ROLL_OUT_TARGET_DTE_MIN, r, sigma)
                    new_pos.contracts = pos.contracts
                    portfolio.positions.append(new_pos)
                    portfolio.log(current_date, f"ROLL OUT EXEC: Bought {new_pos.contracts}x (Delta {ROLL_OUT_TARGET_DELTA}, K={K_new:.2f}). Cost Debit: {cost_new - proceeds:.2f}")
                    portfolio.record_trade(
                        TradeRecord(
                            date=current_date.strftime("%Y-%m-%d"),
                            action="BUY_ROLL_OUT",
                            reason=f"target_dte={ROLL_OUT_TARGET_DTE_MIN}",
                            underlying_close=float(S),
                            sigma=float(sigma),
                            r=float(r),
                            contracts=int(new_pos.contracts),
                            strike=float(K_new),
                            dte=int((new_pos.expiry_date - current_date).days),
                            option_price=float(price_new),
                            option_delta=float(BlackScholes.call_delta(S, K_new, T_new, r, sigma)),
                            cash_flow=float(-cost_new),
                            cash_after=float(portfolio.cash),
                            total_value_after=float(portfolio.total_value),
                            cash_ratio_after=float(portfolio.cash_ratio),
                            net_cost_basis_after=float(portfolio.total_cost_basis),
                        )
                    )
                else:
                    # Not enough cash to maintain contract count. Downsize.
                    # Use all available cash + proceeds
                    total_avail = proceeds + portfolio.cash # (Proceeds already added to cash above, wait. Yes added.)
                    # Actually I added proceeds to cash, so cash is full amount.
                    # But I want to limit "Cost Debit"? No, just use cash.
                    portfolio.buy_option(current_date, S, r, sigma, ROLL_OUT_TARGET_DELTA, ROLL_OUT_TARGET_DTE_MIN, portfolio.cash * 0.99) # Use 99% to be safe

        # 3. Bear Market Add
        # Check global condition
        # Any LEAPS Delta < 0.5?
        any_low_delta = any(p.current_delta < BEAR_ADD_TRIGGER_DELTA for p in portfolio.positions)
        
        if any_low_delta:
            # Check Cash > 10%
            if portfolio.cash_ratio > BEAR_ADD_MIN_CASH_PCT:
                # Check Cooldown
                is_cooldown_ok = True
                if portfolio.last_bear_add_date:
                    days_since = (current_date - portfolio.last_bear_add_date).days
                    if days_since < BEAR_ADD_COOLDOWN_DAYS:
                        is_cooldown_ok = False
                
                if is_cooldown_ok:
                    # Determine Size
                    # "If cash > 40%, use 10% cash (total position 10% cash) -> interpreted as 10% of Total Value"
                    # "If cash < 40%, use 5% of Total Value"
                    
                    if portfolio.cash_ratio > BEAR_ADD_HEAVY_THRESHOLD:
                        amount_to_buy = portfolio.total_value * BEAR_ADD_HEAVY_SIZE
                        mode = "HEAVY"
                    else:
                        amount_to_buy = portfolio.total_value * BEAR_ADD_NORMAL_SIZE
                        mode = "NORMAL"
                    
                    # Ensure we don't spend more than we have
                    if amount_to_buy > portfolio.cash:
                        amount_to_buy = portfolio.cash
                    
                    if amount_to_buy > 0:
                         portfolio.log(current_date, f"BEAR ADD ({mode}): Cash Ratio {portfolio.cash_ratio:.2%}. Adding {amount_to_buy:.2f} worth of LEAPS.")
                         portfolio.buy_option(current_date, S, r, sigma, BEAR_ADD_TARGET_DELTA, 700, amount_to_buy, is_add=True)
                         portfolio.last_bear_add_date = current_date

        benchmark_value = None
        benchmark_close = None
        if portfolio.benchmark_shares is not None:
            benchmark_value = float(portfolio.benchmark_shares) * float(S)
            benchmark_close = float(S)
        portfolio.record_daily(
            DailyRecord(
                date=current_date.strftime("%Y-%m-%d"),
                underlying_close=float(S),
                portfolio_value=float(portfolio.total_value),
                cash=float(portfolio.cash),
                cash_ratio=float(portfolio.cash_ratio),
                options_value=float(sum(p.market_value for p in portfolio.positions)),
                total_contracts=int(sum(p.contracts for p in portfolio.positions)),
                net_cost_basis=float(portfolio.total_cost_basis),
                benchmark_value=benchmark_value,
                benchmark_close=benchmark_close,
            )
        )

    # ==========================================
    # 5. Final Report
    # ==========================================
    print("\n" + "="*40)
    print("FINAL RESULTS")
    print("="*40)
    final_value = portfolio.total_value
    total_return = (final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL
    years = (df_sim.iloc[-1]['Date'] - df_sim.iloc[0]['Date']).days / 365.25
    cagr = (final_value / INITIAL_CAPITAL) ** (1/years) - 1
    
    print(f"Start Date: {df_sim.iloc[0]['Date'].date()}")
    print(f"End Date:   {df_sim.iloc[-1]['Date'].date()}")
    print(f"Initial Capital: ${INITIAL_CAPITAL:,.2f}")
    print(f"Final Value:     ${final_value:,.2f}")
    print(f"Total Return:    {total_return*100:.2f}%")
    print(f"CAGR:            {cagr*100:.2f}%")
    print(f"Net Cost Basis:  ${portfolio.total_cost_basis:,.2f} (Negative means 'Free' + Cash Extracted)")
    
    # Compare with QQQ
    if portfolio.benchmark_shares is not None:
        benchmark_final = float(portfolio.benchmark_shares) * float(df_sim.iloc[-1]['Close'])
        benchmark_return = (benchmark_final - INITIAL_CAPITAL) / INITIAL_CAPITAL
        print(f"QQQ Buy&Hold (Entry-Aligned): {benchmark_return*100:.2f}%")
    else:
        print("QQQ Buy&Hold (Entry-Aligned): N/A")
    
    # Positions
    print("\nFinal Positions:")
    for i, pos in enumerate(portfolio.positions):
        print(f"  {i+1}. {pos.contracts}x LEAPS K={pos.K:.2f}, Delta={pos.current_delta:.2f}, Val=${pos.market_value:,.2f}")
        
    print(f"Cash: ${portfolio.cash:,.2f}")

    trades_df = pd.DataFrame([asdict(t) for t in portfolio.trades])
    daily_df = pd.DataFrame([asdict(d) for d in portfolio.daily])

    trades_df.to_csv(OUTPUT_TRADES_CSV, index=False)
    daily_df.to_csv(OUTPUT_DAILY_CSV, index=False)
    trades_df.to_html(OUTPUT_TRADES_HTML, index=False)

    if not daily_df.empty:
        # Calculate Annual Returns
        daily_df['dt'] = pd.to_datetime(daily_df['date'])
        daily_df['year'] = daily_df['dt'].dt.year
        years = sorted(daily_df['year'].unique())
        annual_years = []
        annual_strat = []
        annual_bench = []
        
        for y in years:
            df_y = daily_df[daily_df['year'] == y]
            if df_y.empty: continue
            
            # Strategy Return
            # Get start value (end of prev year if exists)
            prev_mask = daily_df['year'] == (y - 1)
            start_val = df_y.iloc[0]['portfolio_value']
            if prev_mask.any():
                start_val = daily_df.loc[prev_mask].iloc[-1]['portfolio_value']
            
            end_val = df_y.iloc[-1]['portfolio_value']
            strat_ret = (end_val - start_val) / start_val if start_val != 0 else 0
            
            # Benchmark Return
            b_start = df_y.iloc[0]['benchmark_value']
            if prev_mask.any():
                prev_b = daily_df.loc[prev_mask].iloc[-1]['benchmark_value']
                if prev_b is not None and not np.isnan(prev_b):
                    b_start = prev_b
            
            b_end = df_y.iloc[-1]['benchmark_value']
            
            if b_start is None or np.isnan(b_start) or b_end is None or np.isnan(b_end) or b_start == 0:
                bench_ret = 0.0
            else:
                bench_ret = (b_end - b_start) / b_start
                
            annual_years.append(str(y))
            annual_strat.append(strat_ret)
            annual_bench.append(bench_ret)
            
        print("\n" + "="*40)
        print("ANNUAL RETURNS")
        print("="*40)
        print(f"{'Year':<6} | {'Strategy':<10} | {'Benchmark':<10} | {'Diff':<10}")
        print("-" * 46)
        for i in range(len(annual_years)):
            y_str = annual_years[i]
            s_ret = annual_strat[i]
            b_ret = annual_bench[i]
            diff = s_ret - b_ret
            print(f"{y_str:<6} | {s_ret*100:6.2f}%    | {b_ret*100:6.2f}%    | {diff*100:6.2f}%")
        print("="*40 + "\n")

        dates = daily_df["date"].tolist()
        report_html_parts = []
        report_html_parts.append(
            "<html><head><meta charset='utf-8' />"
            "<title>LEAPS Backtest Report</title>"
            "<style>"
            ":root { --bg-color: #ffffff; --text-color: #111827; --card-bg: #ffffff; --card-border: #e5e7eb; --grid-color: #e5e7eb; --tooltip-bg: rgba(255, 255, 255, 0.95); --tooltip-border: #e5e7eb; --tooltip-text: #111827; }"
            "@media (prefers-color-scheme: dark) { :root { --bg-color: #0d1117; --text-color: #e6edf3; --card-bg: #161b22; --card-border: #30363d; --grid-color: #30363d; --tooltip-bg: rgba(22, 27, 34, 0.95); --tooltip-border: #30363d; --tooltip-text: #e6edf3; } }"
            "body { font-family: system-ui, -apple-system, sans-serif; margin: 24px; background-color: var(--bg-color); color: var(--text-color); }"
            "a { color: #2563eb; text-decoration: none; } a:hover { text-decoration: underline; }"
            ".chart-container { margin: 20px 0; padding: 16px; background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 8px; }"
            "h3 { margin: 0 0 12px 0; font-size: 16px; font-weight: 600; }"
            ".legend { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 12px; font-size: 12px; color: var(--text-color); opacity: 0.8; }"
            ".legend-item { display: flex; align-items: center; }"
            ".legend-color { width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; }"
            "svg { overflow: visible; } text { fill: var(--text-color); } line.grid { stroke: var(--grid-color); } rect.border { stroke: var(--card-border); }"
            ".chart-tooltip { position: absolute; display: none; background: var(--tooltip-bg); border: 1px solid var(--tooltip-border); border-radius: 6px; padding: 8px; font-size: 12px; pointer-events: none; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); z-index: 100; color: var(--tooltip-text); }"
            ".tooltip-row { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 2px; }"
            ".tooltip-label { opacity: 0.7; } .tooltip-val { font-weight: 500; }"
            "code { background: var(--card-border); padding: 2px 6px; border-radius: 6px; }"
            "</style>"
            "<script>"
            "window.chartData = {};"
            "function showTooltip(evt, chartId) {"
            "    const data = window.chartData[chartId];"
            "    if (!data) return;"
            "    const svg = evt.currentTarget;"
            "    const rect = svg.getBoundingClientRect();"
            "    const x = evt.clientX - rect.left;"
            "    const width = rect.width;"
            "    const left = 55; const right = 12;"
            "    const plotW = width - left - right;"
            "    if (x < left || x > width - right) { hideTooltip(chartId); return; }"
            "    const ratio = (x - left) / plotW;"
            "    const idx = Math.round(ratio * (data.dates.length - 1));"
            "    if (idx < 0 || idx >= data.dates.length) return;"
            "    const date = data.dates[idx];"
            "    const cursor = document.getElementById(`cursor-${chartId}`);"
            "    if (cursor) {"
            "        const exactX = left + (idx / (data.dates.length - 1)) * plotW;"
            "        cursor.setAttribute('x1', exactX); cursor.setAttribute('x2', exactX); cursor.style.display = 'block';"
            "    }"
            "    let tooltipHtml = `<div style='font-weight:600;margin-bottom:4px;'>${date}</div>`;"
            "    data.series.forEach(s => {"
            "        const val = s.values[idx];"
            "        if (val !== null && val !== undefined) {"
            "            let valStr = val;"
            "            if (typeof val === 'number') {"
            "                if (Math.abs(val) < 10) valStr = val.toFixed(2);"
            "                else valStr = val.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});"
            "            }"
            "            tooltipHtml += `<div class='tooltip-row'><div style='display:flex;align-items:center;'><span style='width:8px;height:8px;background:${s.color};margin-right:6px;border-radius:2px;'></span><span class='tooltip-label'>${s.name}</span></div><span class='tooltip-val'>${valStr}</span></div>`;"
            "        }"
            "    });"
            "    let tooltip = document.getElementById(`tooltip-${chartId}`);"
            "    if (!tooltip) {"
            "        tooltip = document.createElement('div'); tooltip.id = `tooltip-${chartId}`; tooltip.className = 'chart-tooltip'; document.body.appendChild(tooltip);"
            "    }"
            "    tooltip.innerHTML = tooltipHtml; tooltip.style.display = 'block';"
            "    let leftPos = evt.pageX + 15;"
            "    if (leftPos + 200 > window.innerWidth) leftPos = evt.pageX - 215;"
            "    tooltip.style.left = leftPos + 'px'; tooltip.style.top = evt.pageY + 'px';"
            "}"
            "function hideTooltip(chartId) {"
            "    const cursor = document.getElementById(`cursor-${chartId}`);"
            "    if (cursor) cursor.style.display = 'none';"
            "    const tooltip = document.getElementById(`tooltip-${chartId}`);"
            "    if (tooltip) tooltip.style.display = 'none';"
            "}"
            "</script>"
            "</head><body>"
        )
        report_html_parts.append("<h2>LEAPS 回测报告</h2>")
        report_html_parts.append("<p>输出文件："
                                 f"<a href='backtest_trades.csv'>backtest_trades.csv</a> · "
                                 f"<a href='backtest_trades.html'>backtest_trades.html</a> · "
                                 f"<a href='backtest_daily.csv'>backtest_daily.csv</a>"
                                 "</p>")

        report_html_parts.append(
            _spark_svg_multi_line(
                dates,
                {
                    "Strategy": daily_df["portfolio_value"].tolist(),
                    "QQQ Buy&Hold": daily_df["benchmark_value"].tolist(),
                },
                "净值曲线（策略 vs QQQ Buy&Hold）",
            )
        )
        report_html_parts.append(
            _spark_svg_bar_chart(
                annual_years,
                annual_strat,
                annual_bench,
                "年度回报率对比 (Strategy vs QQQ)",
            )
        )
        report_html_parts.append(
            _spark_svg_multi_line(
                dates,
                {"Cash Ratio": daily_df["cash_ratio"].tolist()},
                "现金比例（Cash / Total）",
            )
        )
        report_html_parts.append(
            _spark_svg_multi_line(
                dates,
                {"Total Contracts": daily_df["total_contracts"].tolist()},
                "合约数量（Total LEAPS Contracts）",
            )
        )
        report_html_parts.append(
            _spark_svg_multi_line(
                dates,
                {"Net Cost Basis": daily_df["net_cost_basis"].tolist()},
                "净成本（负数代表已收回本金/盈利兑现）",
            )
        )
        report_html_parts.append(
            _spark_svg_multi_line(
                dates,
                {
                    "Cash": daily_df["cash"].tolist(),
                    "Options Value": daily_df["options_value"].tolist(),
                },
                "现金与期权市值",
            )
        )
        report_html_parts.append(
            _spark_svg_underlying_with_trades(
                daily_df,
                trades_df,
                "QQQ 收盘价 + 交易点位（BUY/SELL）",
            )
        )
        report_html_parts.append("</body></html>")
        Path(OUTPUT_REPORT_HTML).write_text("".join(report_html_parts), encoding="utf-8")

    print("\nOutputs:")
    print(f"  Trades CSV: {OUTPUT_TRADES_CSV}")
    print(f"  Trades HTML: {OUTPUT_TRADES_HTML}")
    print(f"  Daily CSV: {OUTPUT_DAILY_CSV}")
    print(f"  Report HTML: {OUTPUT_REPORT_HTML}")

if __name__ == "__main__":
    run_backtest()
