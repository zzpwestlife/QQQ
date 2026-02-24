
import os
import sys
import logging
import pandas as pd

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from engine import run_backtest, run_benchmark
from metrics import calculate_metrics
from reporting import generate_report

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def main():
    # Paths
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__))) # Root QQQ/
    qqq_path = os.path.join(base_dir, "input", "QQQ.csv")
    tqqq_path = os.path.join(base_dir, "input", "TQQQ.csv")
    strategy_path = os.path.join(base_dir, "code", "tqqq_opt.py")
    output_dir = os.path.join(base_dir, "code", "backtest", "output_opt")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    if not os.path.exists(qqq_path) or not os.path.exists(tqqq_path):
        logging.error(f"Input files not found: {qqq_path}, {tqqq_path}")
        return
        
    # 1. Run Strategy Backtest
    logging.info("Running Strategy Backtest (V23.0)...")
    df_strategy = run_backtest(qqq_path, tqqq_path, strategy_path)
    df_strategy.to_csv(os.path.join(output_dir, "tqqq_backtest_result.csv"))
    
    # 2. Run Benchmark Backtest (Buy & Hold QQQ)
    logging.info("Running Benchmark Backtest (QQQ)...")
    df_qqq = pd.read_csv(qqq_path)
    df_qqq.columns = [c.lower() for c in df_qqq.columns]
    df_qqq['date'] = pd.to_datetime(df_qqq['date'])
    df_qqq.set_index('date', inplace=True)
    
    # Align with strategy dates
    common_dates = df_strategy.index.intersection(df_qqq.index)
    df_qqq = df_qqq.loc[common_dates].sort_index()
    
    df_benchmark = run_benchmark(df_qqq, initial_capital=100000.0)
    df_benchmark.to_csv(os.path.join(output_dir, "qqq_backtest_result.csv"))
    
    # 3. Metrics
    logging.info("Calculating Metrics...")
    metrics_strat = calculate_metrics(df_strategy)
    metrics_bench = calculate_metrics(df_benchmark)
    
    results = {
        "TQQQ Strategy (V23.0)": {
            "df": df_strategy,
            "metrics": metrics_strat
        },
        "QQQ Benchmark": {
            "df": df_benchmark,
            "metrics": metrics_bench
        }
    }
    
    # 4. Generate Report
    logging.info("Generating Report...")
    generate_report(results, output_dir)
    
    # 5. Summary Text
    logging.info("Generating Summary...")
    strat_ret = metrics_strat['Total Return']
    bench_ret = metrics_bench['Total Return']
    strat_dd = metrics_strat['Max Drawdown']
    bench_dd = metrics_bench['Max Drawdown']
    
    winner = "TQQQ策略" if strat_ret > bench_ret else "QQQ基准"
    summary = (
        f"回测区间内，{winner}表现更优。\n"
        f"TQQQ策略总收益 {strat_ret:.2%} (最大回撤 {strat_dd:.2%})，"
        f"QQQ基准总收益 {bench_ret:.2%} (最大回撤 {bench_dd:.2%})。\n"
        f"策略通过动态仓位调整，{'成功' if abs(strat_dd) < abs(bench_dd) else '未能'}降低最大回撤。"
    )
    
    with open(os.path.join(output_dir, "compare_summary.txt"), "w") as f:
        f.write(summary)
        
    print("\n" + "="*50)
    print(summary)
    print("="*50 + "\n")
    logging.info(f"Done. Results saved to {output_dir}")

if __name__ == "__main__":
    main()
