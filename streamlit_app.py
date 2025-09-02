import streamlit as st
import zipfile
import os
import shutil
import re
from lxml import etree

# === Pembersih raw XML dari prefix/namespace nyasar ===
def clean_raw_xml(raw_xml: bytes) -> bytes:
    # Hapus semua deklarasi xmlns:xxx="..."
    raw_xml = re.sub(rb'\s+xmlns:[a-zA-Z0-9_]+="[^"]*"', b"", raw_xml)
    # Hapus semua prefix xxx: dari tag/atribut
    raw_xml = re.sub(rb"\b[a-zA-Z0-9_]+:", b"", raw_xml)
    return raw_xml

# === Fungsi pembersih tree (backup kalau masih ada sisa) ===
def clean_namespaces(elem):
    if isinstance(elem.tag, str) and ":" in elem.tag:
        elem.tag = elem.tag.split(":")[-1]  # buang prefix
    bad_attrs = [a for a in elem.attrib if ":" in a]
    for a in bad_attrs:
        new_key = a.split(":")[-1]
        elem.attrib[new_key] = elem.attrib[a]
        del elem.attrib[a]
    for child in elem:
        clean_namespaces(child)
    return elem

# === Fungsi utama ===
def clean_kmz(kmz_bytes, output_kml, output_kmz):
    extract_dir = "temp_extract"
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    os.makedirs(extract_dir, exist_ok=True)

    tmp_kmz = "uploaded.kmz"
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

    # Baca dan bersihkan raw XML
    with open(main_kml, "rb") as f:
        raw_xml = f.read()
    raw_xml = clean_raw_xml(raw_xml)

    parser = etree.XMLParser(remove_blank_text=True, recover=True)
    root = etree.fromstring(raw_xml, parser)
    clean_namespaces(root)

    # Simpan KML bersih
    tree = etree.ElementTree(root)
    tree.write(output_kml, pretty_print=True, xml_declaration=True, encoding="UTF-8")

    # Bungkus ulang jadi KMZ
    with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(output_kml, os.path.basename(output_kml))

    shutil.rmtree(extract_dir)
    os.remove(tmp_kmz)

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
