
from enum import Enum, auto

class Strategy(StrategyBase):
    def initialize(self):
        declare_strategy_type(AlgoStrategyType.SECURITY)
        self.trigger_symbols()
        self.global_variables()
        print("[INIT] 策略 V23.0 旗舰优化版 (VolTarget + RSI + StrictBear)")
        alert(title="策略启动", content="V23.0 优化版已启动")

    def trigger_symbols(self):
        # We need QQQ for signals
        pass

    def global_variables(self):
        self.contract_QQQ = Contract("US.QQQ")
        self.contract_TQQQ = Contract("US.TQQQ")
        
        # Parameters
        self.ma_long = 200
        self.ma_short = 20
        self.rsi_period = 14
        self.vol_period = 20
        self.target_vol = 0.30  # Target 30% annualized volatility
        
        self.days_since_rebal = 0
        self.rebal_interval = 1 # Daily rebalance (or check daily)

    def handle_data(self):
        # 1. Get Data
        price_qqq = bar_close(self.contract_QQQ, BarType.D1, 1, THType.RTH)
        if not price_qqq:
            return

        # 2. Indicators
        ma200 = ma(self.contract_QQQ, self.ma_long, BarType.D1, DataType.CLOSE, 1, THType.RTH)
        ma20 = ma(self.contract_QQQ, self.ma_short, BarType.D1, DataType.CLOSE, 1, THType.RTH)
        current_rsi = rsi(self.contract_QQQ, self.rsi_period, BarType.D1, DataType.CLOSE, 1, THType.RTH)
        current_vol = vol(self.contract_QQQ, self.vol_period, 1)

        if not ma200 or not ma20:
            return

        # 3. Logic
        target_leverage = 0.0
        mode = "INIT"
        
        # Regime Detection
        if price_qqq < ma200:
            # Bear Market
            if price_qqq > ma20:
                # Bear Rally - 100% QQQ (1x), NO TQQQ
                target_leverage = 1.0
                mode = "BEAR_RALLY"
            else:
                # Deep Bear - Cash (0x)
                target_leverage = 0.0
                mode = "BEAR_CASH"
        else:
            # Bull Market
            mode = "BULL"
            base_leverage = 2.0 # Default 2x (50/50)
            
            # Volatility Control
            vol_scalar = 1.0
            if current_vol > 0:
                vol_scalar = self.target_vol / current_vol
                # Cap scalar to avoid extreme leverage in low vol
                vol_scalar = min(1.5, max(0.5, vol_scalar))
            
            # RSI Filter
            rsi_scalar = 1.0
            if current_rsi > 75:
                rsi_scalar = 0.7 # Reduce risk at overbought
                mode += "_OVERBOUGHT"
            elif current_rsi < 30:
                rsi_scalar = 1.2 # Buy the dip
                mode += "_OVERSOLD"
                
            target_leverage = base_leverage * vol_scalar * rsi_scalar
            
            # Cap Leverage at 3.0 (Max TQQQ) and Min 0.0
            target_leverage = min(3.0, max(0.0, target_leverage))

        # 4. Allocation Calculation
        # Lev = 3*w_t + 1*w_q + 0*w_c
        # Constraints: w_t + w_q + w_c = 1, w_i >= 0
        
        w_t = 0.0
        w_q = 0.0
        w_c = 0.0
        
        if target_leverage >= 1.0:
            # Mix of TQQQ and QQQ
            # L = 3*wt + 1*(1-wt) = 2*wt + 1
            # wt = (L - 1) / 2
            w_t = (target_leverage - 1) / 2
            # Cap wt at 1.0
            if w_t > 1.0: w_t = 1.0
            w_q = 1.0 - w_t
        else:
            # Mix of QQQ and Cash
            # L = 1*wq
            w_q = target_leverage
            w_c = 1.0 - w_q
            
        # 5. Execution (Simple Rebalance)
        # Check current holdings to avoid churning
        # For simulation, we just set target weights effectively
        # The engine mock uses 'place_market' to adjust qty.
        # We need to calculate target qty.
        
        # Get Net Asset Value
        nav = net_asset(Currency.USD)
        
        target_val_t = nav * w_t
        target_val_q = nav * w_q
        
        # Calculate Qty
        price_tqqq = bar_close(self.contract_TQQQ, BarType.D1, 1, THType.RTH)
        if not price_tqqq: price_tqqq = price_qqq # Should not happen if data aligned
        
        current_qty_t = position_holding_qty(self.contract_TQQQ)
        current_qty_q = position_holding_qty(self.contract_QQQ)
        
        target_qty_t = int(target_val_t / price_tqqq) if price_tqqq > 0 else 0
        target_qty_q = int(target_val_q / price_qqq) if price_qqq > 0 else 0
        
        # Execute TQQQ
        diff_t = target_qty_t - current_qty_t
        if diff_t != 0:
            side = OrderSide.BUY if diff_t > 0 else OrderSide.SELL
            place_market(self.contract_TQQQ, abs(diff_t), side, TimeInForce.DAY)
            
        # Execute QQQ
        diff_q = target_qty_q - current_qty_q
        if diff_q != 0:
            side = OrderSide.BUY if diff_q > 0 else OrderSide.SELL
            place_market(self.contract_QQQ, abs(diff_q), side, TimeInForce.DAY)
            
        # Logging (Optional, avoid spam)
        # print(f"Date: {ctx.current_date} | Mode: {mode} | Lev: {target_leverage:.2f} | Vol: {current_vol:.1%} | RSI: {current_rsi:.1f}")

