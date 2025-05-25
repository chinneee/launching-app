import streamlit as st
import pandas as pd
import numpy as np
import os
import re
import glob
from io import StringIO
import json
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Append CSV to Google Sheet", layout="wide")
st.title("📊 Append CSV Data to Google Sheet After Processing")

# --- Step 1: Upload CSV Files ---
uploaded_files = st.file_uploader("Upload one or more CSV files", type="csv", accept_multiple_files=True)

if uploaded_files:
    # Read and concatenate all CSVs
    df_list = []
    for uploaded_file in uploaded_files:
        df = pd.read_csv(uploaded_file)
        df_list.append(df)
    df_combined = pd.concat(df_list, ignore_index=True)

    # --- Step 2: Clean & Transform Data ---
    st.subheader("✅ Data Cleaning and Transformation")

    df_combined["Keyword"] = ""
    df_combined["Match_Type"] = ""

    # Add CVR column
    df_combined["CVR"] = df_combined["Orders"] / df_combined["Clicks"]
    df_combined["CVR"] = df_combined["CVR"].fillna(0)

    # Campaign keyword extraction function
    def extract_keyword_type(campaign):
        campaign = str(campaign).strip().lower()
        campaign = re.sub(r'[_\s]*\d{1,2}h(?:\d{1,2}m?)?$', '', campaign)
        if campaign.endswith('_product exp'):
            return pd.Series(['product', 'exp'])
        if 'auto' in campaign:
            match = re.search(r'(auto\s?\d*(?:h\d*)?)', campaign, re.IGNORECASE)
            return pd.Series([match.group(1).strip(), 'auto']) if match else pd.Series([None, 'auto'])
        if 'all key' in campaign:
            match = re.search(r'(all\s?key(?:\s?\w+)*)', campaign, re.IGNORECASE)
            return pd.Series([match.group(1).strip(), 'all key']) if match else pd.Series([None, 'all key'])
        match = re.search(r'^(.*?)[_\s]+(?:asin[_\s]*)?((?:b,p|a,b|p|b|ex|exp))(?:(?:\s*\d+h\d+|\s*\d+h|\s*\d+|)?)$', campaign)
        if match:
            keyword_part = match.group(1).strip()
            type_part = match.group(2).strip()
            parts = keyword_part.split('_')
            if len(parts) > 3:
                keyword = ' '.join(parts[3:])
            elif len(parts) > 1:
                keyword = ' '.join(parts[1:])
            else:
                keyword = keyword_part
            return pd.Series([keyword.strip(), type_part])
        return pd.Series([None, None])

    df_combined[['Keyword', 'Match_Type']] = df_combined['Campaigns'].apply(extract_keyword_type)

    # Convert and format date
    df_combined['Start date'] = pd.to_datetime(df_combined['Start date'], format='%d/%m/%y', errors='coerce')
    df_combined['Start date'] = df_combined['Start date'].dt.strftime('%d/%m/%Y')

    # Clean CPC column
    df_combined['CPC(USD)'] = df_combined['CPC(USD)'].replace({r'\$': '', ',': '.'}, regex=True).replace('', '0').astype(float)

    st.success("Data processing complete ✅")
    st.dataframe(df_combined.head())

    # --- Step 3: Upload credentials.json ---
    st.subheader("🔐 Upload credentials.json to connect to Google Sheets")
    cred_file = st.file_uploader("Upload your `credentials.json` file", type="json", key="cred")

    if cred_file is not None:
        try:
            service_account_info = json.load(cred_file)
            creds = Credentials.from_service_account_info(service_account_info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
            client = gspread.authorize(creds)

            # Google Sheet ID and Worksheet name
            sheet_id = "1vaKOc9re-xBwVhJ3oOOGtjmGVembMsAUq93krQo0mpc"
            sheet_name = "LAUNCHING 2025"

            worksheet = client.open_by_key(sheet_id).worksheet(sheet_name)

            # Get number of rows to append
            data = worksheet.get_all_values()
            existing_rows = len(data)
            start_row = existing_rows + 1

            # Append data
            set_with_dataframe(worksheet, df_combined, row=start_row, col=1, include_column_header=False)
            st.success(f"✅ Data successfully appended starting at row {start_row}.")

        except Exception as e:
            st.error(f"❌ Failed to authenticate or append: {e}")
