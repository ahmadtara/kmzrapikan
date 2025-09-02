import streamlit as st
import zipfile
import os
import shutil
import re
from lxml import etree
import tempfile

# Daftar prefix resmi yang ingin dipertahankan
VALID_PREFIXES = {"kml", "gx"}

# === Pembersih raw XML dari unbound prefix ===
def strip_only_bad_prefixes(xml_bytes: bytes) -> bytes:
    """
    Bersihkan elemen/atribut dengan prefix tak dikenal (bukan kml: atau gx:).
    """
    # Hapus tag dengan prefix tak dikenal, tetap pertahankan yang valid
    def repl_tag_start(match):
        prefix, tag = match.group(1).decode(), match.group(2).decode()
        if prefix in VALID_PREFIXES:
            return f"<{prefix}:{tag}>".encode()
        else:
            return f"<{tag}>".encode()

    def repl_tag_end(match):
        prefix, tag = match.group(1).decode(), match.group(2).decode()
        if prefix in VALID_PREFIXES:
            return f"</{prefix}:{tag}>".encode()
        else:
            return f"</{tag}>".encode()

    xml_bytes = re.sub(rb"<(\w+):(\w+)>", repl_tag_start, xml_bytes)
    xml_bytes = re.sub(rb"</(\w+):(\w+)>", repl_tag_end, xml_bytes)

    # Hapus atribut dengan prefix tak dikenal
    def repl_attr(match):
        prefix = match.group(1).decode()
        if prefix in VALID_PREFIXES:
            return match.group(0)
        else:
            return b""

    xml_bytes = re.sub(rb'\s+(\w+):(\w+)="[^"]*"', repl_attr, xml_bytes)

    return xml_bytes

# === Fungsi pembersih tree backup ===
def clean_namespaces(elem):
    """
    Membersihkan sisa prefix tak dikenal dari tree lxml.
    """
    if isinstance(elem.tag, str) and ":" in elem.tag:
        prefix = elem.tag.split(":")[0]
        if prefix not in VALID_PREFIXES:
            elem.tag = elem.tag.split(":")[-1]  # hapus prefix tak dikenal

    bad_attrs = [a for a in elem.attrib if ":" in a and a.split(":")[0] not in VALID_PREFIXES]
    for a in bad_attrs:
        new_key = a.split(":")[-1]
        elem.attrib[new_key] = elem.attrib[a]
        del elem.attrib[a]

    for child in elem:
        clean_namespaces(child)

    return elem

# === Fungsi untuk membersihkan file KML ===
def clean_kml_file(input_path, output_path):
    with open(input_path, "rb") as f:
        raw = f.read()

    cleaned = strip_only_bad_prefixes(raw)

    parser = etree.XMLParser(remove_blank_text=True, recover=True)
    tree = etree.fromstring(cleaned, parser=parser)

    # Backup pembersihan tree
    clean_namespaces(tree)

    with open(output_path, "wb") as f:
        f.write(etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding="UTF-8"))

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

        # Bungkus ulang jadi KMZ, tetap pertahankan semua file
        with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as zf:
            for folder, _, files in os.walk(extract_dir):
                for file in files:
                    file_path = os.path.join(folder, file)
                    arcname = os.path.relpath(file_path, extract_dir)
                    zf.write(file_path, arcname)

# === Streamlit App ===
st.title("🗺️ Pembersih KMZ Aman dari Unbound Prefix")

uploaded_file = st.file_uploader("Upload file KMZ", type=["kmz"])

if uploaded_file:
    output_kml = "clean_output.kml"
    output_kmz = "clean_output.kmz"

    if st.button("🚀 Bersihkan"):
        try:
            clean_kmz(uploaded_file.read(), output_kml, output_kmz)
            st.success("✅ File berhasil dibersihkan tanpa unbound prefix!")

            with open(output_kml, "rb") as f:
                st.download_button("⬇️ Download KML Bersih", f, file_name="clean.kml")

            with open(output_kmz, "rb") as f:
                st.download_button("⬇️ Download KMZ Bersih", f, file_name="clean.kmz")

        except Exception as e:
            st.error(f"Gagal memproses: {e}")
