import streamlit as st
import pandas as pd
import requests
import re
import time
from io import BytesIO

st.set_page_config(page_title="heo ú ", page_icon="🌿", layout="centered")

API_URL = "https://www.pearltrees.com/s/treeandpearlsapi/getPearlParentTreeAndSiblingPearls"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://www.pearltrees.com",
}

def extract_pearl_id(url: str):
    """Tách pearlId từ URL kiểu .../item123456"""
    m = re.search(r"item(\d+)", url)
    if m:
        return int(m.group(1))
    m = re.search(r"pearlId=(\d+)", url)
    return int(m.group(1)) if m else None

def get_related_pearl_ids(pearl_id: int):
    """Lấy danh sách pearl con / anh em"""
    try:
        r = requests.get(API_URL, params={"pearlId": pearl_id}, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        ids = set()
        def extract(obj):
            if isinstance(obj, dict):
                if "id" in obj and isinstance(obj["id"], int):
                    ids.add(obj["id"])
                for v in obj.values():
                    extract(v)
            elif isinstance(obj, list):
                for it in obj:
                    extract(it)
        extract(data)
        return list(ids)
    except Exception:
        return []

def crawl_tree(seed_id: int, limit=1000, delay=0.3):
    """Duyệt toàn bộ cây từ seed_id"""
    visited, to_visit = set(), [seed_id]
    results = []
    progress = st.progress(0)
    step = 0
    while to_visit and len(visited) < limit:
        current = to_visit.pop(0)
        if current in visited:
            continue
        visited.add(current)
        results.append(current)
        related = get_related_pearl_ids(current)
        for rid in related:
            if rid not in visited and rid not in to_visit:
                to_visit.append(rid)
        step += 1
        progress.progress(min(step / limit, 1.0))
        time.sleep(delay)
    return sorted(results)

# ---------- Streamlit UI ----------
st.title("🌿 bé heo dễ thương ")
st.markdown("""
hello 
""")

col1, col2 = st.columns(2)
with col1:
    username = st.text_input("👤 Tên tài khoản (vd: heiliaounu):", "")
with col2:
    start_url = st.text_input("🌐 đường link bài viết :", "")

max_items = st.number_input("số lượng bài viết muốn crawl ", min_value=10, max_value=5000, value=500)

if st.button("🐖🐖🐖 Bắt đầu Crawl"):
    if not username and not start_url:
        st.warning("⚠️ Cần nhập username hoặc URL item.")
    else:
        seed_id = None
        if start_url:
            seed_id = extract_pearl_id(start_url)
        if not seed_id:
            st.error("❌ Không tìm thấy pearlId trong URL.")
        else:
            st.info(f"🔍 Seed pearlId = {seed_id}")
            with st.spinner("Đang crawl danh sách ID..."):
                pearl_ids = crawl_tree(seed_id, limit=max_items)
                st.success(f"✅ Crawl xong {len(pearl_ids)} ID. Tạo link...")

            # Tạo link từ pattern
            links = [
                {"pearlId": pid, "Link": f"https://www.pearltrees.com/{username}/item{pid}"}
                for pid in pearl_ids
            ]

            df = pd.DataFrame(links).drop_duplicates().sort_values(by="pearlId")
            st.dataframe(df)

            # Xuất Excel
            buffer = BytesIO()
            df.to_excel(buffer, index=False, engine="openpyxl")
            buffer.seek(0)
            st.download_button(
                label="📥 Tải file Excel link (pattern)",
                data=buffer,
                file_name=f"{username}_pattern_links.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
