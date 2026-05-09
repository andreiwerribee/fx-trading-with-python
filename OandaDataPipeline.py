"""
OANDA Data Pipeline for GBP/JPY Trading Strategy
Fetches historical candle data from OANDA and enriches it with:
  - Technical indicators (SMA, Bollinger Bands)
  - Daily trend classification (uptrend, downtrend, ranging)
  - Hourly-daily data alignment
"""

import os
import sys
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
from typing import Optional
import traceback

try:
    from oandapyV20 import API
    from oandapyV20.endpoints.instruments import InstrumentsCandles
except ImportError:
    print("Error: oandapyV20 library not installed.")
    print("Install with: pip install oandapyV20")
    sys.exit(1)

# Import strategy from the same directory
try:
    from GBPJPY_SMA_Strategy import GBPJPY_SMA_Strategy
except ImportError:
    print("Warning: Could not import GBPJPY_SMA_Strategy. "
          "Make sure both files are in the same directory.")
    GBPJPY_SMA_Strategy = None


class OandaDataPipeline:
    """
    Fetches and enriches FX data from OANDA API.
    
    Attributes:
        api: OANDA API client
        instrument: Currency pair (e.g., "GBP_JPY")
        slippage: Commission/slippage percentage for backtesting
    """
    
    def __init__(self, access_token: str, instrument: str = "GBP_JPY", slippage: float = 0.0001):
        """
        Initialize the pipeline.
        
        Args:
            access_token: OANDA API access token
            instrument: Trading instrument (default: GBP_JPY)
            slippage: Commission/slippage as decimal (default: 0.01%)
        """
        if not access_token or not isinstance(access_token, str):
            raise ValueError("Invalid access_token provided")
        
        self.api = API(access_token=access_token)
        self.instrument = instrument
        self.slippage = slippage
        self.last_fetch_time = None

    def fetch_candles(self, granularity: str = "H1", count: int = 5000) -> pd.DataFrame:
        """
        Fetch candles from OANDA.
        
        Args:
            granularity: Candle size (M1, M5, M15, H1, H4, D, etc.)
            count: Number of candles to fetch (max 5000 per request)
        
        Returns:
            DataFrame with OHLCV data indexed by time
        
        Raises:
            Exception: If API request fails
        """
        if count > 5000:
            print(f"Warning: OANDA limits requests to 5000 candles. Fetching 5000 instead of {count}")
            count = 5000
        
        print(f"Fetching {count} {granularity} candles for {self.instrument}...")
        
        try:
            params = {"count": count, "granularity": granularity}
            r = InstrumentsCandles(instrument=self.instrument, params=params)
            response = self.api.request(r)
            
            if not response.get('candles'):
                raise ValueError("No candles returned from API")
            
            # Parse candle data
            data = []
            for c in response['candles']:
                data.append({
                    'time': pd.to_datetime(c['time']),
                    'open': float(c['mid']['o']),
                    'high': float(c['mid']['h']),
                    'low': float(c['mid']['l']),
                    'close': float(c['mid']['c']),
                    'volume': int(c['volume'])
                })
            
            df = pd.DataFrame(data)
            df.set_index('time', inplace=True)
            df.sort_index(inplace=True)
            
            self.last_fetch_time = datetime.now()
            print(f"✓ Fetched {len(df)} candles | Time range: {df.index[0]} to {df.index[-1]}")
            
            return df
        
        except Exception as e:
            print(f"Error fetching candles: {e}")
            raise

    def build_enriched_dataset(self, h1_count: int = 5000, d_count: int = 5000) -> pd.DataFrame:
        """
        Build a complete enriched dataset with indicators and trend labels.
        
        Args:
            h1_count: Number of hourly candles to fetch
            d_count: Number of daily candles to fetch
        
        Returns:
            DataFrame with hourly data enriched with indicators and daily trend
        """
        print("\n" + "="*60)
        print("Building Enriched Dataset for GBP/JPY")
        print("="*60)
        
        # Fetch data
        h1 = self.fetch_candles(granularity="H1", count=h1_count)
        daily = self.fetch_candles(granularity="D", count=d_count)
        
        if h1.empty or daily.empty:
            raise ValueError("Failed to fetch data from OANDA")
        
        # ================== Add Indicators to H1 ==================
        print("\nCalculating technical indicators...")
        
        h1['sma_7'] = ta.sma(h1['close'], length=7)
        h1['sma_20'] = ta.sma(h1['close'], length=20)
        h1['sma_50'] = ta.sma(h1['close'], length=50)
        
        # Bollinger Bands
        bb = ta.bbands(h1['close'], length=20, std=2)
        bb.rename(columns={
            'BBL_20_2.0_2.0': 'BBL_20_2.0',
            'BBM_20_2.0_2.0': 'BBM_20_2.0',
            'BBU_20_2.0_2.0': 'BBU_20_2.0',
            'BBB_20_2.0_2.0': 'BBB_20_2.0',
            'BBP_20_2.0_2.0': 'BBP_20_2.0'
            }, inplace=True)
        if bb is not None:
            h1['bb_lower'] = bb['BBL_20_2.0']
            h1['bb_middle'] = bb['BBM_20_2.0']
            h1['bb_upper'] = bb['BBU_20_2.0']
        
        # ================== Add Trend Labels to Daily ==================
        print("Classifying daily trend...")
        
        daily['hh'] = daily['high'] > daily['high'].shift(1)  # Higher High
        daily['hl'] = daily['low'] > daily['low'].shift(1)    # Higher Low
        daily['lh'] = daily['high'] < daily['high'].shift(1)  # Lower High
        daily['ll'] = daily['low'] < daily['low'].shift(1)    # Lower Low
        
        def trend_label(row):
            """Classify trend based on higher highs/lows and lower highs/lows."""
            if row['hh'] and row['hl']:
                return 'uptrend'
            elif row['lh'] and row['ll']:
                return 'downtrend'
            else:
                return 'ranging'
        
        daily['daily_trend'] = daily.apply(trend_label, axis=1)
        
        # ================== Merge Daily Trend to Hourly ==================
        print("Aligning daily trend with hourly bars...")

        # Merge on the date (not time) to align all hourly bars with their daily trend
        h1['date'] = h1.index.date
        daily['date'] = daily.index.date
        
        h1 = h1.merge(daily[['daily_trend', 'date']], left_on='date', right_on='date', how='left')
        h1.drop('date', axis=1, inplace=True)
        h1.set_index(h1.index, inplace=True)
        
        # Forward fill any NaN values
        h1['daily_trend'] = h1['daily_trend'].ffill()
        
        # Drop rows with NaN (usually from indicator calculation at the start)
        h1_clean = h1.dropna(subset=['sma_7', 'sma_20', 'daily_trend'])
        
        print(f"\n✓ Dataset ready: {len(h1_clean)} hourly bars")
        print(f"  Time range: {h1_clean.index[0]} to {h1_clean.index[-1]}")
        print(f"  Columns: {list(h1_clean.columns)}")
        print("="*60 + "\n")
        
        return h1_clean

    def get_data_summary(self, df: pd.DataFrame) -> None:
        """Print a summary of the dataset."""
        if df.empty:
            print("Dataset is empty")
            return
        
        print("\n--- Dataset Summary ---")
        print(f"Total bars: {len(df)}")
        print(f"Date range: {df.index[0]} to {df.index[-1]}")
        print(f"Price range: {df['close'].min():.4f} - {df['close'].max():.4f}")
        print(f"Average volume: {df['volume'].mean():.0f}")
        print(f"Columns: {list(df.columns)}")
        
        trend_counts = df['daily_trend'].value_counts()
        print(f"Trend distribution: {dict(trend_counts)}")


# ====================== CONFIGURATION ======================
# Create a config.py file with your OANDA credentials to avoid hardcoding
def load_api_token(from_file: bool = True) -> str:
    """
    Load OANDA API token from environment variable or file.
    
    Priority:
    1. Environment variable: OANDA_ACCESS_TOKEN
    2. File: .oanda_token (in same directory, git-ignored)
    
    Args:
        from_file: If True, try to load from .oanda_token file
    
    Returns:
        API token string
    
    Raises:
        ValueError: If no token found
    """
    # Check environment variable
    token = os.getenv('OANDA_ACCESS_TOKEN')
    if token:
        return token
    
    # Check local file
    if from_file:
        token_file = os.path.join(os.path.dirname(__file__), '.oanda_token')
        if os.path.exists(token_file):
            with open(token_file, 'r') as f:
                token = f.read().strip()
                if token:
                    return token
    
    raise ValueError(
        "OANDA API token not found. "
        "Set environment variable OANDA_ACCESS_TOKEN or create .oanda_token file"
    )


# ====================== USAGE EXAMPLE ======================
if __name__ == "__main__":
    try:
        # Load token securely
        ACCESS_TOKEN = load_api_token()
        
        # Create pipeline
        pipeline = OandaDataPipeline(ACCESS_TOKEN, instrument="GBP_JPY")
        
        # Build enriched dataset
        data = pipeline.build_enriched_dataset(h1_count=5000, d_count=5000//24)
        
        # Print summary
        pipeline.get_data_summary(data)
        
        # Run backtest (if strategy is available)
        if GBPJPY_SMA_Strategy:
            try:
                from backtesting import Backtest
                
                print("\nRunning backtest...")
                bt = Backtest(data, GBPJPY_SMA_Strategy, 
                              cash=1_000_000, 
                              commission=pipeline.slippage)
                
                stats = bt.run()
                print("\n--- Backtest Results ---")
                print(stats)
                
                # Uncomment to plot (requires matplotlib)
                # bt.plot()
                
            except ImportError:
                print("Error: backtesting library not installed.")
                print("Install with: pip install backtesting")
        else:
            print("Backtest skipped: Strategy not imported")
    
    except ValueError as e:
        print(f"Configuration Error: {e}")
        print("\nSetup Instructions:")
        print("1. Create a .oanda_token file in this directory with your API token")
        print("   OR set environment variable: export OANDA_ACCESS_TOKEN='your_token'")
        print("2. Install dependencies: pip install oandapyV20 pandas pandas_ta backtesting")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
