import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Pearltrees Pearl ID Finder", page_icon="🌿", layout="centered")

def get_all_pearls(username):
    """Lấy tất cả Pearl ID từ tài khoản Pearltrees (mô phỏng trình duyệt thật)."""
    try:
        url = f"https://www.pearltrees.com/s/treeandpearlsapi/getTreeAndPearls?ownerUserName={username}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": f"https://www.pearltrees.com/{username}",
            "Origin": "https://www.pearltrees.com",
            "X-Requested-With": "XMLHttpRequest",
        }
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            st.error(f"❌ Không thể truy cập tài khoản {username} (mã lỗi {r.status_code})")
            return []
        data = r.json()
    except Exception as e:
        st.error(f"❌ Lỗi khi tải dữ liệu: {e}")
        return []

    pearls = []
    def extract_ids(obj):
        if isinstance(obj, dict):
            if "id" in obj:
                pearls.append(obj["id"])
            for v in obj.values():
                extract_ids(v)
        elif isinstance(obj, list):
            for item in obj:
                extract_ids(item)

    extract_ids(data)
    return sorted(set(pearls))

# --- Giao diện Streamlit ---
st.title("🌿 Pearltrees Pearl ID Finder")
st.markdown(
    "Nhập **tên tài khoản Pearltrees**, công cụ sẽ trả về toàn bộ **Pearl ID** "
    "có thể truy cập công khai."
)

username = st.text_input("👤 Nhập tên tài khoản (ví dụ: heiliaounu):")

if st.button("🚀 Lấy danh sách Pearl ID"):
    if not username.strip():
        st.warning("⚠️ Vui lòng nhập tên tài khoản hợp lệ.")
    else:
        with st.spinner("🔎 Đang lấy dữ liệu từ Pearltrees..."):
            pearls = get_all_pearls(username.strip())
            if pearls:
                df = pd.DataFrame(pearls, columns=["Pearl ID"])
                st.success(f"✅ Tìm thấy {len(df)} Pearl ID trong tài khoản {username}.")
                st.dataframe(df)

                excel_bytes = df.to_excel(index=False, engine="openpyxl")
                st.download_button(
                    label="📥 Tải file Excel",
                    data=excel_bytes,
                    file_name=f"{username}_pearls.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            else:
                st.info("Không tìm thấy Pearl ID nào hoặc tài khoản bị hạn chế quyền truy cập.")
