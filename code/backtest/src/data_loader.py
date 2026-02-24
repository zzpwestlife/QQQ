
import pandas as pd
import numpy as np

def load_and_clean_data(qqq_path, tqqq_path):
    """
    Load QQQ and TQQQ data, align timestamps, and clean up.
    """
    # Load QQQ
    df_qqq = pd.read_csv(qqq_path)
    df_qqq.columns = [c.lower() for c in df_qqq.columns]
    df_qqq['date'] = pd.to_datetime(df_qqq['date'])
    df_qqq.set_index('date', inplace=True)
    
    # Load TQQQ
    df_tqqq = pd.read_csv(tqqq_path)
    df_tqqq.columns = [c.lower() for c in df_tqqq.columns]
    df_tqqq['date'] = pd.to_datetime(df_tqqq['date'])
    df_tqqq.set_index('date', inplace=True)
    
    # Align dates (intersection)
    common_dates = df_qqq.index.intersection(df_tqqq.index)
    df_qqq = df_qqq.loc[common_dates].sort_index()
    df_tqqq = df_tqqq.loc[common_dates].sort_index()
    
    # Fill missing columns for backtest (High, Low, Volume)
    # Using Open/Close approximations if missing
    for df in [df_qqq, df_tqqq]:
        if 'high' not in df.columns:
            df['high'] = df[['open', 'close']].max(axis=1)
        if 'low' not in df.columns:
            df['low'] = df[['open', 'close']].min(axis=1)
        if 'volume' not in df.columns:
            df['volume'] = 0.0  # Default to 0, will disable volume-based signals
            
    return df_qqq, df_tqqq
