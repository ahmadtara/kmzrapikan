import streamlit as st
import zipfile
import os
import tempfile
import re
from lxml import etree

# ==============================
# TREE-BASED CLEANER (DWG-safe)
# ==============================
VALID_PREFIXES = {"kml", "gx", "atom"}

def remove_bad_prefixes_tree(elem, valid_prefixes=VALID_PREFIXES):
    # Hapus atribut tak dikenal
    for attr in list(elem.attrib):
        if ":" in attr:
            prefix = attr.split(":")[0]
            if prefix not in valid_prefixes:
                del elem.attrib[attr]

    # Hapus prefix tak dikenal di tag
    if isinstance(elem.tag, str):
        if "}" in elem.tag:
            pass  # default namespace aman
        elif ":" in elem.tag:
            prefix = elem.tag.split(":")[0]
            if prefix not in valid_prefixes:
                elem.tag = elem.tag.split(":")[-1]

    # Rekursif ke anak
    for child in elem:
        remove_bad_prefixes_tree(child, valid_prefixes)

# ==============================
# RAW XML CLEANER (HPDB-safe)
# ==============================
def clean_raw_xml_for_hpdb(raw_xml: bytes) -> bytes:
    # Hapus semua xmlns:xxx
    raw_xml = re.sub(rb'\s+xmlns:[a-zA-Z0-9_]+="[^"]*"', b"", raw_xml)
    # Hapus prefix dari tag (kecuali <coordinates>)
    raw_xml = re.sub(rb"<(/?)([a-zA-Z0-9_]+:)?(coordinates)", rb"<\1\3", raw_xml)
    raw_xml = re.sub(rb"<(/?)([a-zA-Z0-9_]+:)(\w+)", rb"<\1\3", raw_xml)
    # Hapus atribut dengan prefix
    raw_xml = re.sub(rb"\s+[a-zA-Z0-9_]+:\w+=\"[^\"]*\"", b"", raw_xml)
    return raw_xml

# ==============================
# CLEAN KML
# ==============================
def clean_kml_file(input_path, output_path):
    # Baca raw
    with open(input_path, "rb") as f:
        raw_xml = f.read()
    raw_xml = clean_raw_xml_for_hpdb(raw_xml)

    parser = etree.XMLParser(remove_blank_text=True, recover=True)
    root = etree.fromstring(raw_xml, parser)

    # Tree-based cleaning (DWG-safe)
    remove_bad_prefixes_tree(root)

    # Simpan
    tree = etree.ElementTree(root)
    tree.write(output_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")

# ==============================
# CLEAN KMZ
# ==============================
def clean_kmz(kmz_bytes, output_kml, output_kmz):
    with tempfile.TemporaryDirectory() as extract_dir:
        tmp_kmz = os.path.join(extract_dir, "uploaded.kmz")
        with open(tmp_kmz, "wb") as f:
            f.write(kmz_bytes)

        # Ekstrak KMZ
        with zipfile.ZipFile(tmp_kmz, 'r') as kmz:
            kmz.extractall(extract_dir)

        # Cari KML utama
        main_kml = None
        for root_dir, dirs, files in os.walk(extract_dir):
            for f in files:
                if f.lower().endswith(".kml"):
                    main_kml = os.path.join(root_dir, f)
                    break
            if main_kml:
                break

        if not main_kml:
            raise FileNotFoundError("Tidak ada file .kml di dalam KMZ")

        # Bersihkan KML
        clean_kml_file(main_kml, output_kml)

        # Bungkus ulang KMZ
        with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as zf:
            for folder, _, files in os.walk(extract_dir):
                for file in files:
                    file_path = os.path.join(folder, file)
                    arcname = os.path.relpath(file_path, extract_dir)
                    zf.write(file_path, arcname)

# ==============================
# STREAMLIT APP
# ==============================
st.title("🗺️ KMZ Cleaner Aman HPDB & DWG")

uploaded_file = st.file_uploader("Upload KMZ", type=["kmz"])

if uploaded_file:
    output_kml = "clean_output.kml"
    output_kmz = "clean_output.kmz"

    if st.button("🚀 Bersihkan"):
        try:
            kmz_bytes = uploaded_file.read()
            clean_kmz(kmz_bytes, output_kml, output_kmz)
            st.success("✅ File berhasil dibersihkan untuk HPDB & DWG")

            with open(output_kml, "rb") as f:
                st.download_button("⬇️ Download KML Bersih", f, file_name="clean.kml")

            with open(output_kmz, "rb") as f:
                st.download_button("⬇️ Download KMZ Bersih", f, file_name="clean.kmz")

        except Exception as e:
            st.error(f"Gagal memproses: {e}")
