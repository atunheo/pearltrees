import streamlit as st
import pandas as pd
import requests
import re
import time
from io import BytesIO

st.set_page_config(page_title="heo ú", page_icon="🌿", layout="centered")

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

def get_final_url(url):
    """Theo dõi redirect để lấy URL cuối cùng"""
    try:
        r = requests.head(url, allow_redirects=True, timeout=10)
        return r.url
    except Exception:
        return url

# ---------- Streamlit UI ----------
st.title("🌿 heo con dễ thương ")
st.markdown("""
hello world nè 
""")

col1, col2 = st.columns(2)
with col1:
    username = st.text_input("👤 Tên tài khoản (vd: heiliaounu):", "")
with col2:
    start_url = st.text_input("🌐 link bài viết :", "")

max_items = st.number_input("số lượng bài viết  crawl", min_value=10, max_value=5000, value=500)
delay = st.slider("Độ trễ giữa các request (giây)", min_value=0.0, max_value=3.0, value=0.3, step=0.1)

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
                pearl_ids = crawl_tree(seed_id, limit=max_items, delay=delay)
                st.success(f"✅ Crawl xong {len(pearl_ids)} ID. Đang lấy Final Link...")

            progress = st.progress(0)
            final_links = []
            total = len(pearl_ids)

            for i, pid in enumerate(pearl_ids):
                raw_link = f"https://www.pearltrees.com/{username}/item{pid}"
                final_url = get_final_url(raw_link)
                final_links.append(final_url)
                progress.progress(min((i + 1) / total, 1.0))
                time.sleep(delay)

            df = pd.DataFrame(final_links, columns=["Final Link"])
            df = df.drop_duplicates().sort_values(by="Final Link").reset_index(drop=True)

            st.success(f"✅ Hoàn tất! Thu được {len(df)} final links.")
            st.dataframe(df)

            buffer = BytesIO()
            df.to_excel(buffer, index=False, engine="openpyxl")
            buffer.seek(0)
            st.download_button(
                label="📥 Tải file Excel Final Link",
                data=buffer,
                file_name=f"{username}_final_links.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
