
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

def generate_report(results, output_dir="output"):
    """
    Generate HTML and Chart for backtest results.
    results: dict of {
        'Strategy Name': {
            'df': DataFrame (date, total_value),
            'metrics': dict
        }
    }
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # 1. Compare Metrics Table
    metrics_list = []
    for name, data in results.items():
        metrics = data['metrics']
        metrics['Strategy'] = name
        metrics_list.append(metrics)
        
    df_metrics = pd.DataFrame(metrics_list)
    df_metrics.set_index('Strategy', inplace=True)
    
    # Format for display
    df_display = df_metrics.copy()
    for col in df_display.columns:
        if 'Return' in col or 'CAGR' in col or 'Volatility' in col or 'Drawdown' in col:
            df_display[col] = df_display[col].apply(lambda x: f"{x:.2%}")
        else:
            df_display[col] = df_display[col].apply(lambda x: f"{x:.4f}")
            
    # Save CSV
    df_metrics.to_csv(os.path.join(output_dir, "backtest_metrics.csv"))
    
    # Save HTML
    html_content = f"""
    <html>
    <head>
        <title>Backtest Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: right; }}
            th {{ background-color: #f2f2f2; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            h1 {{ color: #333; }}
        </style>
    </head>
    <body>
        <h1>Backtest Performance Comparison</h1>
        {df_display.to_html()}
        <br>
        <img src="compare_chart.png" alt="Performance Chart" style="width:100%; max-width:1000px;">
    </body>
    </html>
    """
    
    with open(os.path.join(output_dir, "compare_report.html"), "w") as f:
        f.write(html_content)
        
    # 2. Charts
    plt.figure(figsize=(12, 8))
    
    # Subplot 1: Equity Curve (Log Scale usually better for long term, but linear requested)
    ax1 = plt.subplot(2, 1, 1)
    for name, data in results.items():
        df = data['df']
        # Normalize to 1.0 start
        normalized = df['total_value'] / df['total_value'].iloc[0]
        ax1.plot(df.index, normalized, label=name)
        
    ax1.set_title("Equity Curve (Normalized)")
    ax1.set_ylabel("Growth Factor")
    ax1.legend()
    ax1.grid(True)
    
    # Subplot 2: Relative Strength (Strategy / Benchmark)
    # Assuming first key is Strategy, second is Benchmark (QQQ)
    keys = list(results.keys())
    if len(keys) >= 2:
        strategy_name = keys[0] # TQQQ Strategy
        benchmark_name = keys[1] # QQQ Benchmark
        
        df_strat = results[strategy_name]['df']
        df_bench = results[benchmark_name]['df']
        
        # Align dates
        common = df_strat.index.intersection(df_bench.index)
        s = df_strat.loc[common, 'total_value']
        b = df_bench.loc[common, 'total_value']
        
        rel_strength = s / b
        
        ax2 = plt.subplot(2, 1, 2, sharex=ax1)
        ax2.plot(common, rel_strength, color='orange', label=f'{strategy_name} / {benchmark_name}')
        ax2.set_title("Relative Strength")
        ax2.set_ylabel("Ratio")
        ax2.legend()
        ax2.grid(True)
        
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "compare_chart.png"))
    plt.close()
