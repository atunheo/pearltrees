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

        status_text.info(f"Đang_
