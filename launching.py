import streamlit as st
import pandas as pd
import numpy as np
import re
import io
import matplotlib.pyplot as plt
from datetime import datetime as dt

import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials

# --- SETUP GOOGLE SHEET ---
SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_ID = "1vaKOc9re-xBwVhJ3oOOGtjmGVembMsAUq93krQo0mpc"
SHEET_NAME = "LAUNCHING 2025"

@st.cache_resource
def get_gsheet_connection():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPE
    )
    client = gspread.authorize(creds)
    return client

# --- EXTRACT FUNCTION ---
def extract_keyword_type(campaign):
    campaign = str(campaign).strip().lower()
    campaign = re.sub(r'[_\s]*\d{1,2}h(?:\d{1,2}m?)?$', '', campaign)

    if campaign.endswith('_product exp'):
        return pd.Series(['product', 'exp'])

    if 'auto' in campaign:
        match = re.search(r'(auto\s?\d*(?:h\d*)?)', campaign)
        return pd.Series([match.group(1).strip(), 'auto']) if match else pd.Series([None, 'auto'])

    if 'all key' in campaign:
        match = re.search(r'(all\s?key(?:\s?\w+)*)', campaign)
        return pd.Series([match.group(1).strip(), 'all key']) if match else pd.Series([None, 'all key'])

    match = re.search(r'^(.*?)[_\s]+(?:asin[_\s]*)?((?:b,p|a,b|p|b|ex|exp))(?:(?:\s*\d+h\d+|\s*\d+h|\s*\d+|)?)$', campaign)
    if match:
        keyword_part = match.group(1).strip()
        type_part = match.group(2).strip()
        parts = keyword_part.split('_')
        keyword = ' '.join(parts[3:]) if len(parts) > 3 else ' '.join(parts[1:])
        return pd.Series([keyword.strip(), type_part])

    return pd.Series([None, None])

# --- MAIN APP ---
st.title("🔁 Keyword Campaign Processing & Google Sheet Uploader")

uploaded_files = st.file_uploader("Upload one or more CSV files", type="csv", accept_multiple_files=True)

if uploaded_files:
    df_list = []
    for file in uploaded_files:
        df = pd.read_csv(file)
        df_list.append(df)

    df_combined = pd.concat(df_list, ignore_index=True)

    # Add columns
    df_combined["Keyword"] = ""
    df_combined["Match_Type"] = ""
    df_combined["CVR"] = df_combined["Orders"] / df_combined["Clicks"]
    df_combined["CVR"] = df_combined["CVR"].fillna(0)

    # Extract keyword and match type
    df_combined[['Keyword', 'Match_Type']] = df_combined['Campaigns'].apply(extract_keyword_type)

    # Show unmatched
    unmatched_rows = df_combined[df_combined['Keyword'].isna() & df_combined['Match_Type'].isna()][['Campaigns', 'Keyword', 'Match_Type']]
    if not unmatched_rows.empty:
        st.subheader("❗️Unmatched Campaigns")
        st.dataframe(unmatched_rows)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            unmatched_rows.to_excel(writer, index=False, sheet_name="Unmatched")
        st.download_button("Download Unmatched Campaigns", output.getvalue(), "unmatched_keyword.xlsx")

    # Format columns
    df_combined['Start date'] = pd.to_datetime(df_combined['Start date'], format='%d/%m/%y', errors='coerce')
    df_combined['Start date'] = df_combined['Start date'].dt.strftime('%d/%m/%Y')
    df_combined['CPC(USD)'] = df_combined['CPC(USD)'].replace({r'\$': '', ',': '.'}, regex=True).replace('', '0').astype(float)

    st.subheader("✅ Processed Data Preview")
    st.dataframe(df_combined.head())

    # Push to Google Sheet
    if st.button("📤 Append to Google Sheet"):
        client = get_gsheet_connection()
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        existing_data = sheet.get_all_values()
        start_row = len(existing_data) + 1

        set_with_dataframe(sheet, df_combined, row=start_row, col=1, include_column_header=False)
        st.success(f"Data appended starting from row {start_row}.")

