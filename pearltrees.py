import streamlit as st
import requests
import pandas as pd
import time

st.set_page_config(page_title="Pearltrees Link Crawler", page_icon="🌐", layout="centered")

TREE_API = "https://www.pearltrees.com/s/treeandpearlsapi/getPearlParentTreeAndSiblingPearls"
DETAIL_API = "https://www.pearltrees.com/s/readerapi/preloadPearlReaderInfo"

def get_related_pearl_ids(pearl_id):
    """Lấy danh sách pearl con hoặc cùng cấp."""
    try:
        r = requests.get(TREE_API, params={"pearlId": pearl_id}, timeout=10)
        r.raise_for_status()
        data = r.json()
        ids = set()
        for k, v in data.items():
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and "id" in item:
                        ids.add(item["id"])
        return list(ids)
    except Exception as e:
        st.error(f"❌ Lỗi lấy danh sách child: {e}")
        return []

def get_pearl_url(user_id, pearl_id):
    """Lấy URL bài viết từ API chi tiết."""
    try:
        r = requests.get(DETAIL_API, params={"userId": user_id, "pearlId": pearl_id}, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("browserUrl")
    except Exception as e:
        st.error(f"❌ Lỗi lấy URL cho pearl {pearl_id}: {e}")
        return None

def crawl_pearltrees(user_id, root_pearl_id, delay=1):
    """Thu thập toàn bộ link bài viết trong cây Pearltrees."""
    visited = set()
    to_visit = [root_pearl_id]
    results = []

    progress = st.progress(0)
    step = 0

    while to_visit:
        current_id = to_visit.pop(0)
        if current_id in visited:
            continue
        visited.add(current_id)

        url = get_pearl_url(user_id, current_id)
        if url:
            results.append({"pearlId": current_id, "URL": url})

        children = get_related_pearl_ids(current_id)
        for c in children:
            if c not in visited:
                to_visit.append(c)

        step += 1
        progress.progress(min(step / 50, 1.0))  # thanh tiến trình
        time.sleep(delay)

    return pd.DataFrame(results)

# --- Giao diện Streamlit ---
st.title("🌐 Pearltrees Link Crawler")
st.markdown("Công cụ tự động thu thập toàn bộ **URL bài viết** từ Pearltrees bằng API nội bộ.")

user_id = st.text_input("🔹 Nhập User ID", value="18995598")
root_pearl_id = st.text_input("🔹 Nhập Pearl ID gốc", value="751860259")

if st.button("🚀 Bắt đầu thu thập"):
    if not user_id or not root_pearl_id:
        st.warning("⚠️ Vui lòng nhập cả User ID và Pearl ID.")
    else:
        with st.spinner("⏳ Đang thu thập dữ liệu..."):
            df = crawl_pearltrees(int(user_id), int(root_pearl_id))
            if not df.empty:
                st.success(f"✅ Thu thập {len(df)} liên kết thành công!")
                st.dataframe(df)

                # Cho phép tải file Excel
                excel_bytes = df.to_excel(index=False, engine="openpyxl")
                st.download_button(
                    label="📥 Tải file Excel",
                    data=excel_bytes,
                    file_name="pearltrees_links.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            else:
                st.info("Không tìm thấy liên kết nào.")
