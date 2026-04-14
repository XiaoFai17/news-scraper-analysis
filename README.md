## Buat venv
python -m venv venv

## Aktifkan venv
.\venv\Scripts\activate

## Install library
pip install -r requirements.txt

## Run app
streamlit run app.py

---

## Alur Kerja Program (Arsitektur)
Program ini terdiri dari tiga komponen utama (file Python) yang saling bekerja sama untuk menghasilkan web app scraper dan analisis berita:

1. **`app.py` (Antarmuka Pengguna & Pengendali Utama)**
   Ini adalah file utama yang menjalankan aplikasi web berbasis **Streamlit**. File ini bertanggung jawab untuk menampilkan UI (User Interface) kepada pengguna, seperti kolom input *keyword*, filter tanggal, dan tombol untuk memulai pencarian. Saat pengguna mengklik tombol "Cari Berita", `app.py` akan bertindak sebagai pengatur (controller) yang memanggil fungsi-fungsi dari `scraper.py` untuk mengambil data teks, lalu mengirimkan data tersebut ke `nlp_pipeline.py` untuk dianalisis kecerdasan buatan (NLP), dan pada akhirnya membangun tabel *dataframe* (via `pandas`) untuk ditampilkan kembali ke layar pengguna beserta opsi unduhan (CSV/Excel).

2. **`scraper.py` (Mesin Pencari & Pengambil Data)**
   File ini menangani semua proses yang berkaitan dengan pengumpulan data artikel dari internet. Modul ini dipanggil oleh `app.py` dengan alur:
   - `fetch_rss`: Mencari berita tahap awal di Google News menggunakan *library* `gnews` berdasarkan *keyword*. Mem-parsing metadata seperti tanggal dan sumber media.
   - `filter_by_date`: Melakukan *filtering* artikel agar sesuai dengan rentang tanggal yang dipatok.
   - `resolve_google_news_url_selenium`: Mengubah URL redirect bawaan Google News menjadi URL asli situs media dengan bantuan *Virtual Browser* (**Selenium**).  
   - `scrape_full_text` & `scrape_all_articles`: Mengunjungi URL asli berita tersebut dan menarik isi teks utuh (*full text*) serta *author* / jurnalis pembuatnya. Proses ekstraksi teks utamanya menggunakan `newspaper3k`, dan jika gagal akan menggunakan *fallback* ke `BeautifulSoup` + **Selenium**. Total hasil *scraping* teks dikembalikan ke `app.py`.

3. **`nlp_pipeline.py` (Pemroses Bahasa Alami / AI)**
   File ini memuat logika analitis (*Natural Language Processing*) terhadap isi teks berita. Jika di UI pengguna mengaktifkan saklar "Jalankan Analisis NLP", `app.py` akan mengoper seluruh artikel ke dalam fungsi `process_nlp` yang ada di sini untuk diperkaya dengan tiga jenis analisis utama:
   - **Summarization** (`summarize_text`): Membuat ringkasan kalimat pendek dari panjangnya keseluruhan berita dengan model Deep Learning `facebook/bart-large-cnn`.
   - **Sentiment Analysis** (`analyze_sentiment`): Menentukan apakah nada penulisan berita tersebut bernilai **Positif, Negatif, atau Netral** menggunakan model `indonesian-roberta`.
   - **Topic Modelling** (`extract_topics`): Mengekstrak kata kunci esensial/topik unggulan berbasis perhitungan bobot kata **TF-IDF**.
   Selesai diperhitungkan, seluruh _insight_ ini ditanamkan ke dalam data artikel dan dikirim balik kepada `app.py` untuk divisualisasikan.