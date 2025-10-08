import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Pearltrees Pearl ID Crawler", page_icon="🌿", layout="centered")

TREE_API = "https://www.pearltrees.com/s/treeandpearlsapi/getTreeAndPearls"

def get_all_pearls(username):
    """Lấy tất cả pearlId từ tài khoản Pearltrees"""
    try:
        url = f"{TREE_API}?ownerUserName={username}"
        r = requests.get(url, timeout=15)
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
st.markdown("Nhập **tên tài khoản Pearltrees**, công cụ sẽ trả về toàn bộ **Pearl ID** thuộc tài khoản đó.")

username = st.text_input("👤 Nhập tên tài khoản (vd: heiliaounu):", "")

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

                # Tải Excel
                excel_bytes = df.to_excel(index=False, engine="openpyxl")
                st.download_button(
                    label="📥 Tải file Excel",
                    data=excel_bytes,
                    file_name=f"{username}_pearls.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            else:
                st.info("Không tìm thấy Pearl ID nào.")
