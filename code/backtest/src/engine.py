
import pandas as pd
import numpy as np
import logging
import importlib.util
import sys
import os
from mock_api import *
from data_loader import load_and_clean_data

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_backtest(qqq_path, tqqq_path, strategy_path):
    logging.info("Loading data...")
    df_qqq, df_tqqq = load_and_clean_data(qqq_path, tqqq_path)
    
    # Define time range (intersection of both)
    dates = df_qqq.index
    logging.info(f"Backtest range: {dates[0]} to {dates[-1]}")
    
    # Initialize Context
    ctx = MockContext(df_qqq, df_tqqq)
    set_context(ctx)
    
    # Dynamically load strategy from file
    logging.info(f"Loading strategy from {strategy_path}...")
    spec = importlib.util.spec_from_file_location("StrategyModule", strategy_path)
    module = importlib.util.module_from_spec(spec)
    
    # Inject mock API into module namespace
    # This is tricky because the module expects `from extensions import *` etc.
    # We can inject into sys.modules or monkeypatch.
    # A cleaner way: Read the file content and exec it in a custom globals dict that has our mocks.
    
    with open(strategy_path, 'r') as f:
        code = f.read()
    
    # Prepare global namespace with our mock functions
    mock_globals = {
        'StrategyBase': StrategyBase,
        'AlgoStrategyType': AlgoStrategyType,
        'BarType': BarType,
        'DataType': DataType,
        'OrderSide': OrderSide,
        'OrderStatus': OrderStatus,
        'OrdType': OrdType,
        'TimeInForce': TimeInForce,
        'THType': THType,
        'TSType': TSType,
        'Currency': Currency,
        'TimeZone': TimeZone,
        'Contract': Contract,
        'declare_strategy_type': declare_strategy_type,
        'declare_trig_symbol': declare_trig_symbol,
        'alert': alert,
        'bar_close': bar_close,
        'bar_open': bar_open,
        'bar_high': bar_high,
        'bar_volume': bar_volume,
        'ma': ma,
        'rsi': rsi,
        'vol': vol,
        'request_orderid': request_orderid,
        'order_status': order_status,
        'position_holding_qty': position_holding_qty,
        'available_qty': available_qty,
        'position_market_cap': position_market_cap,
        'net_asset': net_asset,
        'place_market': place_market,
        'max_qty_to_buy_on_cash': max_qty_to_buy_on_cash,
        # Helper for print
        'print': logging.info
    }
    
    # Execute strategy definition
    try:
        exec(code, mock_globals)
    except Exception as e:
        logging.error(f"Failed to load strategy code: {e}")
        raise e
        
    StrategyClass = mock_globals.get('Strategy')
    if not StrategyClass:
        raise ValueError("Class 'Strategy' not found in strategy file.")
    
    strategy = StrategyClass()
    
    # Initialize
    logging.info("Initializing strategy...")
    strategy.initialize()
    
    # Run Loop
    logging.info("Starting simulation loop...")
    for current_date in dates:
        ctx.current_date = current_date
        
        # Check if data exists for today
        if current_date not in df_qqq.index or current_date not in df_tqqq.index:
            continue
            
        # Run handle_data
        try:
            strategy.handle_data()
        except Exception as e:
            logging.error(f"Error on {current_date}: {e}")
            
        # Update portfolio value for the day (mark-to-market)
        # Note: positions updated inside place_market (instant fill assumption)
        # We calculate EOD value
        val_qqq = ctx.positions["US.QQQ"] * df_qqq.loc[current_date, 'close']
        val_tqqq = ctx.positions["US.TQQQ"] * df_tqqq.loc[current_date, 'close']
        total_value = ctx.cash + val_qqq + val_tqqq
        
        ctx.portfolio_history.append({
            'date': current_date,
            'total_value': total_value,
            'cash': ctx.cash,
            'qqq_val': val_qqq,
            'tqqq_val': val_tqqq,
            'qqq_qty': ctx.positions["US.QQQ"],
            'tqqq_qty': ctx.positions["US.TQQQ"]
        })
        
    # Convert history to DataFrame
    df_results = pd.DataFrame(ctx.portfolio_history)
    df_results.set_index('date', inplace=True)
    return df_results

def run_benchmark(df, initial_capital=100000.0):
    """
    Simple Buy & Hold Benchmark
    """
    start_price = df['close'].iloc[0]
    shares = initial_capital // start_price
    cash = initial_capital - (shares * start_price)
    
    df_bm = pd.DataFrame(index=df.index)
    df_bm['total_value'] = (df['close'] * shares) + cash
    return df_bm
