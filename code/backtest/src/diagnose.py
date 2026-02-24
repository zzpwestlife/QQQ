
import pandas as pd
import numpy as np
import os

def calculate_max_drawdown(equity_curve):
    """Calculate Max Drawdown and Duration."""
    high_water_mark = equity_curve.cummax()
    drawdown = (equity_curve - high_water_mark) / high_water_mark
    max_dd = drawdown.min()
    return max_dd, drawdown

def calculate_metrics(daily_returns, equity_curve):
    """Calculate CAGR, Vol, Sharpe, Sortino, Win Rate."""
    trading_days = 252
    
    # CAGR
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
    years = len(daily_returns) / trading_days
    cagr = (equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (1/years) - 1
    
    # Volatility
    ann_vol = daily_returns.std() * np.sqrt(trading_days)
    
    # Sharpe (Rf=3%)
    rf = 0.03
    sharpe = (daily_returns.mean() * trading_days - rf) / (ann_vol + 1e-9)
    
    # Sortino (Rf=3%)
    downside_returns = daily_returns[daily_returns < 0]
    downside_vol = downside_returns.std() * np.sqrt(trading_days)
    sortino = (daily_returns.mean() * trading_days - rf) / (downside_vol + 1e-9)
    
    # Win Rate
    win_rate = len(daily_returns[daily_returns > 0]) / len(daily_returns)
    
    return {
        "CAGR": cagr,
        "Vol": ann_vol,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "WinRate": win_rate,
        "TotalReturn": total_return
    }

import sys

def run_diagnosis(output_dir=None):
    # 1. Load Data
    if output_dir is None:
        # Default to output_opt if not specified, or check sys.argv
        if len(sys.argv) > 1:
            output_dir = sys.argv[1]
        else:
            output_dir = "/Users/joeyzou/Code/OpenSource/QQQ/code/backtest/output_opt"
            
    print(f"Diagnosing results in: {output_dir}")
    tqqq_path = os.path.join(output_dir, "tqqq_backtest_result.csv")
    qqq_path = os.path.join(output_dir, "qqq_backtest_result.csv")
    
    if not os.path.exists(tqqq_path) or not os.path.exists(qqq_path):
        print(f"Error: Files not found.")
        return

    # Load TQQQ Strategy Result
    df_strat = pd.read_csv(tqqq_path, header=0, parse_dates=['date'])
    df_strat.set_index('date', inplace=True)
    df_strat.rename(columns={'total_value': 'StrategyAssets'}, inplace=True)
    
    # Load QQQ Benchmark Result
    df_bench = pd.read_csv(qqq_path, header=0, parse_dates=['date'])
    df_bench.set_index('date', inplace=True)
    df_bench.rename(columns={'total_value': 'BenchmarkAssets'}, inplace=True)
    
    # Merge
    df = df_strat.join(df_bench[['BenchmarkAssets']], how='inner')
    
    # 2. Daily Returns
    df['Strategy_Ret'] = df['StrategyAssets'].pct_change().fillna(0)
    df['Benchmark_Ret'] = df['BenchmarkAssets'].pct_change().fillna(0)
    
    # 3. Overall Metrics
    strat_dd, strat_dd_curve = calculate_max_drawdown(df['StrategyAssets'])
    bench_dd, bench_dd_curve = calculate_max_drawdown(df['BenchmarkAssets'])
    
    strat_metrics = calculate_metrics(df['Strategy_Ret'], df['StrategyAssets'])
    bench_metrics = calculate_metrics(df['Benchmark_Ret'], df['BenchmarkAssets'])
    
    print("="*80)
    print("OVERALL DIAGNOSIS REPORT")
    print("="*80)
    print(f"{'Metric':<20} | {'Strategy':<15} | {'Benchmark (QQQ)':<15} | {'Diff'}")
    print("-" * 80)
    print(f"{'CAGR':<20} | {strat_metrics['CAGR']:.2%}           | {bench_metrics['CAGR']:.2%}           | {strat_metrics['CAGR']-bench_metrics['CAGR']:.2%}")
    print(f"{'Max Drawdown':<20} | {strat_dd:.2%}           | {bench_dd:.2%}           | {strat_dd-bench_dd:.2%}")
    print(f"{'Sharpe':<20} | {strat_metrics['Sharpe']:.4f}           | {bench_metrics['Sharpe']:.4f}           | {strat_metrics['Sharpe']-bench_metrics['Sharpe']:.4f}")
    print(f"{'Sortino':<20} | {strat_metrics['Sortino']:.4f}           | {bench_metrics['Sortino']:.4f}           | {strat_metrics['Sortino']-bench_metrics['Sortino']:.4f}")
    print(f"{'Volatility':<20} | {strat_metrics['Vol']:.2%}           | {bench_metrics['Vol']:.2%}           | {strat_metrics['Vol']-bench_metrics['Vol']:.2%}")
    
    # 4. Golden Decade (2015-2025)
    start_date = '2015-01-01'
    df_recent = df[df.index >= start_date]
    
    if not df_recent.empty:
        strat_recent_metrics = calculate_metrics(df_recent['Strategy_Ret'], df_recent['StrategyAssets'])
        bench_recent_metrics = calculate_metrics(df_recent['Benchmark_Ret'], df_recent['BenchmarkAssets'])
        strat_recent_dd, _ = calculate_max_drawdown(df_recent['StrategyAssets'])
        bench_recent_dd, _ = calculate_max_drawdown(df_recent['BenchmarkAssets'])
        
        print("\n" + "="*80)
        print(f"GOLDEN DECADE (2015-2025) REPORT")
        print("="*80)
        print(f"{'Metric':<20} | {'Strategy':<15} | {'Benchmark (QQQ)':<15} | {'Diff'}")
        print("-" * 80)
        print(f"{'Total Return':<20} | {strat_recent_metrics['TotalReturn']:.2%}           | {bench_recent_metrics['TotalReturn']:.2%}           | {strat_recent_metrics['TotalReturn']-bench_recent_metrics['TotalReturn']:.2%}")
        print(f"{'CAGR':<20} | {strat_recent_metrics['CAGR']:.2%}           | {bench_recent_metrics['CAGR']:.2%}           | {strat_recent_metrics['CAGR']-bench_recent_metrics['CAGR']:.2%}")
        print(f"{'Max Drawdown':<20} | {strat_recent_dd:.2%}           | {bench_recent_dd:.2%}           | {strat_recent_dd-bench_recent_dd:.2%}")
        print(f"{'Sharpe':<20} | {strat_recent_metrics['Sharpe']:.4f}           | {bench_recent_metrics['Sharpe']:.4f}           | {strat_recent_metrics['Sharpe']-bench_recent_metrics['Sharpe']:.4f}")
        print(f"{'Volatility':<20} | {strat_recent_metrics['Vol']:.2%}           | {bench_recent_metrics['Vol']:.2%}           | {strat_recent_metrics['Vol']-bench_recent_metrics['Vol']:.2%}")
        print("="*80)

def compare_versions(v22_dir, v23_dir):
    print(f"Comparing V22.1 (in {v22_dir}) vs V23.0 (in {v23_dir})")
    
    # Load V22
    v22_path = os.path.join(v22_dir, "tqqq_backtest_result.csv")
    df_v22 = pd.read_csv(v22_path, parse_dates=['date'], index_col='date')
    df_v22.rename(columns={'total_value': 'V22'}, inplace=True)
    
    # Load V23
    v23_path = os.path.join(v23_dir, "tqqq_backtest_result.csv")
    df_v23 = pd.read_csv(v23_path, parse_dates=['date'], index_col='date')
    df_v23.rename(columns={'total_value': 'V23'}, inplace=True)
    
    # Load QQQ (Benchmark)
    qqq_path = os.path.join(v23_dir, "qqq_backtest_result.csv")
    df_qqq = pd.read_csv(qqq_path, parse_dates=['date'], index_col='date')
    df_qqq.rename(columns={'total_value': 'QQQ'}, inplace=True)
    
    # Merge
    df = df_v23[['V23']].join(df_v22[['V22']], how='inner').join(df_qqq[['QQQ']], how='inner')
    
    # Calculate Returns
    df['V23_Ret'] = df['V23'].pct_change().fillna(0)
    df['V22_Ret'] = df['V22'].pct_change().fillna(0)
    df['QQQ_Ret'] = df['QQQ'].pct_change().fillna(0)
    
    # Helper to print row
    def print_row(name, m_v23, m_v22, m_qqq, is_percent=True, is_float=False):
        fmt = "{:.2%}" if is_percent else ("{:.4f}" if is_float else "{}")
        v23_val = fmt.format(m_v23)
        v22_val = fmt.format(m_v22)
        qqq_val = fmt.format(m_qqq)
        print(f"| **{name}** | **{v23_val}** | {v22_val} | {qqq_val} | - |")

    # Analyze Periods
    periods = {
        "全周期 (1999-2025)": df,
        "黄金十年 (2015-2025)": df[df.index >= '2015-01-01']
    }
    
    for name, data in periods.items():
        print(f"\n### {name}")
        print("| 指标 | **V23.0 旗舰版** | V22.1 修正版 | QQQ 基准 | 点评 |")
        print("| :--- | :--- | :--- | :--- | :--- |")
        
        # Metrics
        m_v23 = calculate_metrics(data['V23_Ret'], data['V23'])
        m_v22 = calculate_metrics(data['V22_Ret'], data['V22'])
        m_qqq = calculate_metrics(data['QQQ_Ret'], data['QQQ'])
        
        dd_v23, _ = calculate_max_drawdown(data['V23'])
        dd_v22, _ = calculate_max_drawdown(data['V22'])
        dd_qqq, _ = calculate_max_drawdown(data['QQQ'])
        
        if name.startswith("黄金"):
             print_row("总收益 (Total Return)", m_v23['TotalReturn'], m_v22['TotalReturn'], m_qqq['TotalReturn'])
        
        print_row("全周期年化 (CAGR)" if "全" in name else "年化收益 (CAGR)", m_v23['CAGR'], m_v22['CAGR'], m_qqq['CAGR'])
        print_row("最大回撤 (MDD)", dd_v23, dd_v22, dd_qqq)
        print_row("夏普比率 (Sharpe)", m_v23['Sharpe'], m_v22['Sharpe'], m_qqq['Sharpe'], is_percent=False, is_float=True)
        print_row("胜率 (Win Rate)" if "全" in name else "波动率 (Vol)", 
                  m_v23['WinRate'] if "全" in name else m_v23['Vol'], 
                  m_v22['WinRate'] if "全" in name else m_v22['Vol'], 
                  m_qqq['WinRate'] if "全" in name else m_qqq['Vol'],
                  is_percent=True)

if __name__ == "__main__":
    if len(sys.argv) == 3:
        compare_versions(sys.argv[1], sys.argv[2])
    else:
        run_diagnosis()

