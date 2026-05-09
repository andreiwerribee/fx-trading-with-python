"""
GBP/JPY SMA-based Trading Strategy
Implements a trend-following strategy with:
  - Dynamic position sizing based on loss streak
  - Adaptive take-profit based on consecutive losses
  - Daily trend filtering (uptrend, downtrend, ranging)
  - Mean reversion in ranging markets
"""

from backtesting import Backtest, Strategy


class GBPJPY_SMA_Strategy(Strategy):
    """
    Trend-following SMA strategy with loss-streak-based position sizing.
    
    Parameters:
      base_tp_percent: Starting take-profit percentage (increases per loss)
      sl_percent: Fixed stop-loss percentage
      max_streak_limit: Maximum consecutive losses before stopping trades
    """
    
    # ================== Strategy Parameters ==================
    base_tp_percent   = 0.25      # Starting TP, increases by 0.25% per loss
    sl_percent        = 0.50      # Fixed Stop Loss
    max_streak_limit  = 7         # ← Locked as per your preference
    
    # ================== Internal State ==================
    trade_counter          = 0
    consecutive_losses     = 0
    max_consecutive_losses = 0

    def init(self):
        """Initialize technical indicators from enriched dataset."""
        # These columns should come from OandaDataPipeline
        if not hasattr(self.data, 'sma_7') or not hasattr(self.data, 'daily_trend'):
            raise ValueError(
                "Required columns not found in data: 'sma_7', 'sma_20', 'daily_trend'. "
                "Ensure OandaDataPipeline.build_enriched_dataset() was used."
            )
        
        self.sma_fast = self.I(lambda x=self.data.sma_7: x)
        self.sma_slow = self.I(lambda x=self.data.sma_20: x)
        self.daily_trend = self.data.daily_trend

    def next(self):
        """Execute trading logic on each bar."""
        # Safety: Stop increasing size after max streak
        if self.consecutive_losses >= self.max_streak_limit:
            return
        
        # Skip if we already have an open position
        if self.position:
            return

        price = self.data.close[-1]
        trend = self.daily_trend[-1] if len(self.daily_trend) > 0 else 'ranging'
        
        size = self.consecutive_losses + 1
        current_tp = self.base_tp_percent * size

        # ================== ENTRY LOGIC ==================
        if trend == 'uptrend':
            if price > self.sma_fast[-1] and self.sma_fast[-1] > self.sma_slow[-1]:
                self.buy(size=size,
                         sl=price * (1 - self.sl_percent/100),
                         tp=price * (1 + current_tp/100))
                self._on_trade_entry(size, current_tp)

        elif trend == 'downtrend':
            if price < self.sma_fast[-1] and self.sma_fast[-1] < self.sma_slow[-1]:
                self.sell(size=size,
                          sl=price * (1 + self.sl_percent/100),
                          tp=price * (1 - current_tp/100))
                self._on_trade_entry(size, current_tp)

        elif trend == 'ranging':
            if price < self.sma_fast[-1]:           # Mean reversion - Long
                self.buy(size=size,
                         sl=price * (1 - self.sl_percent/100),
                         tp=price * (1 + current_tp/100))
                self._on_trade_entry(size, current_tp)
            elif price > self.sma_fast[-1]:         # Mean reversion - Short
                self.sell(size=size,
                          sl=price * (1 + self.sl_percent/100),
                          tp=price * (1 - current_tp/100))
                self._on_trade_entry(size, current_tp)

        self._check_last_trade_result()

    def _on_trade_entry(self, size, tp_percent):
        """Log trade entry information."""
        self.trade_counter += 1
        print(f"→ Trade #{self.trade_counter:3d} | Size: {size} | TP: {tp_percent:4.2f}% | "
              f"Streak: {self.consecutive_losses}")

    def _check_last_trade_result(self):
        """Check if the last trade closed and update streak counter."""
        if len(self.trades) == 0:
            return
            
        last_trade = self.trades[-1]
        # Trade closed on this bar (exit_bar is the current bar index)
        if last_trade.exit_bar == len(self.data) - 1:
            if last_trade.pl > 0:                        # WIN
                print(f"✅ WIN  | Trade #{self.trade_counter} | Profit: {last_trade.pl:+7.3f}% | Reset")
                self.consecutive_losses = 0
            else:                                        # LOSS
                self.consecutive_losses += 1
                if self.consecutive_losses > self.max_consecutive_losses:
                    self.max_consecutive_losses = self.consecutive_losses
                print(f"❌ LOSS | Trade #{self.trade_counter} | Loss: {last_trade.pl:+7.3f}% | "
                      f"Streak: {self.consecutive_losses}/{self.max_streak_limit}")

    def stats(self):
        """Return custom statistics dictionary."""
        trades = self.trades
        if not trades:
            return {
                "Total Trades": 0,
                "Max Consecutive Losses": 0,
                "Win Rate %": 0,
                "Final Equity": round(self.equity, 2),
                "Return %": 0,
            }
        
        win_rate = len([t for t in trades if t.pl > 0]) / len(trades) * 100
        return {
            "Total Trades": self.trade_counter,
            "Max Consecutive Losses": self.max_consecutive_losses,
            "Win Rate %": round(win_rate, 2),
            "Final Equity": round(self.equity, 2),
            "Return %": round((self.equity - 1000000) / 10000, 2),
        }
