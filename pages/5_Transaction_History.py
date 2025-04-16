import streamlit as st

from db import load_data


st.header("Transaction History")
df = load_data()
st.dataframe(df)
transaction_types = df['Type'].unique()
selected_types = st.multiselect("Filter by transaction type", transaction_types, default=transaction_types)
if selected_types:
    trans_filtered = df[df['Type'].isin(selected_types)]
    st.subheader("Transactions Over Time")
    chart_data = trans_filtered.pivot_table(index='Date', columns='Type', values='Total Amount', aggfunc='sum')
    st.bar_chart(chart_data)
