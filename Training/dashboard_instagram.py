import streamlit as st
from elasticsearch import Elasticsearch, exceptions
import pandas as pd
import os
from dotenv import load_dotenv

# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================
load_dotenv()
ES_URL = os.getenv("ELASTICSEARCH_URL")
ES_USER = os.getenv("ELASTICSEARCH_USERNAME")
ES_PASS = os.getenv("ELASTICSEARCH_PASSWORD")

# =========================================================
# CONNECT TO ELASTICSEARCH
# =========================================================
def connect_elasticsearch():
    try:
        # Gunakan basic_auth agar tidak deprecated
        es = Elasticsearch(
            [ES_URL],
            basic_auth=(ES_USER, ES_PASS),
            verify_certs=False
        )

        # Tes koneksi dasar (gunakan info cluster aman)
        try:
            es.info()
        except Exception:
            st.warning("Tidak bisa ambil info cluster (mungkin hak akses terbatas).")

        return es
    except exceptions.AuthenticationException:
        st.error("❌ Autentikasi gagal! Cek username/password di file .env kamu.")
        return None
    except Exception as e:
        st.error(f"⚠️ Elasticsearch error: {e}")
        return None


# =========================================================
# AMBIL DATA DARI ELASTICSEARCH
# =========================================================
def get_data(es, index_name="socmed-instagram-comments"):
    try:
        # Query aman untuk semua versi
        query = {
            "size": 1000,
            "sort": [{"created_at": {"order": "desc"}}],
            "_source": [
                "sender_fullname", "text", "sentiment", "like_count",
                "account_for_crawl", "post_url", "created_at"
            ]
        }

        res = es.search(index=index_name, body=query)
        hits = res.get("hits", {}).get("hits", [])
        data = []
        for hit in hits:
            src = hit.get("_source", {})
            data.append({
                "Nama": src.get("sender_fullname", ""),
                "Komentar": src.get("text", ""),
                "Sentimen": src.get("sentiment", ""),
                "Likes": src.get("like_count", 0),
                "Akun": src.get("account_for_crawl", ""),
                "URL Post": src.get("post_url", ""),
                "Tanggal": src.get("created_at", "")
            })

        return pd.DataFrame(data)
    except exceptions.NotFoundError:
        st.warning("⚠️ Index tidak ditemukan di Elasticsearch.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Elasticsearch error: {e}")
        return pd.DataFrame()


# =========================================================
# DASHBOARD UTAMA
# =========================================================
def main():
    st.set_page_config(page_title="Instagram Comment Dashboard", layout="wide")

    # Header
    st.title("📊 Dashboard Komentar Instagram")
    st.write("Data diambil langsung dari Elasticsearch index `socmed-instagram-comments`")

    # Koneksi
    es = connect_elasticsearch()
    if es is None:
        st.stop()

    # Ambil data
    df = get_data(es)

    if df.empty:
        st.warning("Tidak ada data yang ditemukan di Elasticsearch.")
        st.stop()

    # =====================================================
    # KOMPONEN DASHBOARD (tampilan sesuai referensi kamu)
    # =====================================================
    col1, col2, col3 = st.columns(3)

    total_komentar = len(df)
    total_like = df["Likes"].sum()
    sentimen_positif = len(df[df["Sentimen"] == "positif"])
    sentimen_negatif = len(df[df["Sentimen"] == "negatif"])
    sentimen_netral = len(df[df["Sentimen"] == "netral"])

    with col1:
        st.metric("Total Komentar", total_komentar)
        st.metric("Total Likes", total_like)

    with col2:
        st.metric("Sentimen Positif", sentimen_positif)
        st.metric("Sentimen Negatif", sentimen_negatif)

    with col3:
        st.metric("Sentimen Netral", sentimen_netral)

    st.divider()

    # =====================================================
    # TABEL DATA
    # =====================================================
    st.subheader("🗒️ Daftar Komentar Terbaru")
    st.dataframe(df, use_container_width=True)


# =========================================================
# MAIN EXECUTION
# =========================================================
if __name__ == "__main__":
    main()
