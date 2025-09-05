import streamlit as st
import zipfile
import os
import tempfile
from lxml import etree

# Daftar prefix resmi yang ingin dipertahankan
VALID_PREFIXES = {"kml", "gx", "atom"}

# === Fungsi pembersih tree aman ===
def remove_bad_prefixes_tree(elem, valid_prefixes=VALID_PREFIXES):
    """
    Hapus atribut dan tag dengan prefix tak dikenal, tetap pertahankan default namespace.
    """
    # Hapus atribut tak dikenal
    for attr in list(elem.attrib):
        if ":" in attr:
            prefix = attr.split(":")[0]
            if prefix not in valid_prefixes:
                del elem.attrib[attr]

    # Hapus prefix tak dikenal di tag
    if isinstance(elem.tag, str):
        if "}" in elem.tag:
            # Tag dengan default namespace, biarkan
            pass
        elif ":" in elem.tag:
            prefix = elem.tag.split(":")[0]
            if prefix not in valid_prefixes:
                elem.tag = elem.tag.split(":")[-1]

    # Rekursif ke child
    for child in elem:
        remove_bad_prefixes_tree(child, valid_prefixes)

# === Fungsi membersihkan KML ===
def clean_kml_file(input_path, output_path):
    parser = etree.XMLParser(remove_blank_text=True, recover=True)
    tree = etree.parse(input_path, parser)
    root = tree.getroot()

    # Bersihkan prefix/atribut tak dikenal
    remove_bad_prefixes_tree(root)

    # === Tambahkan namespace resmi ke root <kml> ===
    if root.tag.endswith("kml") or root.tag.endswith("}kml"):
        nsmap = root.nsmap.copy()

        # namespace default KML
        if None not in nsmap:
            root.set("xmlns", "http://www.opengis.net/kml/2.2")
        # gx (Google extension)
        if "gx" not in nsmap:
            root.set("xmlns:gx", "http://www.google.com/kml/ext/2.2")
        # atom (kadang dipakai di <atom:author> / <atom:link>)
        if "atom" not in nsmap:
            root.set("xmlns:atom", "http://www.w3.org/2005/Atom")

    tree.write(output_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")

# === Fungsi utama membersihkan KMZ ===
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
            raise FileNotFoundError("Tidak ada file .kml di dalam KMZ")

        # Bersihkan KML
        clean_kml_file(main_kml, output_kml)

        # Bungkus ulang jadi KMZ (pertahankan semua file)
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
