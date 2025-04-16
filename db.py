import pandas as pd
import functools


@functools.lru_cache
def load_data():
    df = pd.read_csv('Trades.csv', parse_dates=['Date'])

    for col in ['Price per share', 'Total Amount']:
        if col in df.columns:
            df[col] = df[col].str.replace('[$,€]', '', regex=True).astype(float)

    df['Type'] = df['Type'].str.replace(' - MARKET', '')

    buy_condition = df['Type'] == 'BUY'
    df.loc[buy_condition, 'Fees'] = (df.loc[buy_condition, 'Total Amount']
                                     - df.loc[buy_condition, 'Price per share']
                                     * df.loc[buy_condition, 'Quantity'])
    df.loc[buy_condition & (df['Fees'] < 0.01) & (df['Fees'] > -0.6), 'Fees'] = 0

    sell_condition = df['Type'] == 'SELL'
    df.loc[sell_condition, 'Fees'] = (df.loc[sell_condition, 'Price per share']
                                      * df.loc[sell_condition, 'Quantity']
                                      - df.loc[sell_condition, 'Total Amount'])
    df.loc[sell_condition & (df['Fees'] < 0.01) & (df['Fees'] > -0.6), 'Fees'] = 0

    return df
