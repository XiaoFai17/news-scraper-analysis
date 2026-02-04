import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Import modul lokal
from scraper import fetch_rss, filter_by_date, scrape_all_articles
from nlp_pipeline import process_nlp


# ============================================================
# Konfigurasi Streamlit
# ============================================================

st.set_page_config(
    page_title="📰 News Scraper & Analisis",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# Custom CSS
# ============================================================

st.markdown("""
<style>
    .stDataframe { font-size: 14px; }
    .sentiment-positif { color: #2ecc71; font-weight: bold; }
    .sentiment-negatif { color: #e74c3c; font-weight: bold; }
    .sentiment-netral  { color: #95a5a6; font-weight: bold; }
    .block-container { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# Sidebar — Input dan Filter
# ============================================================

st.sidebar.title("⚙️ Pencarian Berita")
st.sidebar.divider()

keyword = st.sidebar.text_input(
    "🔤 Keyword",
    placeholder="misal: bps kota surabaya",
    help="Masukkan kata kunci yang ingin dicari di Google News"
)

st.sidebar.divider()
st.sidebar.subheader("📅 Filter Tanggal")

filter_pilihan = st.sidebar.selectbox(
    "Pilih Rentang Tanggal",
    options=[
        "7 hari terakhir",
        "14 hari terakhir",
        "30 hari terakhir",
        "Bulan ini",
        "Custom (pilih tanggal manyal)"
    ]
)

hari_ini = datetime.now()

if filter_pilihan == "7 hari terakhir":
    from_date = hari_ini - timedelta(days=7)
    to_date = hari_ini

elif filter_pilihan == "14 hari terakhir":
    from_date = hari_ini - timedelta(days=14)
    to_date = hari_ini

elif filter_pilihan == "30 hari terakhir":
    from_date = hari_ini - timedelta(days=30)
    to_date = hari_ini

elif filter_pilihan == "Bulan ini":
    from_date = hari_ini.replace(day=1)
    to_date = hari_ini

else:  # Custom
    col_d1, col_d2 = st.sidebar.columns(2)
    from_date_input = col_d1.date_input("Dari", value=(hari_ini - timedelta(days=7)).date())
    to_date_input   = col_d2.date_input("Sampai", value=hari_ini.date())
    from_date = datetime.combine(from_date_input, datetime.min.time())
    to_date   = datetime.combine(to_date_input,   datetime.max.time())

# Validasi
date_valid = True
if from_date > to_date:
    st.sidebar.warning("⚠️ Tanggal 'Dari' tidak boleh lebih besar dari 'Sampai'.")
    date_valid = False

st.sidebar.divider()

# --- Toggle: Jalankan NLP? ---
jalankan_nlp = st.sidebar.toggle(
    "🧠 Jalankan Analisis NLP",
    value=True,
    help="Summarization, Sentiment Analysis, dan Topic Modelling. Butuh lebih lama."
)

# --- Tombol Cari ---
cari_btn = st.sidebar.button("🔍 Cari Berita", use_container_width=True, type="primary")


# ============================================================
# Main Area
# ============================================================

st.title("📰 News Scraper & Analisis Berita")
st.caption("Mengambil berita dari Google News, scraping full text, dan analisis NLP.")

# --- State Management: simpan hasil di session_state ---
if "df_result" not in st.session_state:
    st.session_state["df_result"] = None


# ============================================================
# Logika Utama — Triggered saat tombol Cari diklik
# ============================================================

if cari_btn:
    # Reset
    st.session_state["df_result"] = None

    # Validasi input
    if not keyword.strip():
        st.warning("⚠️ Tolong masukkan keyword terlebih dahulu.")
        st.stop()

    if not date_valid:
        st.error("⚠️ Perbaiki filter tanggal dulu.")
        st.stop()

    # ---------------------------------------------------------
    # STEP 1: Fetch dari Google News RSS
    # ---------------------------------------------------------
    with st.status("🔄 Mengambil berita dari Google News...", expanded=True) as status:

        rss_result = fetch_rss(keyword)

        if rss_result["error"]:
            st.error(rss_result["error"])
            st.stop()

        articles_raw = rss_result["articles"]
        st.write(f"   ✔️ Ditemukan **{len(articles_raw)} artikel** dari RSS.")

        # ---------------------------------------------------------
        # STEP 2: Filter berdasarkan tanggal
        # ---------------------------------------------------------
        articles_filtered = filter_by_date(articles_raw, from_date, to_date)
        st.write(f"   ✔️ Setelah filter tanggal: **{len(articles_filtered)} artikel**.")

        if len(articles_filtered) == 0:
            status.update(label="Selesai", state="error")
            st.info("ℹ️ Tidak ada berita yang sesuai dengan keyword dan filter tanggal. Coba ubah keyword atau perluas rentang tanggal.")
            st.stop()

        # ---------------------------------------------------------
        # STEP 3: Scraping full text dari setiap URL
        # ---------------------------------------------------------
        st.write("   🕐 Scraping full text dari setiap artikel...")
        articles_scraped = scrape_all_articles(articles_filtered, delay=1.0)

        # Hitung berapa yang berhasil di-scrape
        berhasil = sum(1 for a in articles_scraped if a["content"] and not a["content"].startswith("["))
        st.write(f"   ✔️ Full text berhasil di-extract dari **{berhasil}/{len(articles_scraped)} artikel**.")

        status.update(label="✅ Pengambilan data selesai!", state="complete")

    # ---------------------------------------------------------
    # STEP 4: NLP Pipeline (Opsional)
    # ---------------------------------------------------------
    if jalankan_nlp:
        st.info("🧠 Menjalankan analisis NLP... Ini mungkin membutuhkan beberapa menit untuk pertama kali (download model).")
        progress_bar = st.progress(0, text="Mempersiapkan NLP pipeline...")

        articles_final = process_nlp(articles_scraped, streamlit_progress=progress_bar)
        st.success("✅ Analisis NLP selesai!")
    else:
        articles_final = articles_scraped

    # ---------------------------------------------------------
    # STEP 5: Bangun DataFrame untuk ditampilkan
    # ---------------------------------------------------------
    rows = []
    for article in articles_final:
        tanggal = article.get("date")
        tanggal_str = tanggal.strftime("%d %b %Y, %H:%M") if tanggal else "-"

        row = {
            "Tanggal": tanggal_str,
            "Nama Media": article.get("source", "-"),
            "Judul Berita": article.get("title", "-"),
            "URL": article.get("url", "-"),
            "Jurnalis": article.get("journalist", "-") or "-",
            "Isi Berita": article.get("content", "-"),
        }

        # Tambahkan kolom NLP kalau sudah dijalankan
        if jalankan_nlp:
            row["Ringkasan"] = article.get("summary", "-")
            row["Topik/Isu"] = article.get("topics", "-")
            row["Sentimen"] = article.get("sentiment", "-")

        rows.append(row)

    df = pd.DataFrame(rows)
    st.session_state["df_result"] = df


# ============================================================
# Tampilan Hasil dan Download
# ============================================================

df = st.session_state.get("df_result")

if df is not None and len(df) > 0:

    st.divider()
    st.subheader(f"📋 Hasil: {len(df)} Berita Ditemukan")

    # --- Kolom untuk tampilan ringkas dan download ---
    col_info, col_dl1, col_dl2 = st.columns([3, 1, 1])

    col_info.write(f"Menampilkan **{len(df)}** artikel.")

    # Download CSV
    col_dl1.download_button(
        label="⬇️ Download CSV",
        data=df.to_csv(index=False, encoding="utf-8-sig"),  # utf-8-sig agar Excel baca UTF-8 dengan benar
        file_name="hasil_berita.csv",
        mime="text/csv",
        use_container_width=True
    )

    # Download Excel
    # to_excel() butuh writer (file/buffer), bukan langsung return bytes.
    # Pakai BytesIO sebagai buffer di memory.
    from io import BytesIO

    @st.cache_data
    def convert_df_to_xlsx(dataframe):
        buffer = BytesIO()
        dataframe.to_excel(buffer, index=False, engine="openpyxl")
        return buffer.getvalue()  # return bytes dari buffer

    col_dl2.download_button(
        label="⬇️ Download Excel",
        data=convert_df_to_xlsx(df),
        file_name="hasil_berita.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    st.divider()

    # --- Tabel Utama (kolom ringkas) ---
    # Pilih kolom yang ditampilkan di tabel utama agar tidak terlalu lebar
    if "Ringkasan" in df.columns:
        kolom_tampil = ["Tanggal", "Nama Media", "Judul Berita", "Ringkasan", "Topik/Isu", "Sentimen", "URL"]
    else:
        kolom_tampil = ["Tanggal", "Nama Media", "Judul Berita", "URL"]

    st.dataframe(
        df[kolom_tampil],
        use_container_width=True,
        hide_index=True,
        column_config={
            "URL": st.column_config.LinkColumn("URL", help="Klik untuk buka artikel"),
            "Ringkasan": st.column_config.TextColumn("Ringkasan", width="large"),
            "Isi Berita": st.column_config.TextColumn("Isi Berita", width="large"),
        }
    )

    # --- Detail per Artikel (Expander) ---
    st.divider()
    st.subheader("📄 Detail Artikel")

    for i, row in df.iterrows():
        with st.expander(f"{row['Tanggal']}  |  {row['Nama Media']}  |  {row['Judul Berita']}", expanded=False):

            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"**📰 Judul:** {row['Judul Berita']}")
                st.markdown(f"**🗞️ Media:** {row['Nama Media']}")
                st.markdown(f"**📅 Tanggal:** {row['Tanggal']}")
                if row.get("Jurnalis", "-") != "-":
                    st.markdown(f"**✍️ Jurnalis:** {row['Jurnalis']}")
                st.markdown(f"**🔗 URL:** [{row['URL']}]({row['URL']})")

            with col2:
                if "Sentimen" in row:
                    sentimen = row["Sentimen"]
                    emoji = "🟢" if sentimen == "Positif" else ("🔴" if sentimen == "Negatif" else "⚪")
                    st.markdown(f"**Sentimen:** {emoji} {sentimen}")
                if "Topik/Isu" in row:
                    st.markdown(f"**Topik:** {row['Topik/Isu']}")

            st.divider()

            if "Ringkasan" in row and row["Ringkasan"] != "-":
                st.markdown("📝 **Ringkasan:**")
                st.write(row["Ringkasan"])

            st.markdown("📖 **Isi Berita (Full):**")
            st.write(row["Isi Berita"])

else:
    # Tampilan awal sebelum pencarian
    st.info("👈 Masukkan keyword dan pilih filter tanggal di sidebar, lalu klik **Cari Berita**.")

    st.divider()
    st.markdown("""
    ### 💡 Tips Penggunaan
    - Coba keyword seperti: `inflasi Surabaya`, `UMKM Jawa Timur`, `ekspor Indonesia`
    - Untuk hasil terbaik, gunakan keyword dalam **Bahasa Indonesia**
    - Toggle **Analisis NLP** untuk mendapatkan ringkasan, sentimen, dan topik
    - Pertama kali jalankan NLP mungkin lebih lama karena perlu download model (~1-2 GB)
    """)