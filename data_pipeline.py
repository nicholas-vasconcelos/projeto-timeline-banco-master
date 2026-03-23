import yfinance as yf
import pandas as pd
import pandas_market_calendars as mcal
import json
import logging

# Set up defensive logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def fetch_and_prep_b3_data(ticker: str, start_date: str, end_date: str) -> list:
    """
    Fetches market data, aligns to B3 calendar, calculates SMAs, and outputs JSON-ready dict.
    """
    try:
        logger.info(f"Fetching data for {ticker} from {start_date} to {end_date}...")
        # 1. Fetch raw data
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        
        if df.empty:
            raise ValueError(f"No data returned for {ticker}. Check ticker symbol or rate limits.")
            
        # Flatten MultiIndex columns (yfinance behavior change in recent versions)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 2. Generate strict B3 Business Days calendar (BM&F Bovespa)
        b3 = mcal.get_calendar('BMF')
        schedule = b3.schedule(start_date=start_date, end_date=end_date)
        b3_days = mcal.date_range(schedule, frequency='1D')
        
        # 3. Normalize indices to prevent timezone-aware vs timezone-naive crashes
        df.index = df.index.tz_localize(None).normalize()
        b3_days = b3_days.tz_localize(None).normalize()
        
        # 4. Reindex to B3 calendar and apply Strict Forward Fill
        # This carries Friday's close through to Monday open. NO interpolation.
        df = df.reindex(b3_days)
        df = df.ffill() 
        
        # 5. Calculate Rolling Metrics (7-day and 30-day SMA)
        df['SMA_7'] = df['Close'].rolling(window=7, min_periods=1).mean()
        df['SMA_30'] = df['Close'].rolling(window=30, min_periods=1).mean()
        
        # Optional: 30-day annualized volatility (crucial for contagion analysis)
        df['Volatility_30'] = df['Close'].pct_change().rolling(window=30).std() * (252 ** 0.5)
        
        # 6. Clean up for JSON Serialization
        df.index.name = 'Date'
        df = df.reset_index()
        df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
        
        # Convert NaNs to 0 or None for valid JSON handling in React
        df = df.fillna(0) 
        
        return df.to_dict(orient='records')

    except Exception as e:
        logger.error(f"Pipeline failed for {ticker}: {str(e)}")
        return [{"error": str(e)}]

if __name__ == "__main__":
    # Target: BRB Preferred Shares (BSLI4.SA). 
    # Timeline: Capturing baseline before Nov 2025 through today (March 23, 2026).
    target_ticker = 'BSLI4.SA' 
    
    brb_data = fetch_and_prep_b3_data(target_ticker, '2025-08-01', '2026-03-23')
    
    # Export to a local JSON cache so Django doesn't have to hit yfinance on every request
    output_file = 'brb_market_data.json'
    with open(output_file, 'w') as f:
        json.dump(brb_data, f, indent=4)
        
    logger.info(f"Successfully exported data to {output_file}")