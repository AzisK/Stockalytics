from datetime import datetime

import pandas as pd

from ticker import get_current_price, get_historical_price


def get_future_date():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f+00:00')


def _process_full_sale(buy_row, sell_total_amount, sell_total_quantity, left_buy_quantity, 
                      sell_fees, left_buy_fees, buy_amount, sell_date, sell_price_per_share):
    """Process a full sale of a buy position."""
    buy_row['Sell Type'] = 'Full'
    buy_row['Sell Quantity'] = left_buy_quantity
    buy_row['Sell Total Amount'] = sell_total_amount * left_buy_quantity / sell_total_quantity
    buy_row['Buy Total Amount'] = buy_amount
    buy_row['Sell Fees'] = sell_fees
    buy_row['Buy Fees'] = left_buy_fees
    buy_row['Left Quantity'] = 0
    buy_row['Left Total Amount'] = 0
    buy_row['Left Fees'] = 0
    buy_row['Sell Date'] = sell_date
    buy_row['Sell Price per share'] = sell_price_per_share
    return buy_row

def _process_partial_sale(buy_row, sell_total_amount, sell_total_quantity, sell_quantity,
                         left_buy_quantity, buy_amount, left_buy_fees, total_sell_fees,
                         sell_date, sell_price_per_share):
    """Process a partial sale of a buy position."""
    left_sell_quantity = sell_quantity - left_buy_quantity
    buy_row['Sell Type'] = 'Partial'
    buy_row['Sell Quantity'] = sell_quantity
    buy_row['Left Quantity'] = -left_sell_quantity
    buy_row['Left Total Amount'] = buy_amount * -left_sell_quantity / left_buy_quantity
    buy_row['Left Fees'] = left_buy_fees * -left_sell_quantity / left_buy_quantity
    buy_row['Buy Fees'] = left_buy_fees * sell_quantity / left_buy_quantity
    buy_row['Sell Fees'] = total_sell_fees
    buy_row['Sell Total Amount'] = sell_total_amount * sell_quantity / sell_total_quantity
    buy_row['Buy Total Amount'] = buy_amount * sell_quantity / left_buy_quantity
    buy_row['Sell Date'] = sell_date
    buy_row['Sell Price per share'] = sell_price_per_share
    return buy_row

def _process_dividend_rows(df):
    """Process dividend rows and add necessary columns."""
    dividend_rows = df[df['Type'] == 'DIVIDEND'].copy()
    if not dividend_rows.empty:
        dividend_rows['Sell Total Amount'] = dividend_rows['Total Amount']
        dividend_rows['Buy Total Amount'] = 0
        dividend_rows['Buy Fees'] = 0
        dividend_rows['Sell Fees'] = 0
        dividend_rows['Sell Date'] = dividend_rows['Date']
    return dividend_rows

def _calculate_profits_and_totals(sold_df, buy_rows):
    """Calculate profits and totals for both sold and unsold positions."""
    sold_df_totals = pd.DataFrame()
    if not sold_df.empty:
        sold_df['Total Fees'] = sold_df['Buy Fees'] + sold_df['Sell Fees']
        sold_df['Profit'] = sold_df['Sell Total Amount'] - sold_df['Buy Total Amount'] - sold_df['Buy Fees']
        sold_df_totals = sold_df.groupby(['Ticker', 'Currency'])[['Buy Total Amount', 'Sell Total Amount', 'Profit', 'Total Fees']].sum().reset_index()
        sold_df_totals['Profit (%)'] = sold_df_totals['Profit'] / sold_df_totals['Buy Total Amount'] * 100

    buy_rows['Current Price per share'] = buy_rows['Ticker'].map(get_current_price)
    buy_rows['Unsold Amount'] = buy_rows['Current Price per share'] * buy_rows['Left Quantity']
    buy_rows['Unsold Profit'] = buy_rows['Unsold Amount'] - buy_rows['Left Total Amount'] - buy_rows['Left Fees']

    buy_rows_totals = buy_rows.groupby(['Ticker', 'Currency'])[['Unsold Amount', 'Unsold Profit']].sum().reset_index()
    buy_rows_totals['Unsold Profit (%)'] = buy_rows_totals['Unsold Profit'] / buy_rows_totals['Unsold Amount'] * 100

    return sold_df_totals, buy_rows_totals


def map_sold_to_bought(df):
    sold = []
    sell_rows = df[df['Type'] == 'SELL'].copy()
    buy_rows = df[df['Type'].isin(['BUY', 'STOCK SPLIT'])].copy()
    buy_rows['Left Quantity'] = buy_rows['Quantity']
    buy_rows['Left Total Amount'] = buy_rows['Total Amount']
    buy_rows['Left Fees'] = buy_rows['Fees']
    buy_rows['Sell Date'] = pd.to_datetime(get_future_date())

    for _, row in sell_rows.iterrows():
        sell_total_amount = row['Total Amount']
        sell_total_quantity = row['Quantity']
        sell_quantity = sell_total_quantity
        sell_date = pd.to_datetime(row['Date'])
        sell_price_per_share = row['Price per share']
        total_sell_fees = row['Fees']

        for buy_index, buy_row in buy_rows.iterrows():
            left_buy_quantity = buy_row['Left Quantity']
            left_sell_quantity = sell_quantity - left_buy_quantity
            left_buy_fees = 0 if pd.isna(buy_row['Left Fees']) else buy_row['Left Fees']
            buy_amount = buy_row['Left Total Amount']
            sell_fees = total_sell_fees * left_buy_quantity / sell_total_quantity

            if left_sell_quantity >= 0.01:
                processed_row = _process_full_sale(buy_row, sell_total_amount, sell_total_quantity,
                                                 left_buy_quantity, sell_fees, left_buy_fees,
                                                 buy_amount, sell_date, sell_price_per_share)
                buy_rows = buy_rows.drop(buy_index)
                sold.append(processed_row)
            elif abs(left_sell_quantity) < 0.01:
                processed_row = _process_full_sale(buy_row, sell_total_amount, sell_total_quantity,
                                                 left_buy_quantity, sell_fees, left_buy_fees,
                                                 buy_amount, sell_date, sell_price_per_share)
                buy_rows = buy_rows.drop(buy_index)
                sold.append(processed_row)
                break
            elif left_sell_quantity <= -0.01:
                processed_row = _process_partial_sale(buy_row, sell_total_amount, sell_total_quantity,
                                                    sell_quantity, left_buy_quantity, buy_amount,
                                                    left_buy_fees, total_sell_fees,
                                                    sell_date, sell_price_per_share)
                buy_rows.loc[buy_index, ['Left Quantity', 'Left Total Amount', 'Left Fees']] = [
                    -left_sell_quantity,
                    buy_amount * -left_sell_quantity / left_buy_quantity,
                    left_buy_fees * -left_sell_quantity / left_buy_quantity
                ]
                sold.append(processed_row)
                break

            sell_quantity = left_sell_quantity

    sold_df = pd.DataFrame(sold)
    dividend_rows = _process_dividend_rows(df)
    if not dividend_rows.empty:
        sold_df = pd.concat([sold_df, dividend_rows])

    sold_df_totals, buy_rows_totals = _calculate_profits_and_totals(sold_df, buy_rows)

    all_df_totals = buy_rows_totals
    all_df = pd.concat([sold_df, buy_rows]).reset_index(drop=True)

    if not sold_df_totals.empty:
        all_df_totals = sold_df_totals.merge(buy_rows_totals, on=['Ticker', 'Currency'], how='outer')
        all_df_totals['Total Profit'] = all_df_totals['Profit'] + all_df_totals['Unsold Profit']
        all_df_totals['Total Profit (%)'] = all_df_totals['Total Profit'] / (all_df_totals['Buy Total Amount'] + all_df_totals['Unsold Amount']) * 100

    return all_df, all_df_totals


def get_sold_stats(df):
    grouped = df.groupby(['Ticker', 'Currency'])
    results = [map_sold_to_bought(group) for name, group in grouped]

    # Combine the results
    all_dfs = pd.concat([result[0] for result in results])
    all_profits = pd.concat([result[1] for result in results])

    # Reset index if needed
    all_dfs = all_dfs.reset_index(drop=True)
    all_profits = all_profits.reset_index(drop=True)
    return all_dfs, all_profits


def color_rows_by_sell_date(df):
    """Apply background colors to rows based on sell date."""
    colors = {}
    unique_dates = df['Sell Date'].unique()
    color_palette = ['#042940', '#015c53', '#9fc130', '#818273', '#506165', '#11454f']
    
    for i, date in enumerate(unique_dates):
        colors[date] = color_palette[i % len(color_palette)]
    
    def apply_color(row):
        color = colors.get(row['Sell Date'], '')
        return ['background-color: {}'.format(color) if color else '' for _ in row]
    
    return df.style.apply(apply_color, axis=1)

def color_rows(df, color_by_column=None):
    """Apply different background colors to each row of a DataFrame.
    
    Args:
        df: The DataFrame to style
        color_by_column: Column to use for coloring. If None, uses row index.
    """
    color_palette = ['#042940', '#015c53', '#9fc130', '#818273', '#506165', '#11454f']
    
    def apply_color(row):
        if color_by_column and color_by_column in row.index:
            # Use value in specified column as the color key
            key = row[color_by_column]
        else:
            # Use row name (index) as the color key
            key = row.name
            
        # Get color from palette using key's hash or position
        if isinstance(key, (int, float)):
            color_idx = int(key) % len(color_palette)
        else:
            # For non-numeric keys, use hash to get a consistent color
            color_idx = hash(str(key)) % len(color_palette)
            
        color = color_palette[color_idx]
        return ['background-color: {}'.format(color) for _ in row]
    
    return df.style.apply(apply_color, axis=1)

def map_sold_to_bought_with_date(df, reference_date=None):
    """Map sold positions to bought positions with prices as of a specific reference date.
    
    Args:
        df: DataFrame with transactions
        reference_date: Date to use for pricing unsold positions. If None, uses current prices.
    """
    sold = []
    sell_rows = df[df['Type'] == 'SELL'].copy()
    buy_rows = df[df['Type'].isin(['BUY', 'STOCK SPLIT'])].copy()
    buy_rows['Left Quantity'] = buy_rows['Quantity']
    buy_rows['Left Total Amount'] = buy_rows['Total Amount']
    buy_rows['Left Fees'] = buy_rows['Fees']
    
    # Set sell date for unsold positions
    if reference_date is not None:
        buy_rows['Sell Date'] = pd.to_datetime(reference_date)
    else:
        buy_rows['Sell Date'] = pd.to_datetime(get_future_date())

    for _, row in sell_rows.iterrows():
        sell_total_amount = row['Total Amount']
        sell_total_quantity = row['Quantity']
        sell_quantity = sell_total_quantity
        sell_date = pd.to_datetime(row['Date'])
        sell_price_per_share = row['Price per share']
        total_sell_fees = row['Fees']

        for buy_index, buy_row in buy_rows.iterrows():
            left_buy_quantity = buy_row['Left Quantity']
            left_sell_quantity = sell_quantity - left_buy_quantity
            left_buy_fees = 0 if pd.isna(buy_row['Left Fees']) else buy_row['Left Fees']
            buy_amount = buy_row['Left Total Amount']
            sell_fees = total_sell_fees * left_buy_quantity / sell_total_quantity

            if left_sell_quantity >= 0.01:
                processed_row = _process_full_sale(buy_row, sell_total_amount, sell_total_quantity,
                                                 left_buy_quantity, sell_fees, left_buy_fees,
                                                 buy_amount, sell_date, sell_price_per_share)
                buy_rows = buy_rows.drop(buy_index)
                sold.append(processed_row)
            elif abs(left_sell_quantity) < 0.01:
                processed_row = _process_full_sale(buy_row, sell_total_amount, sell_total_quantity,
                                                 left_buy_quantity, sell_fees, left_buy_fees,
                                                 buy_amount, sell_date, sell_price_per_share)
                buy_rows = buy_rows.drop(buy_index)
                sold.append(processed_row)
                break
            elif left_sell_quantity <= -0.01:
                processed_row = _process_partial_sale(buy_row, sell_total_amount, sell_total_quantity,
                                                    sell_quantity, left_buy_quantity, buy_amount,
                                                    left_buy_fees, total_sell_fees,
                                                    sell_date, sell_price_per_share)
                buy_rows.loc[buy_index, ['Left Quantity', 'Left Total Amount', 'Left Fees']] = [
                    -left_sell_quantity,
                    buy_amount * -left_sell_quantity / left_buy_quantity,
                    left_buy_fees * -left_sell_quantity / left_buy_quantity
                ]
                sold.append(processed_row)
                break

            sell_quantity = left_sell_quantity

    sold_df = pd.DataFrame(sold)
    dividend_rows = _process_dividend_rows(df)
    if not dividend_rows.empty:
        sold_df = pd.concat([sold_df, dividend_rows])

    # Calculate profits and totals with historical or current prices
    sold_df_totals = pd.DataFrame()
    if not sold_df.empty:
        sold_df['Total Fees'] = sold_df['Buy Fees'] + sold_df['Sell Fees']
        sold_df['Profit'] = sold_df['Sell Total Amount'] - sold_df['Buy Total Amount'] - sold_df['Buy Fees']
        sold_df_totals = sold_df.groupby(['Ticker', 'Currency'])[['Buy Total Amount', 'Sell Total Amount', 'Profit', 'Total Fees']].sum().reset_index()
        sold_df_totals['Profit (%)'] = sold_df_totals['Profit'] / sold_df_totals['Buy Total Amount'] * 100

    # For unsold positions, use either historical or current prices
    if reference_date is not None:
        # Use historical prices from the reference date
        # Convert reference_date to string format needed by the API
        date_str = pd.to_datetime(reference_date).strftime('%Y-%m-%d')
        
        # Apply historical prices one by one to avoid DataFrame assignment issues
        historical_prices = []
        for idx, row in buy_rows.iterrows():
            try:
                price = get_historical_price(row['Ticker'], date_str)
                historical_prices.append(price)
            except Exception as e:
                print(f"Error getting price for {row['Ticker']} on {date_str}: {e}")
                # Fallback to current price
                historical_prices.append(get_current_price(row['Ticker']))
        
        # Assign the collected prices to the DataFrame
        buy_rows['Historical Price per share'] = historical_prices
        buy_rows['Unsold Amount'] = buy_rows['Historical Price per share'] * buy_rows['Left Quantity']
    else:
        # Use current prices
        buy_rows['Current Price per share'] = buy_rows['Ticker'].map(get_current_price)
        buy_rows['Unsold Amount'] = buy_rows['Current Price per share'] * buy_rows['Left Quantity']
    
    buy_rows['Unsold Profit'] = buy_rows['Unsold Amount'] - buy_rows['Left Total Amount'] - buy_rows['Left Fees']

    buy_rows_totals = buy_rows.groupby(['Ticker', 'Currency'])[['Unsold Amount', 'Unsold Profit']].sum().reset_index()
    buy_rows_totals['Unsold Profit (%)'] = buy_rows_totals['Unsold Profit'] / buy_rows_totals['Unsold Amount'] * 100

    all_df_totals = buy_rows_totals
    all_df = pd.concat([sold_df, buy_rows]).reset_index(drop=True)

    if not sold_df_totals.empty:
        all_df_totals = sold_df_totals.merge(buy_rows_totals, on=['Ticker', 'Currency'], how='outer')
        all_df_totals['Total Profit'] = all_df_totals['Profit'] + all_df_totals['Unsold Profit']
        all_df_totals['Total Profit (%)'] = all_df_totals['Total Profit'] / (all_df_totals['Buy Total Amount'] + all_df_totals['Unsold Amount']) * 100

    return all_df, all_df_totals


def get_sold_stats_with_date(df, reference_date=None):
    """Get sold stats with prices as of a specific reference date.
    
    Args:
        df: DataFrame with transactions
        reference_date: Date to use for pricing unsold positions. If None, uses current prices.
    """
    grouped = df.groupby(['Ticker', 'Currency'])
    results = [map_sold_to_bought_with_date(group, reference_date) for name, group in grouped]

    # Combine the results
    all_dfs = pd.concat([result[0] for result in results])
    all_profits = pd.concat([result[1] for result in results])

    # Reset index if needed
    all_dfs = all_dfs.reset_index(drop=True)
    all_profits = all_profits.reset_index(drop=True)
    return all_dfs, all_profits
