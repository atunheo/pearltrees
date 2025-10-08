# streamlit_app.py
import streamlit as st
import openpyxl
from openpyxl import Workbook
import os
import pandas as pd

OUTPUT_FILE = "pearltrees_urls.xlsx"

def save_url_to_excel(url, filename=OUTPUT_FILE):
    """Lưu URL vào file Excel, tránh trùng lặp"""
    if not os.path.exists(filename):
        wb = Workbook()
        ws = wb.active
        ws.title = "URLs"
        ws.append(["Index", "URL"])
    else:
        wb = openpyxl.load_workbook(filename)
        ws = wb.active

    existing = {ws.cell(row=i, column=2).value for i in range(2, ws.max_row + 1)}
    if url not in existing:
        ws.append([ws.max_row, url])
        wb.save(filename)
        st.success(f"✅ Đã lưu URL: {url}")
    else:
        st.info(f"🔁 URL đã tồn tại: {url}")

def load_urls(filename=OUTPUT_FILE):
    """Đọc file Excel thành DataFrame"""
    if os.path.exists(filename):
        df = pd.read_excel(filename)
        return df
    return pd.DataFrame(columns=["Index", "URL"])

st.title("🌐 Lưu trữ URL Pearltrees")
st.write("Nhập URL bạn muốn lưu vào danh sách theo dõi:")

url_input = st.text_input("Nhập URL Pearltrees:")
if st.button("💾 Lưu URL"):
    if url_input.strip():
        save_url_to_excel(url_input.strip())
    else:
        st.warning("⚠️ Vui lòng nhập URL hợp lệ.")

st.subheader("📄 Danh sách URL đã lưu")
urls_df = load_urls()
st.dataframe(urls_df)

st.download_button(
    label="📥 Tải xuống file Excel",
    data=open(OUTPUT_FILE, "rb").read() if os.path.exists(OUTPUT_FILE) else b"",
    file_name="pearltrees_urls.xlsx",
)
