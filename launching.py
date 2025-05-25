import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime
from gspread_dataframe import set_with_dataframe
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Append Launching Data", layout="wide")
st.title("📊 Append Launching Campaigns to Google Sheets")

# --- STEP 1: Upload CSV ---
st.subheader("📁 Step 1: Upload CSV file(s)")
uploaded_files = st.file_uploader("Upload multiple CSV files", type=["csv"], accept_multiple_files=True)

if uploaded_files:
    # Combine all CSVs
    df_list = [pd.read_csv(file) for file in uploaded_files]
    df = pd.concat(df_list, ignore_index=True)

    # --- PROCESSING ---
    df["Keyword"] = ""
    df["Match_Type"] = ""
    df["CVR"] = df["Orders"] / df["Clicks"]
    df["CVR"] = df["CVR"].fillna(0)

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

        match = re.search(
            r'^(.*?)[_\s]+(?:asin[_\s]*)?((?:b,p|a,b|p|b|ex|exp))(?:(?:\s*\d+h\d+|\s*\d+h|\s*\d+|)?)$',
            campaign
        )
        if match:
            keyword_part = match.group(1).strip()
            type_part = match.group(2).strip()
            parts = keyword_part.split('_')
            keyword = ' '.join(parts[3:]) if len(parts) > 3 else ' '.join(parts[1:])
            return pd.Series([keyword.strip(), type_part])

        return pd.Series([None, None])

    df[['Keyword', 'Match_Type']] = df['Campaigns'].apply(extract_keyword_type)

    # Chuẩn hoá CPC
    df['CPC(USD)'] = df['CPC(USD)'].replace({r'\$': '', ',': '.'}, regex=True).replace('', '0').astype(float)

    # Chuẩn hoá ngày
    df['Start date'] = pd.to_datetime(df['Start date'], format='%d/%m/%y', errors='coerce')
    df['Start date'] = df['Start date'].dt.strftime('%d/%m/%Y')

    st.success("✅ File processed. Ready to push!")
    st.dataframe(df.head())

    # --- STEP 2: Read Google Sheets để lấy dòng append ---
    st.subheader("🔐 Step 2: Upload credential.json to push to Google Sheets")
    cred_file = st.file_uploader("Upload your `credentials.json` file", type=["json"])

    if cred_file:
        try:
            creds = Credentials.from_service_account_info(
                eval(cred_file.read().decode()),  # convert file to dict
                scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
            client = gspread.authorize(creds)

            SHEET_ID = "1vaKOc9re-xBwVhJ3oOOGtjmGVembMsAUq93krQo0mpc"
            SHEET_NAME = "LAUNCHING 2025"
            sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

            current_data = sheet.get_all_values()
            start_row = len(current_data) + 1

            if st.button("📤 Append to Google Sheet"):
                set_with_dataframe(sheet, df, row=start_row, col=1, include_column_header=False)
                st.success(f"✅ Successfully appended {len(df)} rows starting from row {start_row}.")

        except Exception as e:
            st.error(f"❌ Error loading credentials: {e}")
else:
    st.info("👈 Please upload your CSV files first.")
