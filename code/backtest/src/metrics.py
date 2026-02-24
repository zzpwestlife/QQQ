
import pandas as pd
import numpy as np

def calculate_metrics(df_results, initial_capital=100000.0, risk_free_rate=0.0):
    """
    Calculate performance metrics from a daily portfolio value DataFrame.
    df_results: DataFrame with 'total_value' column, indexed by date.
    """
    df = df_results.copy()
    df['returns'] = df['total_value'].pct_change().fillna(0.0)
    
    # Total Return
    total_return = (df['total_value'].iloc[-1] / initial_capital) - 1.0
    
    # CAGR
    days = (df.index[-1] - df.index[0]).days
    years = days / 365.25
    if years > 0:
        cagr = (df['total_value'].iloc[-1] / initial_capital) ** (1 / years) - 1.0
    else:
        cagr = 0.0
        
    # Volatility (Annualized)
    volatility = df['returns'].std() * np.sqrt(252)
    
    # Max Drawdown
    cumulative_returns = (1 + df['returns']).cumprod()
    peak = cumulative_returns.cummax()
    drawdown = (cumulative_returns - peak) / peak
    max_drawdown = drawdown.min()
    
    # Sharpe Ratio
    excess_returns = df['returns'] - (risk_free_rate / 252)
    if df['returns'].std() > 0:
        sharpe_ratio = np.sqrt(252) * excess_returns.mean() / df['returns'].std()
    else:
        sharpe_ratio = 0.0
        
    # Calmar Ratio
    if abs(max_drawdown) > 0:
        calmar_ratio = cagr / abs(max_drawdown)
    else:
        calmar_ratio = 0.0
        
    return {
        "Total Return": total_return,
        "CAGR": cagr,
        "Annual Volatility": volatility,
        "Max Drawdown": max_drawdown,
        "Sharpe Ratio": sharpe_ratio,
        "Calmar Ratio": calmar_ratio
    }

def calculate_trade_metrics(orders):
    """
    Calculate trade-based metrics (Win Rate, P/L Ratio).
    This is tricky because orders are just executions.
    Simplification: We won't calculate per-trade P&L here accurately without a proper trade matcher (FIFO/LIFO).
    We will just count trades.
    """
    trade_count = len(orders)
    return {
        "Trade Count": trade_count
    }
