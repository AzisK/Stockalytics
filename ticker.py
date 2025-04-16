import yfinance as yf
from functools import lru_cache
import pandas as pd
from datetime import datetime, timedelta
import os

from mapping import RevolutToYahooTicker

# File to store historical prices
HISTORICAL_PRICES_FILE = "historical_prices.csv"

# Initialize the cache as a DataFrame with MultiIndex
historical_prices_cache = pd.DataFrame(columns=['ticker', 'date', 'price']).set_index(['ticker', 'date'])

# Load historical prices cache if it exists
def load_historical_prices_cache():
    global historical_prices_cache
    if os.path.exists(HISTORICAL_PRICES_FILE):
        try:
            # Load the cache from CSV
            cache_df = pd.read_csv(HISTORICAL_PRICES_FILE)
            
            # Convert date column to datetime.date objects
            cache_df['date'] = pd.to_datetime(cache_df['date']).dt.date
            
            # Set the MultiIndex for fast lookups
            cache_df = cache_df.set_index(['ticker', 'date'])
            
            historical_prices_cache = cache_df
            print(f"Loaded price cache with {len(historical_prices_cache)} entries")
        except Exception as e:
            print(f"Error loading historical prices cache: {e}")
            historical_prices_cache = pd.DataFrame(columns=['ticker', 'date', 'price']).set_index(['ticker', 'date'])
    else:
        # Create empty cache if file doesn't exist
        historical_prices_cache = pd.DataFrame(columns=['ticker', 'date', 'price']).set_index(['ticker', 'date'])

# Load the cache at module import time
load_historical_prices_cache()


@lru_cache(maxsize=128)
def get_current_price(ticker):
    print(f"Fetching currentPrice for {ticker}")
    stock = yf.Ticker(RevolutToYahooTicker.get(ticker, ticker))
    price = stock.info.get('currentPrice') or stock.info.get('regularMarketPrice') or 0
    if not price:
        print(f"Could not fetch currentPrice for {ticker}")
        print(stock.info)
        price = 0
    return price


def get_historical_price(ticker, date_str):
    """Get the closing price of a ticker on a specific date.
    First checks the local cache, then falls back to API if needed.
    
    Args:
        ticker: The stock ticker symbol
        date_str: The date in 'YYYY-MM-DD' format
    
    Returns:
        The closing price on that date
    """
    global historical_prices_cache
    
    # Parse the date
    target_date = pd.to_datetime(date_str).date()
    
    # Fast cache lookup with MultiIndex
    try:
        if (ticker, target_date) in historical_prices_cache.index:
            print(f"Using cached price for {ticker} on {date_str}")
            return float(historical_prices_cache.loc[(ticker, target_date), 'price'])
    except KeyError:
        # Index lookup failed, continue to API fetch
        pass
    
    # If not in cache, fetch from API
    print(f"Fetching historical price for {ticker} on {date_str}")
    
    # Convert ticker to Yahoo Finance format if needed
    yahoo_ticker = RevolutToYahooTicker.get(ticker, ticker)
    
    # Set date range: from 10 days before to 10 days after
    # (in case the exact date is a weekend or holiday)
    start_date = (target_date - timedelta(days=10)).strftime('%Y-%m-%d')
    end_date = (target_date + timedelta(days=10)).strftime('%Y-%m-%d')
    
    try:
        # Get historical data
        stock = yf.Ticker(yahoo_ticker)
        hist = stock.history(start=start_date, end=end_date)
        
        if hist.empty:
            print(f"No historical data found for {ticker} around {date_str}")
            current_price = float(get_current_price(ticker))
            
            # Add to cache using DataFrame
            new_row = pd.DataFrame({'price': [current_price]}, index=pd.MultiIndex.from_tuples([(ticker, target_date)], names=['ticker', 'date']))
            historical_prices_cache = pd.concat([historical_prices_cache, new_row])
            save_historical_prices_cache()
            
            return current_price
        
        # Find the closest date
        hist.index = pd.to_datetime(hist.index).date  # Convert to date for easier comparison
        
        # First try to find the exact date
        price = None
        if target_date in hist.index:
            price_series = hist.loc[target_date, 'Close']
            price = price_series.iloc[0] if hasattr(price_series, 'iloc') else price_series
        else:
            # If not found, find the closest date before the target date
            earlier_dates = hist.index[hist.index <= target_date]
            if not earlier_dates.empty:
                closest_earlier = earlier_dates[-1]  # Get the most recent date before target
                price_series = hist.loc[closest_earlier, 'Close']
                price = price_series.iloc[0] if hasattr(price_series, 'iloc') else price_series
            else:
                # If no earlier date, use the earliest available date
                price_series = hist['Close'].iloc[0]
                price = price_series.iloc[0] if hasattr(price_series, 'iloc') else price_series
        
        price = float(price)
        
        # Add to cache using DataFrame
        new_row = pd.DataFrame({'price': [price]}, index=pd.MultiIndex.from_tuples([(ticker, target_date)], names=['ticker', 'date']))
        historical_prices_cache = pd.concat([historical_prices_cache, new_row])
        save_historical_prices_cache()
        
        return price
        
    except Exception as e:
        print(f"Error getting historical price for {ticker} on {date_str}: {e}")
        current_price = float(get_current_price(ticker))
        
        # Add to cache using DataFrame
        new_row = pd.DataFrame({'price': [current_price]}, index=pd.MultiIndex.from_tuples([(ticker, target_date)], names=['ticker', 'date']))
        historical_prices_cache = pd.concat([historical_prices_cache, new_row])
        save_historical_prices_cache()
        
        return current_price


def save_historical_prices_cache():
    """Save the historical prices cache to disk"""
    try:
        # Reset index to convert MultiIndex to columns, then save to CSV
        historical_prices_cache.reset_index().to_csv(HISTORICAL_PRICES_FILE, index=False)
        print(f"Saved {len(historical_prices_cache)} historical prices to cache")
    except Exception as e:
        print(f"Error saving historical prices cache: {e}")


@lru_cache(maxsize=128)
def get_current_prices(tickers):
    """Get current prices for multiple tickers at once."""
    print(f"Fetching current prices for {tickers}")
    prices = {}
    for ticker in tickers:
        prices[ticker] = get_current_price(ticker)
    return prices
