import streamlit as st
import pandas as pd
import requests
import re
import time
import concurrent.futures
from io import BytesIO

st.set_page_config(page_title="Pearltrees Crawler + Filter", page_icon="🌿", layout="centered")

# --- API constants ---
TREE_SIBLING_API = "https://www.pearltrees.com/s/treeandpearlsapi/getPearlParentTreeAndSiblingPearls"
PRELOAD_API = "https://www.pearltrees.com/s/readerapi/preloadPearlReaderInfo"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://www.pearltrees.com",
}

# ---------- Utility functions ----------
def extract_pearl_id(url: str):
    """Tách pearlId từ URL item..."""
    m = re.search(r"item(\d+)", url)
    if m:
        return int(m.group(1))
    m = re.search(r"pearlId=(\d+)", url)
    return int(m.group(1)) if m else None

def get_related_pearl_ids(pearl_id: int):
    """Lấy danh sách pearl con / anh em"""
    try:
        r = requests.get(TREE_SIBLING_API, params={"pearlId": pearl_id}, headers=HEADERS, timeout=10)
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

def check_valid_pearl(username, pearl_id, timeout=8):
    """Kiểm tra 1 pearlId có browserUrl hợp lệ"""
    try:
        params = {"userId": 0, "pearlId": int(pearl_id)}
        headers = HEADERS.copy()
        headers["Referer"] = f"https://www.pearltrees.com/{username}"
        r = requests.get(PRELOAD_API, params=params, headers=headers, timeout=timeout)
        if r.status_code != 200:
            return None
        data = r.json()
        url = data.get("browserUrl")
        if url and str(pearl_id) in url:
            return f"https://www.pearltrees.com/{username}/item{pearl_id}"
        return None
    except Exception:
        return None

def crawl_tree(seed_id: int, limit=500, delay=0.3):
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

# ---------- Streamlit App ----------
st.title("🌿 Pearltrees — Crawl & Lọc Link Hợp Lệ")
st.markdown("""
Nhập **tên tài khoản** hoặc **URL item** (ví dụ `https://www.pearltrees.com/heiliaounu/item751860259`),
app sẽ:
1. Crawl toàn bộ **pearlId** liên quan (qua API chính thức),
2. Kiểm tra song song từng ID để tìm **link hoạt động thật**,
3. Xuất file Excel chứa link hoàn chỉnh.
""")

col1, col2 = st.columns(2)
with col1:
    username = st.text_input("👤 Tên tài khoản (vd: heiliaounu):", "")
with col2:
    start_url = st.text_input("🌐 Hoặc dán 1 URL item:", "")

max_items = st.number_input("Giới hạn số item tối đa để crawl", min_value=10, max_value=5000, value=500)
threads = st.slider("Số luồng kiểm tra song song", min_value=2, max_value=20, value=8)

if st.button("🚀 Bắt đầu Crawl + Lọc"):
    if not username and not start_url:
        st.warning("⚠️ Cần nhập username hoặc URL item.")
    else:
        # Lấy pearlId seed
        seed_id = None
        if start_url:
            seed_id = extract_pearl_id(start_url)
        if not seed_id:
            st.error("❌ Không tìm thấy pearlId trong URL.")
        else:
            st.info(f"🔍 Seed pearlId = {seed_id}")
            with st.spinner("Đang crawl danh sách ID..."):
                pearl_ids = crawl_tree(seed_id, limit=max_items)
                st.success(f"✅ Crawl xong {len(pearl_ids)} ID. Bắt đầu lọc...")

            progress = st.progress(0)
            valid_links = []
            total = len(pearl_ids)
            start_time = time.time()

            def process_pid(pid):
                return pid, check_valid_pearl(username, pid)

            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                futures = {executor.submit(process_pid, pid): pid for pid in pearl_ids}
                for i, future in enumerate(concurrent.futures.as_completed(futures)):
                    pid, link = future.result()
                    if link:
                        valid_links.append({"pearlId": pid, "Link": link})
                    progress.progress(min((i + 1) / total, 1.0))

            elapsed = time.time() - start_time
            st.success(f"✅ Hoàn tất! {len(valid_links)} link hợp lệ trong {elapsed:.1f}s.")

            if valid_links:
                df = pd.DataFrame(valid_links).sort_values("pearlId").drop_duplicates()
                st.dataframe(df)

                buffer = BytesIO()
                df.to_excel(buffer, index=False, engine="openpyxl")
                buffer.seek(0)
                st.download_button(
                    "📥 Tải file Excel link hợp lệ",
                    data=buffer,
                    file_name=f"{username}_valid_links.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            else:
                st.warning("Không tìm thấy link hợp lệ nào.")
