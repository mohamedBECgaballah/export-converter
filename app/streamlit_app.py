"""
app/streamlit_app.py

Run:
    streamlit run app/streamlit_app.py
"""

import streamlit as st
import pandas as pd
import os

# ---------- Page Config ----------
st.set_page_config(page_title="Excel Cleaner", layout="wide")

# ---------- Sidebar Settings ----------
st.sidebar.title("Settings")

default_upload_path = st.sidebar.text_input(
    "Default upload directory",
    value="",
    placeholder="Optional: /path/to/upload/folder"
)

default_export_path = st.sidebar.text_input(
    "Default export directory",
    value="",
    placeholder="Optional: /path/to/export/folder"
)

st.sidebar.markdown("---")

# ---------- Header with Logo Placeholder ----------
cols = st.columns([0.2, 2])

with cols[0]:
    st.write("### Logo Placeholder")
    # You can replace with:
    # st.image("your_logo.png", width=120)

with cols[1]:
    st.title("Excel Cleaner & Converter")

# ---------- File Upload Section ----------
uploaded = st.file_uploader("Upload your Excel file", type=["xlsx"])

if uploaded:
    # Load
    df = pd.read_excel(uploaded)

    st.subheader("Preview (Top 20 Rows)")
    st.dataframe(df.head(20), use_container_width=True)

    # ---------- Remove Top Rows ----------
    top_rows = st.number_input(
        "Remove top X rows",
        min_value=0,
        max_value=len(df),
        step=1
    )
    df_clean = df.iloc[top_rows:].copy()

    # ---------- Use First Row as Header ----------
    use_first_row = st.checkbox("Use first row as column headers")
    if use_first_row:
        df_clean.columns = df_clean.iloc[0]
        df_clean = df_clean[1:]

    st.subheader("Cleaned Preview")
    st.dataframe(df_clean.head(20), use_container_width=True)

    # ---------- Column Selection ----------
    cols_to_keep = st.multiselect(
        "Select columns to keep",
        df_clean.columns.tolist(),
        default=df_clean.columns.tolist()
    )
    df_clean = df_clean[cols_to_keep]

    # ---------- Column Stats via Dropdown ----------
    st.subheader("Column Stats")

    if len(cols_to_keep) > 0:
        selected_col = st.selectbox(
            "Choose a column to view stats",
            options=cols_to_keep
        )

        if selected_col:
            col_data = df_clean[selected_col]

            st.write(f"### Stats for: **{selected_col}**")
            st.write(f"- Data type: `{col_data.dtype}`")
            st.write(f"- Blanks: `{col_data.isna().sum()}`")
            st.write(f"- Unique values: `{col_data.nunique()}`")

            # Category breakdown if low cardinality
            if col_data.nunique() <= 20:
                st.write("Top values:")
                st.write(col_data.value_counts().head(10))

            # Numeric statistics
            if pd.api.types.is_numeric_dtype(col_data):
                st.write("Numeric summary:")
                st.write(col_data.describe())

    # ---------- Export ----------
    st.subheader("Export File")

    export_type = st.selectbox("Select export format", ["parquet", "csv", "xlsx"])

    if st.button("Download"):
        # Determine original filename
        orig_name = os.path.splitext(uploaded.name)[0]
        cleaned_name = orig_name + "_cleaned"

        # Prepare export path
        if default_export_path.strip():
            full_path = os.path.join(default_export_path, cleaned_name)
        else:
            full_path = cleaned_name

        # Output file and Streamlit download
        if export_type == "parquet":
            outfile = cleaned_name + ".parquet"
            data = df_clean.to_parquet(index=False)
            st.download_button("Download Parquet", data=data, file_name=outfile)

        elif export_type == "csv":
            outfile = cleaned_name + ".csv"
            data = df_clean.to_csv(index=False).encode()
            st.download_button("Download CSV", data=data, file_name=outfile)

        elif export_type == "xlsx":
            outfile = cleaned_name + ".xlsx"
            buffer = df_clean.to_excel(index=False, engine="openpyxl")
            st.download_button("Download Excel", data=buffer, file_name=outfile)
