from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from sold import get_sold_stats_with_date


def daily_status(df):
    # Get date range from min transaction date to today
    min_timestamp = df['Date'].min()
    min_date = min(min_timestamp.date(), datetime.now().date())
    max_date = datetime.now().date()
    date_range = pd.date_range(start=min_date, end=max_date, freq='D')

    # Initialize lists to store daily results
    daily_results = []

    # Set a progress bar for the calculation
    progress_bar = st.progress(0)

    # Iterate through each day and calculate cumulative profits with historical prices
    for i, day in enumerate(date_range):
        current_date = day.date()

        # Filter transactions up to this date
        filtered_df = df[df['Date'].dt.date <= current_date]

        # Skip days with no transactions
        if len(filtered_df) == 0:
            continue

        # Get profit stats for transactions up to this day using historical prices
        try:
            _, day_profit_total = get_sold_stats_with_date(filtered_df, reference_date=current_date)

            # Skip if no profit data
            if day_profit_total.empty:
                continue

            # Extract relevant metrics for this day
            realized_profit = day_profit_total['Profit'].sum() if 'Profit' in day_profit_total else 0
            unrealized_profit = day_profit_total['Unsold Profit'].sum() if 'Unsold Profit' in day_profit_total else 0
            total_profit = realized_profit + unrealized_profit
            buy_amount = day_profit_total['Buy Total Amount'].sum() if 'Buy Total Amount' in day_profit_total else 0
            sell_amount = day_profit_total['Sell Total Amount'].sum() if 'Sell Total Amount' in day_profit_total else 0

            # Add to results
            daily_results.append({
                'Date': current_date,
                'Realized Profit': realized_profit,
                'Unrealized Profit': unrealized_profit,
                'Total Profit': total_profit,
                'Buy Amount': buy_amount,
                'Sell Amount': sell_amount,
                'Transactions': len(filtered_df)
            })
        except Exception as e:
            st.error(f"Error processing date {current_date}: {e}")

        # Update progress bar
        progress_bar.progress((i + 1) / len(date_range))

    # Clear progress bar when done
    progress_bar.empty()

    if daily_results:
        # Convert to DataFrame
        daily_df = pd.DataFrame(daily_results)

        # Sort by date for proper timeline display
        daily_df = daily_df.sort_values('Date')

        fig = px.line(
            daily_df,
            x='Date',
            y=['Realized Profit', 'Unrealized Profit', 'Total Profit'],
            title='Daily Profit Timeline',
            labels={'value': 'Profit', 'Date': 'Date', 'variable': 'Type'},
            markers=True
        )

        # Show the plot
        st.plotly_chart(fig, use_container_width=True)

        with st.expander('Daily Profit Data', expanded=False):
            st.dataframe(daily_df.sort_values('Date', ascending=False).style.format({
                'Realized Profit': '€{:.2f}',
                'Unrealized Profit': '€{:.2f}',
                'Total Profit': '€{:.2f}',
                'Buy Amount': '€{:.2f}',
                'Sell Amount': '€{:.2f}'
            }))
    else:
        st.warning("No daily profit data could be calculated.")
