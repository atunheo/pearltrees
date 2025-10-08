# streamlit_app.py
import streamlit as st
import requests
import re
import time
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Pearltrees Crawler", page_icon="🌿", layout="centered")

# --- API endpoints ---
TREE_SIBLING_API = "https://www.pearltrees.com/s/treeandpearlsapi/getPearlParentTreeAndSiblingPearls"
PRELOAD_API = "https://www.pearltrees.com/s/readerapi/preloadPearlReaderInfo"

# --- default headers to mimic a browser (helps tránh lỗi 500) ---
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.pearltrees.com/",
    "Origin": "https://www.pearltrees.com",
    "X-Requested-With": "XMLHttpRequest",
}

# ---------- helper functions ----------
def extract_pearl_id_from_url(url: str):
    """Tìm pearlId trong URL dạng .../item123456"""
    m = re.search(r"item(\d+)", url)
    if m:
        return int(m.group(1))
    # thử tìm query param pearlId=...
    m2 = re.search(r"pearlId=(\d+)", url)
    if m2:
        return int(m2.group(1))
    return None

def try_find_seed_pearl_from_username(username: str, timeout=10):
    """
    Cố gắng lấy 1 pearlId khởi đầu bằng cách fetch trang user và quét item\d+
    Trả về list (có thể rỗng) các pearlId tìm được.
    """
    url = f"https://www.pearltrees.com/{username}"
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        if r.status_code != 200:
            return []
        html = r.text
        ids = set(map(int, re.findall(r"item(\d+)", html)))
        return sorted(ids)
    except Exception:
        return []

def preload_pearl_info(user_id: int, pearl_id: int, timeout=10):
    """Gọi preloadPearlReaderInfo để lấy chi tiết (có browserUrl, userId...)"""
    try:
        params = {"userId": user_id, "pearlId": pearl_id}
        r = requests.get(PRELOAD_API, params=params, headers=DEFAULT_HEADERS, timeout=timeout)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None

def get_pearl_detail_by_pearlid(pearl_id: int, timeout=10):
    """
    Thử lấy userId + browserUrl cho 1 pearlId.
    Vì preload cần userId, ta thử gọi preload với userId=0 (một số trường hợp trả userId),
    nếu không, cố gắng gọi getPearlParentTreeAndSiblingPearls để tìm dữ liệu kèm userId.
    """
    # 1) Thử preload với userId=0 (nhiều endpoint trả dữ liệu cơ bản bất chấp userId)
    info = preload_pearl_info(0, pearl_id, timeout=timeout)
    if info and isinstance(info, dict):
        # tìm browserUrl và userId (nếu có)
        browser_url = info.get("browserUrl") or info.get("pearl", {}).get("browserUrl")
        user_id = info.get("userId") or info.get("pearl", {}).get("ownerUserId")
        return {"pearlId": pearl_id, "browserUrl": browser_url, "userId": user_id, "raw": info}

    # 2) Nếu không có, gọi tree sibling API để tìm object chứa id-> có thể chứa hơn
    try:
        r = requests.get(TREE_SIBLING_API, params={"pearlId": pearl_id}, headers=DEFAULT_HEADERS, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            # tìm browserUrl hoặc id owner trong data
            # scan dict for browserUrl or userId
            browser_url = None
            user_id = None
            def find_fields(obj):
                nonlocal browser_url, user_id
                if isinstance(obj, dict):
                    if "browserUrl" in obj and not browser_url:
                        browser_url = obj.get("browserUrl")
                    if "userId" in obj and not user_id:
                        user_id = obj.get("userId")
                    for v in obj.values():
                        find_fields(v)
                elif isinstance(obj, list):
                    for it in obj:
                        find_fields(it)
            find_fields(data)
            return {"pearlId": pearl_id, "browserUrl": browser_url, "userId": user_id, "raw": data}
    except Exception:
        pass

    return {"pearlId": pearl_id, "browserUrl": None, "userId": None, "raw": None}

def get_related_pearl_ids(pearl_id: int, timeout=10):
    """Gọi getPearlParentTreeAndSiblingPearls để lấy các pearl liên quan (child/sibling)"""
    try:
        r = requests.get(TREE_SIBLING_API, params={"pearlId": pearl_id}, headers=DEFAULT_HEADERS, timeout=timeout)
        if r.status_code != 200:
            return []
        data = r.json()
        ids = set()
        # duyệt data để thu id
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

# ---------- crawling logic ----------
def crawl_from_seed(seed_pearl_id: int, max_items: int = 500, delay: float = 0.5):
    """
    Duyệt BFS từ seed_pearl_id, thu tất cả pearlId và browserUrl (khi có).
    max_items giới hạn tổng số nodes để tránh quá tải.
    """
    visited = set()
    to_visit = [seed_pearl_id]
    results = []
    steps = 0

    progress = st.progress(0)
    status_text = st.empty()

    while to_visit and len(visited) < max_items:
        current = to_visit.pop(0)
        if current in visited:
            continue
        visited.add(current)

        status_text.info(f"Đang xử lý pearlId: {current}  — đã thu: {len(results)} / giới hạn {max_items}")
        info = get_pearl_detail_by_pearlid(current)
        browser_url = info.get("browserUrl") if info else None
        user_id = info.get("userId") if info else None

        results.append({"pearlId": current, "browserUrl": browser_url, "userId": user_id})
        # lấy related ids
        related = get_related_pearl_ids(current)
        for r in related:
            if r not in visited and r not in to_visit:
                to_visit.append(r)

        steps += 1
        progress.progress(min(steps / max_items, 1.0))
        time.sleep(delay)

    status_text.success(f"Hoàn tất: thu được {len(results)} item(s).")
    return results

# ---------- Streamlit UI ----------
st.title("🌿 Pearltrees — Lấy Pearl ID & URLs")
st.markdown(
    "Bạn có thể nhập **Tên tài khoản** hoặc **dán trực tiếp 1 URL item** (ví dụ: "
    "`https://www.pearltrees.com/heiliaounu/item751860259`).\n\n"
    "- Nếu nhập username, app sẽ cố gắng tìm 1 seed `pearlId` từ trang public.\n"
    "- Sau đó app duyệt đệ quy (BFS) qua API `getPearlParentTreeAndSiblingPearls` để thu toàn bộ `pearlId` và `browserUrl`."
)

col1, col2 = st.columns(2)
with col1:
    user_input = st.text_input("Tên tài khoản (ví dụ: heiliaounu)", value="")
with col2:
    url_input = st.text_input("Hoặc dán 1 URL item (ví dụ chứa 'item123...')", value="")

max_items = st.number_input("Giới hạn số items tối đa (để tránh quá tải)", min_value=10, max_value=5000, value=600, step=10)
delay = st.slider("Delay giữa các request (giây)", min_value=0.1, max_value=3.0, value=0.5, step=0.1)

if st.button("🚀 Bắt đầu thu thập"):
    seed_ids = []
    seed_pearl = None

    # 1) nếu user dán URL item thì ưu tiên lấy pearlId từ đó
    if url_input and "pearltrees.com" in url_input:
        pid = extract_pearl_id_from_url(url_input)
        if pid:
            seed_ids = [pid]
        else:
            st.warning("Không tìm thấy 'item<ID>' trong URL. Vui lòng dán đúng URL item.")
    # 2) nếu chỉ có username -> cố gắng quét HTML để tìm item ids
    elif user_input:
        found = try_find_seed_pearl_from_username(user_input)
        if found:
            seed_ids = found  # dùng các ids tìm được (thứ tự tăng dần)
        else:
            st.warning("Không tìm thấy pearlId trong trang user công khai. Vui lòng dán 1 URL item cụ thể.")
    else:
        st.warning("Vui lòng nhập username hoặc dán 1 URL item.")
    
    # Nếu có seed, tiến hành crawl (ưu tiên id đầu tiên)
    if seed_ids:
        seed = seed_ids[0]
        st.info(f"Sử dụng seed pearlId = {seed}  (tổng seed tìm thấy: {len(seed_ids)})")
        with st.spinner("⏳ Đang crawl..."):
            results = crawl_from_seed(seed, max_items=int(max_items), delay=float(delay))
            if results:
                df = pd.DataFrame(results)
                st.success(f"✅ Thu thập xong — tổng {len(df)} items.")
                st.dataframe(df)

                # Xuất Excel (BytesIO)
                buffer = BytesIO()
                df.to_excel(buffer, index=False, engine="openpyxl")
                buffer.seek(0)
                st.download_button(
                    "📥 Tải file Excel",
                    data=buffer,
                    file_name="pearltrees_links.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("Không thu thập được item nào. Có thể tài khoản private hoặc API bị hạn chế.")
