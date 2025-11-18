# app/streamlit_app.py
import streamlit as st
import pandas as pd
import numpy as np
import os
from io import BytesIO

# Page config (wide + title)
st.set_page_config(page_title="Excel Cleaner", layout="wide")

# ---------------- Sidebar Settings ----------------
st.sidebar.title("Settings")
default_upload_path = st.sidebar.text_input(
    "Default upload directory", value="", placeholder="Optional: /path/to/upload/folder"
)
default_export_path = st.sidebar.text_input(
    "Default export directory", value="", placeholder="Optional: /path/to/export/folder"
)
st.sidebar.markdown("---")

# ---------------- Header (logo above title) ----------------
with st.container():
    try:
        st.image("static/logo.png", width=180)   # enlarged logo
    except Exception:
        st.write("### Logo")

    st.markdown("<h1 style='margin-top: -10px;'>Excel Cleaner & Converter</h1>", unsafe_allow_html=True)

# ---------------- Utility: infer types ----------------
def infer_and_cast(df: pd.DataFrame, datetime_threshold=0.6, numeric_threshold=0.8):
    """
    For each column, try to infer if it's datetime, numeric or remain object.
    If more than numeric_threshold of non-null values convert to numeric.
    If more than datetime_threshold of non-null values convert to datetime.
    Returns casted df and a dict with inferred types.
    """
    inferred = {}
    df = df.copy()
    for col in df.columns:
        series = df[col]
        non_null = series.dropna()
        n = len(non_null)
        if n == 0:
            inferred[col] = "empty"
            continue

        # Try numeric
        coerced_num = pd.to_numeric(non_null, errors="coerce")
        num_ok = coerced_num.notna().sum() / n

        # Try datetime
        coerced_dt = pd.to_datetime(non_null, errors="coerce", infer_datetime_format=True)
        dt_ok = coerced_dt.notna().sum() / n

        # Decide priority: datetime if strong, else numeric if strong
        if dt_ok >= datetime_threshold and dt_ok > num_ok:
            df[col] = pd.to_datetime(df[col], errors="coerce", infer_datetime_format=True)
            inferred[col] = "datetime"
        elif num_ok >= numeric_threshold:
            # if numeric but all ints -> cast to Int64 to preserve NA; else float
            df[col] = pd.to_numeric(df[col], errors="coerce")
            if pd.api.types.is_integer_dtype(pd.Series(coerced_num.dropna()).dtype):
                df[col] = df[col].astype("Int64")
                inferred[col] = "integer"
            else:
                inferred[col] = "float"
        else:
            # Keep as object/string; strip whitespace
            if series.dtype == object:
                df[col] = series.astype(str).replace({"nan": pd.NA})
                df[col] = df[col].where(~df[col].isin(["nan", "None"]), other=pd.NA)
                df[col] = df[col].str.strip()
            inferred[col] = "string"
    return df, inferred

# ---------------- File upload & processing ----------------
uploaded = st.file_uploader("Upload your Excel file", type=["xlsx", "xls", "csv"])

if uploaded:
    # Read intelligently: csv or excel
    if uploaded.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded)

    st.subheader("Preview (Top 20 rows)")
    st.dataframe(df.head(20), use_container_width=True)

    # Remove top rows
    top_rows = st.number_input("Remove top X rows", min_value=0, max_value=len(df), step=1, value=0)
    df_clean = df.iloc[top_rows:].reset_index(drop=True).copy()

    # Use first row as header
    use_first_row = st.checkbox("Use first row as column headers")
    if use_first_row and len(df_clean) > 0:
        df_clean.columns = df_clean.iloc[0].astype(str)
        df_clean = df_clean[1:].reset_index(drop=True)

    st.subheader("After basic header/row cleanup (Top 20)")
    st.dataframe(df_clean.head(20), use_container_width=True)

    # Column selection
    cols_to_keep = st.multiselect("Select columns to keep", df_clean.columns.tolist(), default=df_clean.columns.tolist())
    if not cols_to_keep:
        st.warning("Select at least one column.")
    df_clean = df_clean[cols_to_keep].copy()

    # ---------------- Automatic type inference ----------------
    st.subheader("Automatic type inference")
    infer_button = st.button("Run type inference")
    if infer_button:
        with st.spinner("Inferring column types..."):
            df_inferred, inferred_types = infer_and_cast(df_clean)
            df_clean = df_inferred
        st.success("Type inference complete.")
    else:
        # Offer to show current simple dtypes if not inferred
        inferred_types = {c: str(df_clean[c].dtype) for c in df_clean.columns}

    # Show inferred types summary
    st.write("Inferred column types (click to refresh by running inference):")
    st.json(inferred_types)

    # ---------------- Column Stats (dropdown) ----------------
    st.subheader("Column Stats")
    if len(df_clean.columns) > 0:
        col = st.selectbox("Choose column to inspect", options=df_clean.columns)
        col_s = df_clean[col]

        # Common metrics
        cnt = len(col_s)
        missing = col_s.isna().sum()
        pct_missing = missing / max(1, cnt)

        st.write(f"**{col}** — inferred: `{inferred_types.get(col, str(col_s.dtype))}`")
        st.write(f"- Count: {cnt}")
        st.write(f"- Missing: {missing} ({pct_missing:.1%})")
        st.write(f"- Unique values: {col_s.nunique(dropna=True)}")

        # If numeric: detailed stats
        if pd.api.types.is_numeric_dtype(col_s):
            st.write("**Numeric statistics**")
            # describe returns count, mean, std, min, 25%, 50%, 75%, max
            desc = col_s.describe().to_frame().T
            st.table(desc)

            median = col_s.median()
            st.write(f"- Median: {median}")
            # Simple histogram (streamlit chart)
            hist_values = col_s.dropna()
            if len(hist_values) > 0:
                st.write("Distribution (histogram):")
                st.bar_chart(hist_values.value_counts(bins=20).sort_index())
        else:
            # Categorical / string stats
            top = col_s.value_counts(dropna=True).head(10)
            if len(top) > 0:
                st.write("Top values:")
                st.table(top)

    # ---------------- Export block ----------------
    st.subheader("Export")
    export_type = st.selectbox("Select export format", ["parquet", "csv", "xlsx"])
    if st.button("Prepare download"):
        # original name and cleaned suffix
        orig_name = os.path.splitext(uploaded.name)[0]
        cleaned_name = f"{orig_name}_cleaned"

        if default_export_path.strip():
            out_base = os.path.join(default_export_path, cleaned_name)
        else:
            out_base = cleaned_name

        if export_type == "parquet":
            # write to BytesIO using pyarrow engine
            buf = BytesIO()
            df_clean.to_parquet(buf, engine="pyarrow", index=False)
            buf.seek(0)
            st.download_button("Download Parquet", data=buf.read(), file_name=out_base + ".parquet", mime="application/octet-stream")

        elif export_type == "csv":
            csv_bytes = df_clean.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", data=csv_bytes, file_name=out_base + ".csv", mime="text/csv")

        elif export_type == "xlsx":
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df_clean.to_excel(writer, index=False, sheet_name="cleaned")
            buf.seek(0)
            st.download_button("Download Excel", data=buf.read(), file_name=out_base + ".xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
