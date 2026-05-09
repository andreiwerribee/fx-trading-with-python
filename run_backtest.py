"""
Quick-Start Example: GBP/JPY SMA Strategy Backtest
Run this script after setting up your OANDA API token.
"""

import sys
import os

# Add current directory to path to import strategy
sys.path.insert(0, os.path.dirname(__file__))

from OandaDataPipeline import OandaDataPipeline, load_api_token
from GBPJPY_SMA_Strategy import GBPJPY_SMA_Strategy

try:
    from backtesting import Backtest
except ImportError:
    print("Error: backtesting not installed. Run: pip install backtesting")
    sys.exit(1)


def main():
    """Main execution function."""
    
    print("\n" + "="*70)
    print("GBP/JPY SMA Trading Strategy - Quick Start Backtest")
    print("="*70 + "\n")
    
    # Step 1: Load API Token
    print("Step 1: Loading OANDA API Token...")
    try:
        access_token = load_api_token()
        print("✓ Token loaded successfully\n")
    except ValueError as e:
        print(f"✗ Error: {e}\n")
        return False
    
    # Step 2: Create Pipeline
    print("Step 2: Initializing Data Pipeline...")
    try:
        pipeline = OandaDataPipeline(
            access_token=access_token,
            instrument="GBP_JPY",
            slippage=0.0001  # 0.01% commission
        )
        print("✓ Pipeline initialized\n")
    except Exception as e:
        print(f"✗ Error: {e}\n")
        return False
    
    # Step 3: Fetch and Enrich Data
    print("Step 3: Fetching and enriching market data...")
    print("(This may take a minute...)\n")
    try:
        data = pipeline.build_enriched_dataset(
            h1_count=5000,   # hourly bars
            d_count=5000//24 # daily bars
        )
        print("✓ Data ready for backtesting\n")
    except Exception as e:
        print(f"✗ Error fetching data: {e}\n")
        print("Tips:")
        print("- Check your internet connection")
        print("- Verify OANDA API is online")
        print("- Try reducing count parameter")
        return False
    
    # Step 4: Print Data Summary
    print("Step 4: Dataset Summary")
    print("-" * 70)
    pipeline.get_data_summary(data)
    print()
    
    # Step 5: Run Backtest
    print("Step 5: Running Backtest...")
    print("-" * 70 + "\n")
    try:
        data['Open'] = data['open']
        data['High'] = data['high']
        data['Low'] = data['low']
        data['Close'] = data['close']
        bt = Backtest(
            data,
            GBPJPY_SMA_Strategy,
            cash=1_000_000,        # $1M initial capital
            commission=pipeline.slippage,
            finalize_trades=True
        )
        stats = bt.run()
        print("✓ Backtest completed\n")
    except Exception as e:
        print(f"✗ Error running backtest: {e}\n")
        return False
    
    # Step 6: Display Results
    print("Step 6: Backtest Results")
    print("="*70)
    
    # Custom stats
    custom_stats = stats._strategy.stats()
    print("\n📊 Strategy Performance:")
    print(f"   Total Trades:          {custom_stats['Total Trades']}")
    print(f"   Winning Trades:        {int(custom_stats['Total Trades'] * custom_stats['Win Rate %'] / 100)}")
    print(f"   Losing Trades:         {int(custom_stats['Total Trades'] * (100 - custom_stats['Win Rate %']) / 100)}")
    print(f"   Win Rate:              {custom_stats['Win Rate %']:.2f}%")
    print(f"   Max Consecutive Losses: {custom_stats['Max Consecutive Losses']}")
    
    print("\n💰 Financial Results:")
    print(f"   Initial Capital:       ${1_000_000:,.2f}")
    print(f"   Final Equity:          ${custom_stats['Final Equity']:,.2f}")
    print(f"   Return:                {custom_stats['Return %']:.2f}%")
    
    # Additional stats from backtesting lib
    print("\n📈 Additional Metrics:")
    if 'Return [%]' in stats:
        print(f"   Total Return:          {stats['Return [%]']:.2f}%")
    if 'Sharpe Ratio' in stats:
        print(f"   Sharpe Ratio:          {stats['Sharpe Ratio']:.2f}")
    if 'Max. Drawdown [%]' in stats:
        print(f"   Max Drawdown:          {stats['Max. Drawdown [%]']:.2f}%")
    if 'Win Rate [%]' in stats:
        print(f"   Win Rate (Backtesting):{stats['Win Rate [%]']:.2f}%")
    
    print("\n" + "="*70)
    print("✓ Backtest finished successfully!")
    print("="*70 + "\n")
    
    # Step 7: Optional - Generate Plot
    print("Step 7: Plot Generation")
    try:
        response = input("Generate equity curve plot? (y/n): ").strip().lower()
        if response == 'y':
            print("Generating plot... (this will open in a new window)")
            bt.plot()
    except Exception as e:
        print(f"Note: Could not generate plot ({e})")
        print("Make sure matplotlib is installed: pip install matplotlib")
    
    return True


def print_next_steps():
    """Print helpful next steps."""
    print("\n📚 Next Steps:")
    print("-" * 70)
    print("1. Adjust strategy parameters in GBPJPY_SMA_Strategy.py")
    print("2. Test different instruments (EUR_USD, GBP_USD, etc.)")
    print("3. Optimize with different SMA periods")
    print("4. Run walk-forward analysis for robustness testing")
    print("5. Create demo account and forward test on real data")
    print("\nFor more info, see README.md")
    print("="*70 + "\n")


if __name__ == "__main__":
    try:
        success = main()
        if success:
            print_next_steps()
        else:
            print("⚠️  Backtest failed. See errors above.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Backtest interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
