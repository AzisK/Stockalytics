import pandas as pd
import streamlit as st

from db import load_data

st.set_page_config(page_title="Home", layout="wide")


def main():
    uploaded_file = st.file_uploader("Upload your stocks as CSV", type=["csv"])
    
    if uploaded_file is not None:
        try:
            df_uploaded = pd.read_csv(uploaded_file)
            
            st.subheader("Preview uploaded data")
            st.dataframe(df_uploaded)
            
            if st.button("Override"):
                df_uploaded.to_csv("Trades.csv", index=False)
                st.success("✅ Trades.csv has been successfully updated!")
                st.rerun()
        except Exception as e:
            st.error(f"Error uploading file: {e}")
    
    df = load_data()

    st.sidebar.header("Filters")
    date_min = df['Date'].min().date()
    date_max = df['Date'].max().date()
    start_date = st.sidebar.date_input("Start Date", date_min)
    end_date = st.sidebar.date_input("End Date", date_max)
    filtered_df = df[(df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)]
    
    st.subheader("Transactions")
    st.dataframe(filtered_df)
    

if __name__ == "__main__":
    main()
