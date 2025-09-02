import streamlit as st
import zipfile
import os
import shutil
from lxml import etree

# Fungsi pembersih namespace
def clean_namespaces(elem):
    if isinstance(elem.tag, str) and (elem.tag.startswith("ns1:") or elem.tag.startswith("gx:")):
        return None
    bad_attrs = [a for a in elem.attrib if a.startswith("ns1:") or a.startswith("gx:")]
    for a in bad_attrs:
        del elem.attrib[a]
    to_remove = []
    for child in elem:
        cleaned = clean_namespaces(child)
        if cleaned is None:
            to_remove.append(child)
    for child in to_remove:
        elem.remove(child)
    return elem

def clean_kmz(kmz_bytes, output_kml, output_kmz):
    extract_dir = "temp_extract"
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    os.makedirs(extract_dir, exist_ok=True)

    # Simpan upload sebagai sementara
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

    parser = etree.XMLParser(remove_blank_text=True, recover=True)
    tree = etree.parse(main_kml, parser)
    root = tree.getroot()
    clean_namespaces(root)

    # Simpan KML bersih
    tree.write(output_kml, pretty_print=True, xml_declaration=True, encoding="UTF-8")

    # Bungkus ulang jadi KMZ
    with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(output_kml, os.path.basename(output_kml))

    shutil.rmtree(extract_dir)
    os.remove(tmp_kmz)

# === Streamlit App ===
st.title("🗺️ Pembersih KMZ KML Namespace")

uploaded_file = st.file_uploader("Upload file KMZ", type=["kmz"])

if uploaded_file:
    output_kml = "clean_output.kml"
    output_kmz = "clean_output.kmz"

    if st.button("Bersihkan"):
        clean_kmz(uploaded_file.read(), output_kml, output_kmz)

        with open(output_kml, "rb") as f:
            st.download_button("⬇️ Download KML Bersih", f, file_name="clean.kml")

        with open(output_kmz, "rb") as f:
            st.download_button("⬇️ Download KMZ Bersih", f, file_name="clean.kmz")
