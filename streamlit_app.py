import streamlit as st
import zipfile
import os
import tempfile
from lxml import etree
from io import BytesIO

# Daftar prefix resmi yang ingin dipertahankan
VALID_PREFIXES = {"kml", "gx"}

# === Tree-based cleaner aman ===
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

# === Bersihkan KML ===
def clean_kml_file(input_path, output_path):
    parser = etree.XMLParser(remove_blank_text=True, recover=True)
    tree = etree.parse(input_path, parser)
    root = tree.getroot()

    # Bersihkan prefix/atribut tak dikenal
    remove_bad_prefixes_tree(root)

    tree.write(output_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")

# === Bersihkan KMZ ===
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

        # Bungkus ulang jadi KMZ
        with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as zf:
            for folder, _, files in os.walk(extract_dir):
                for file in files:
                    file_path = os.path.join(folder, file)
                    arcname = os.path.relpath(file_path, extract_dir)
                    zf.write(file_path, arcname)

# === Fungsi extract Placemark aman dari ValueError ===
def extract_placemarks(kmz_bytes):
    import xml.etree.ElementTree as ET
    def recurse_folder(folder, ns, path=""):
        items = []
        name_el = folder.find("kml:name", ns)
        folder_name = name_el.text.upper() if name_el is not None else "UNKNOWN"
        new_path = f"{path}/{folder_name}" if path else folder_name
        for sub in folder.findall("kml:Folder", ns):
            items += recurse_folder(sub, ns, new_path)
        for pm in folder.findall("kml:Placemark", ns):
            nm = pm.find("kml:name", ns)
            coord = pm.find(".//kml:coordinates", ns)
            if nm is not None and coord is not None and coord.text and coord.text.strip():
                parts = coord.text.strip().split(",")
                if len(parts) >= 2:
                    try:
                        lon, lat = map(float, parts[:2])
                        items.append({
                            "name": nm.text.strip(),
                            "lat": lat,
                            "lon": lon,
                            "path": new_path
                        })
                    except ValueError:
                        # Koordinat tidak valid, skip
                        continue
        return items

    with zipfile.ZipFile(BytesIO(kmz_bytes)) as z:
        f = [f for f in z.namelist() if f.lower().endswith(".kml")][0]
        root = ET.parse(z.open(f)).getroot()
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        all_pm = []
        for folder in root.findall(".//kml:Folder", ns):
            all_pm += recurse_folder(folder, ns)
        return all_pm

# === Streamlit App ===
st.title("🗺️ KMZ Cleaner Aman + Koordinat Valid")

uploaded_file = st.file_uploader("Upload file KMZ", type=["kmz"])

if uploaded_file:
    output_kml = "clean_output.kml"
    output_kmz = "clean_output.kmz"

    if st.button("🚀 Bersihkan"):
        try:
            kmz_bytes = uploaded_file.read()
            clean_kmz(kmz_bytes, output_kml, output_kmz)

            st.success("✅ File berhasil dibersihkan tanpa unbound prefix!")

            # Test extract koordinat aman
            placemarks = extract_placemarks(kmz_bytes)
            st.write(f"Jumlah Placemark valid: {len(placemarks)}")

            with open(output_kml, "rb") as f:
                st.download_button("⬇️ Download KML Bersih", f, file_name="clean.kml")

            with open(output_kmz, "rb") as f:
                st.download_button("⬇️ Download KMZ Bersih", f, file_name="clean.kmz")

        except Exception as e:
            st.error(f"Gagal memproses: {e}")
