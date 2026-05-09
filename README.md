# GBP/JPY SMA Trading Strategy - Setup & Usage Guide

## Overview
This is a trend-following SMA-based strategy with:
- **Dynamic position sizing** based on consecutive loss streaks
- **Adaptive take-profit** (increases with each loss)
- **Daily trend filtering** (uptrend, downtrend, ranging)
- **Mean reversion** logic in ranging markets
- **Backtesting framework** using the backtesting.py library

---

## Files Included
- **GBPJPY_SMA_Strategy.py** - Trading strategy class
- **OandaDataPipeline.py** - OANDA API wrapper and data enrichment
- **requirements.txt** - Python dependencies
- **README.md** - This file

---

## Installation

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install oandapyV20 pandas pandas_ta backtesting matplotlib
```

### 2. Get OANDA API Credentials
1. Sign up for a free demo account at [oanda.com](https://www.oanda.com)
2. Generate an API token in your account settings
3. Keep your token secure (never commit to git!)

### 3. Set Up Your API Token

#### Option A: Environment Variable (Recommended)
```bash
export OANDA_ACCESS_TOKEN="your_token_here"
```

Or on Windows:
```cmd
set OANDA_ACCESS_TOKEN=your_token_here
```

#### Option B: Token File (Git-Ignored)
Create a `.oanda_token` file in the same directory as the scripts:
```
your_token_here
```

Then add to `.gitignore`:
```
.oanda_token
```

---

## Usage

### Basic Backtest
```python
from OandaDataPipeline import OandaDataPipeline
from GBPJPY_SMA_Strategy import GBPJPY_SMA_Strategy
from backtesting import Backtest

# Fetch and enrich data
pipeline = OandaDataPipeline(access_token="your_token")
data = pipeline.build_enriched_dataset(h1_count=5000, d_count=5000)

# Run backtest
bt = Backtest(data, GBPJPY_SMA_Strategy, cash=1_000_000, commission=0.0001)
stats = bt.run()
print(stats)
```

### Generate Plot
```python
# After running backtest
bt.plot()  # Opens matplotlib window
```

### Adjust Strategy Parameters
Modify class variables in `GBPJPY_SMA_Strategy`:
```python
class GBPJPY_SMA_Strategy(Strategy):
    base_tp_percent   = 0.25      # Starting TP (%)
    sl_percent        = 0.50      # Stop loss (%)
    max_streak_limit  = 7         # Max consecutive losses
```

---

## Strategy Logic

### Entry Conditions

#### Uptrend
- Daily trend: **uptrend**
- Condition: `price > SMA(7)` AND `SMA(7) > SMA(20)`
- Action: **BUY**

#### Downtrend
- Daily trend: **downtrend**
- Condition: `price < SMA(7)` AND `SMA(7) < SMA(20)`
- Action: **SELL**

#### Ranging Market (Mean Reversion)
- Daily trend: **ranging**
- If `price < SMA(7)`: **BUY**
- If `price > SMA(7)`: **SELL**

### Position Sizing
- Base size = 1 + consecutive_losses
- Example:
  - No losses: size = 1
  - 1 loss: size = 2
  - 2 losses: size = 3
  - Capped at max_streak_limit (7)

### Stop Loss & Take Profit
- **SL**: Fixed at 0.50% from entry
- **TP**: Increases with loss streak
  - 1st trade: 0.25%
  - 2nd trade (after loss): 0.50%
  - 3rd trade (2 losses): 0.75%
  - etc.

---

## Data Pipeline Details

### Indicators Calculated
- **SMA(7)** - Fast moving average
- **SMA(20)** - Slow moving average
- **SMA(50)** - Trend confirmation
- **Bollinger Bands(20, 2σ)** - Volatility bands

### Daily Trend Classification
Based on Higher Highs/Lows (HH/HL) and Lower Highs/Lows (LH/LL):

| Condition | Trend |
|-----------|-------|
| HH + HL | uptrend |
| LH + LL | downtrend |
| Other | ranging |

### Data Merge
- Hourly bars enriched with daily trend
- Trend forward-filled throughout the day
- All NaN values removed before backtesting

---

## Backtest Output

The backtest returns:
- **Total Trades** - Number of executed trades
- **Max Consecutive Losses** - Longest loss streak
- **Win Rate %** - Percentage of profitable trades
- **Final Equity** - Ending account balance
- **Return %** - Percentage gain/loss

Example output:
```
Total Trades: 456
Max Consecutive Losses: 5
Win Rate %: 52.15
Final Equity: 1,125,430.50
Return %: 12.54
```

---

## Troubleshooting

### "No module named 'oandapyV20'"
```bash
pip install oandapyV20
```

### "OANDA API token not found"
Ensure either:
- Environment variable is set: `echo $OANDA_ACCESS_TOKEN`
- `.oanda_token` file exists in the script directory

### "Required columns not found"
Make sure you're using data from `OandaDataPipeline.build_enriched_dataset()`, not raw OANDA data.

### Connection timeout
- Check internet connection
- Verify OANDA API is online
- Try reducing `count` parameter in `fetch_candles()`

### Empty dataset after cleanup
- Increase `count` to fetch more bars
- Verify data is returned from OANDA API
- Check for NaN values: `df.info()`

---

## Optimization Tips

### Adjust for Different Instruments
```python
pipeline = OandaDataPipeline(access_token, instrument="EUR_USD")
```

### Backtest with Different Parameters
```python
# Grid search
for base_tp in [0.20, 0.25, 0.30]:
    class TempStrategy(GBPJPY_SMA_Strategy):
        base_tp_percent = base_tp
    bt = Backtest(data, TempStrategy, cash=1_000_000)
    print(bt.run())
```

### Use Walk-Forward Analysis
```python
# Test on different time periods
train_data = data[:'2023-01-01']
test_data = data['2023-01-01':]

bt_train = Backtest(train_data, GBPJPY_SMA_Strategy, cash=1_000_000)
bt_test = Backtest(test_data, GBPJPY_SMA_Strategy, cash=1_000_000)
```

---

## Important Disclaimers

⚠️ **Backtesting Limitations:**
- Past performance ≠ future results
- Assumes instant fills at bid/ask (slippage not fully modeled)
- Does not account for gaps or market hours
- Commission set to 0.01% (adjust for your broker)

⚠️ **Live Trading:**
- Test strategy on OANDA demo account first
- Implement position size limits
- Use proper risk management
- Monitor for black swan events

---

## Advanced Usage

### Custom Indicators
Add to `OandaDataPipeline.build_enriched_dataset()`:
```python
# RSI
h1['rsi'] = ta.rsi(h1['close'], length=14)

# MACD
macd = ta.macd(h1['close'])
h1['macd'] = macd['MACD_12_26_9']
```

### Save Dataset to CSV
```python
data.to_csv('gbpjpy_enriched.csv')

# Load later
data = pd.read_csv('gbpjpy_enriched.csv', index_col='time', parse_dates=True)
```

### Multi-instrument Backtesting
```python
for instrument in ["EUR_USD", "GBP_JPY", "USD_JPY"]:
    pipeline = OandaDataPipeline(token, instrument=instrument)
    data = pipeline.build_enriched_dataset()
    bt = Backtest(data, GBPJPY_SMA_Strategy, cash=1_000_000)
    print(f"{instrument}: {bt.run()}")
```

---

## Support & References

- **backtesting.py**: https://kernc.github.io/backtesting.py/
- **pandas_ta**: https://github.com/twopirllc/pandas-ta
- **OANDA API**: https://developer.oanda.com/
- **pandas Documentation**: https://pandas.pydata.org/

---

## Version History

**v1.1 (Enhanced)**
- ✅ Added comprehensive error handling
- ✅ Secure API token loading (environment/file)
- ✅ Detailed inline documentation
- ✅ Type hints for better IDE support
- ✅ Dataset summary function
- ✅ Improved data validation

**v1.0 (Original)**
- Initial release

---

## License
Use freely for backtesting and educational purposes.
Always test on a demo account before live trading.
