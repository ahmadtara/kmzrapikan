import streamlit as st
import zipfile
import os
import shutil
import re
from lxml import etree
import tempfile

# === Pembersih raw XML dari prefix/namespace nyasar ===
def strip_bad_prefixes(xml_bytes: bytes) -> bytes:
    """
    Bersihkan elemen/atribut dengan prefix tak dikenal (gx:, ns1:, dll).
    """
    # Hapus prefix di tag secara mentah pakai regex
    # Contoh: <ns1:fovy> → <fovy>
    cleaned = re.sub(rb"</?\w+:(\w+)", rb"<\1", xml_bytes)

    # Hapus atribut dengan prefix ns1: atau gx:
    cleaned = re.sub(rb"\s+\w+:\w+=\"[^\"]*\"", b"", cleaned)

    return cleaned

def clean_kml_file(input_path, output_path):
    with open(input_path, "rb") as f:
        raw = f.read()

    cleaned = strip_bad_prefixes(raw)

    parser = etree.XMLParser(remove_blank_text=True, recover=True)
    tree = etree.fromstring(cleaned, parser=parser)

    with open(output_path, "wb") as f:
        f.write(etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding="UTF-8"))

# === Fungsi pembersih tree sebagai backup ===
def clean_namespaces(elem):
    if isinstance(elem.tag, str) and ":" in elem.tag:
        elem.tag = elem.tag.split(":")[-1]
    bad_attrs = [a for a in elem.attrib if ":" in a]
    for a in bad_attrs:
        new_key = a.split(":")[-1]
        elem.attrib[new_key] = elem.attrib[a]
        del elem.attrib[a]
    for child in elem:
        clean_namespaces(child)
    return elem

# === Fungsi utama untuk membersihkan KMZ ===
def clean_kmz(kmz_bytes, output_kml, output_kmz):
    with tempfile.TemporaryDirectory() as extract_dir:
        tmp_kmz = os.path.join(extract_dir, "uploaded.kmz")
        with open(tmp_kmz, "wb") as f:
            f.write(kmz_bytes)

        # Ekstrak KMZ
        with zipfile.ZipFile(tmp_kmz, 'r') as kmz:
            kmz.extractall(extract_dir)

        # Cari file KML
        main_kml = None
        for root, dirs, files in os.walk(extract_dir):
            for f in files:
                if f.endswith(".kml"):
                    main_kml = os.path.join(root, f)
                    break
            if main_kml:
                break

        if not main_kml:
            raise FileNotFoundError("Tidak ada file .kml di dalam KMZ")

        # Bersihkan KML
        clean_kml_file(main_kml, output_kml)

        # Backup cleanup tree tambahan
        parser = etree.XMLParser(remove_blank_text=True, recover=True)
        tree_root = etree.parse(output_kml, parser).getroot()
        clean_namespaces(tree_root)
        etree.ElementTree(tree_root).write(output_kml, pretty_print=True, xml_declaration=True, encoding="UTF-8")

        # Bungkus ulang jadi KMZ
        with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as zf:
            # Tambahkan semua file dari extract_dir agar struktur folder KMZ tetap
            for folder, _, files in os.walk(extract_dir):
                for file in files:
                    file_path = os.path.join(folder, file)
                    arcname = os.path.relpath(file_path, extract_dir)
                    zf.write(file_path, arcname)

# === Streamlit App ===
st.title("🗺️ Pembersih KMZ dari Namespace Nyasar")

uploaded_file = st.file_uploader("Upload file KMZ", type=["kmz"])

if uploaded_file:
    output_kml = "clean_output.kml"
    output_kmz = "clean_output.kmz"

    if st.button("🚀 Bersihkan"):
        try:
            clean_kmz(uploaded_file.read(), output_kml, output_kmz)
            st.success("✅ File berhasil dibersihkan!")

            with open(output_kml, "rb") as f:
                st.download_button("⬇️ Download KML Bersih", f, file_name="clean.kml")

            with open(output_kmz, "rb") as f:
                st.download_button("⬇️ Download KMZ Bersih", f, file_name="clean.kmz")

        except Exception as e:
            st.error(f"Gagal memproses: {e}")
