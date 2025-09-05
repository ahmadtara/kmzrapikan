import streamlit as st
import zipfile
import os
import re
import tempfile

# --- Fungsi pembersih raw XML ---
def clean_raw_xml(raw_xml: bytes) -> bytes:
    """
    Bersihkan deklarasi namespace aneh & prefix asing dari XML,
    tapi pertahankan isi Placemark, Polygon, LineString, dll.
    """
    # Hapus semua deklarasi xmlns selain default & gx
    raw_xml = re.sub(rb'\s+xmlns:(?!gx)[a-zA-Z0-9_]+="[^"]*"', b"", raw_xml)

    # Hapus prefix asing dari tag (contoh: ns2:Placemark -> Placemark)
    raw_xml = re.sub(rb"<(/?)[a-zA-Z0-9_]+:", rb"<\1", raw_xml)

    # Hapus prefix asing dari atribut (contoh: ns2:id="x" -> id="x")
    raw_xml = re.sub(rb"\s+[a-zA-Z0-9_]+:([a-zA-Z0-9_]+=)", rb" \1", raw_xml)

    return raw_xml

# --- Fungsi utama untuk bersihkan KMZ ---
def clean_kmz(kmz_bytes, output_kml, output_kmz):
    with tempfile.TemporaryDirectory() as extract_dir:
        tmp_kmz = os.path.join(extract_dir, "uploaded.kmz")
        with open(tmp_kmz, "wb") as f:
            f.write(kmz_bytes)

        # Ekstrak KMZ
        with zipfile.ZipFile(tmp_kmz, 'r') as kmz:
            kmz.extractall(extract_dir)

        # Cari file KML utama
        main_kml = None
        for root, dirs, files in os.walk(extract_dir):
            for f in files:
                if f.endswith(".kml"):
                    main_kml = os.path.join(root, f)
                    break
            if main_kml:
                break

        if not main_kml:
            raise FileNotFoundError("❌ Tidak ada file .kml di dalam KMZ")

        # Baca & bersihkan raw xml
        with open(main_kml, "rb") as f:
            raw_xml = f.read()

        cleaned = clean_raw_xml(raw_xml)

        # Tambahkan namespace standar di root <kml>
        cleaned = re.sub(
            rb"<kml[^>]*>",
            b'<kml xmlns="http://www.opengis.net/kml/2.2" '
            b'xmlns:gx="http://www.google.com/kml/ext/2.2">',
            cleaned,
            count=1
        )

        # Simpan hasil KML
        with open(output_kml, "wb") as f:
            f.write(cleaned)

        # Bungkus ulang jadi KMZ (replace KML lama dengan yang sudah bersih)
        with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as zf:
            for folder, _, files in os.walk(extract_dir):
                for file in files:
                    file_path = os.path.join(folder, file)
                    arcname = os.path.relpath(file_path, extract_dir)
                    if file_path == main_kml:
                        zf.write(output_kml, arcname)  # tulis versi bersih
                    else:
                        zf.write(file_path, arcname)

# --- Streamlit App ---
st.title("🗺️ Pembersih KMZ Kotor → Jadi Bersih")

uploaded_file = st.file_uploader("Upload file KMZ kotor", type=["kmz"])

if uploaded_file:
    output_kml = "clean_output.kml"
    output_kmz = "clean_output.kmz"

    if st.button("🚀 Bersihkan"):
        try:
            clean_kmz(uploaded_file.read(), output_kml, output_kmz)
            st.success("✅ File berhasil dibersihkan tanpa merusak isi")

            with open(output_kml, "rb") as f:
                st.download_button("⬇️ Download KML Bersih", f, file_name="clean.kml")

            with open(output_kmz, "rb") as f:
                st.download_button("⬇️ Download KMZ Bersih", f, file_name="clean.kmz")

        except Exception as e:
            st.error(f"Gagal memproses: {e}")
