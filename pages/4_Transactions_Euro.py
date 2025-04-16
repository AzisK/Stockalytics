import pandas as pd
import streamlit as st

from daily import daily_status
from db import load_data
from sold import color_rows_by_sell_date, get_sold_stats, color_rows

df = load_data()
df = df[df['Currency'] == 'EUR']

df = df[df['Type'].str.contains('BUY|SELL|STOCK SPLIT|DIVIDEND|CUSTODY FEE|CUSTODY FEE REVERSAL')]

# Get query parameters
query_params = st.query_params
default_ticker = query_params.get('ticker', 'All Ticker')
default_sell_month = query_params.get('sell_month', 'All')

tickers = df['Ticker'].unique().tolist()
tickers.insert(0, 'All Ticker')
selected_ticker = st.sidebar.selectbox('Select Ticker', tickers, index=tickers.index(default_ticker))

query_params.from_dict(dict(ticker=selected_ticker, sell_month=default_sell_month))

if selected_ticker != 'All Ticker':
    df = df[df['Ticker'] == selected_ticker]

st.dataframe(df)

profit_df, profit_total = get_sold_stats(df)

profit_df['Sell Month'] = profit_df['Sell Date'].dt.tz_localize(None).dt.to_period('M')
sell_months = profit_df['Sell Month'].unique().tolist()
sell_months.insert(0, 'All')
selected_sell_month = st.sidebar.selectbox('Select Sell Month', sell_months, index=sell_months.index(default_sell_month))

if selected_sell_month != 'All':
    profit_df = profit_df[profit_df['Sell Month'] == selected_sell_month]

st.dataframe(color_rows_by_sell_date(profit_df))
st.dataframe(color_rows(profit_total, color_by_column='Ticker'))

fee_rows = df[df['Type'].str.contains('FEE')]
fee_rows = fee_rows.groupby(['Type', 'Currency'])['Total Amount'].sum().reset_index()
if not fee_rows.empty:
    st.dataframe(fee_rows)
    fee_rows['Sell Total Amount'] = 0
    fee_rows['Buy Total Amount'] = 0
    fee_rows['Buy Fees'] = -fee_rows['Total Amount']
    fee_rows['Total Fees'] = -fee_rows['Total Amount']
    fee_rows['Profit'] = fee_rows['Total Amount']
    profit_total = pd.concat([profit_total, fee_rows])

if selected_ticker == 'All Ticker':
    cols = ['Buy Total Amount', 'Sell Total Amount', 'Profit', 'Total Fees', 'Unsold Amount', 'Unsold Profit']
    profit_total = profit_total[cols].sum()
    profit_total['Profit (%)'] = profit_total['Profit'] / profit_total['Buy Total Amount'] * 100
    profit_total['Unsold Profit (%)'] = profit_total['Unsold Profit'] / profit_total['Unsold Amount'] * 100
    profit_total['Total Profit'] = profit_total['Profit'] + profit_total['Unsold Profit']
    profit_total['Total Profit (%)'] = profit_total['Total Profit'] / (
                profit_total['Buy Total Amount'] + profit_total['Unsold Amount']) * 100

    # For Series (1D), convert to DataFrame for styling
    profit_total_df = pd.DataFrame(profit_total).T
    st.dataframe(color_rows(profit_total_df))

st.subheader("Daily Profit")
daily_status(df)
