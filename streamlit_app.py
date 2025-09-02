import streamlit as st
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO

# Namespace standar KML
KML_NS = "http://www.opengis.net/kml/2.2"
ET.register_namespace("", KML_NS)

def parse_kml_from_kmz(kmz_bytes):
    with zipfile.ZipFile(BytesIO(kmz_bytes), "r") as kmz:
        with kmz.open("doc.kml") as kml_file:
            tree = ET.parse(kml_file)
            return tree

def build_new_kml(hp_list, pole_list):
    kml = ET.Element("{%s}kml" % KML_NS)
    document = ET.SubElement(kml, "Document")

    # HP COVER A/B/C/D
    for key, elements in hp_list.items():
        folder = ET.SubElement(document, "Folder")
        ET.SubElement(folder, "name").text = f"HP COVER {key.upper()}"
        for el in elements:
            folder.append(el)

    # LINE A/B/C/D
    for key, elements in pole_list.items():
        folder = ET.SubElement(document, "Folder")
        ET.SubElement(folder, "name").text = f"LINE {key.upper()}"
        for el in elements:
            folder.append(el)

    return ET.ElementTree(kml)

def clean_and_group(tree):
    root = tree.getroot()
    hp_list = {"a": [], "b": [], "c": [], "d": []}
    pole_list = {"a": [], "b": [], "c": [], "d": []}

    # Cari semua Placemark
    for pm in root.findall(".//{%s}Placemark" % KML_NS):
        name_el = pm.find("{%s}name" % KML_NS)
        if name_el is None or not name_el.text:
            continue
        name = name_el.text.lower()

        # Grouping HP
        if "hp" in name:
            for key in hp_list.keys():
                if key in name:
                    hp_list[key].append(pm)
                    break

        # Grouping POLE
        if "pole" in name:
            for key in pole_list.keys():
                if key in name:
                    pole_list[key].append(pm)
                    break

    return hp_list, pole_list

def update_kmz(kmz_bytes, new_kml_tree):
    # simpan doc.kml baru ke buffer
    new_kml_bytes = BytesIO()
    new_kml_tree.write(new_kml_bytes, encoding="utf-8", xml_declaration=True)

    out_buffer = BytesIO()
    with zipfile.ZipFile(BytesIO(kmz_bytes), "r") as old_kmz:
        with zipfile.ZipFile(out_buffer, "w") as new_kmz:
            for item in old_kmz.infolist():
                if item.filename != "doc.kml":
                    new_kmz.writestr(item, old_kmz.read(item.filename))
            # tulis doc.kml baru
            new_kmz.writestr("doc.kml", new_kml_bytes.getvalue())

    return out_buffer.getvalue()

# ================== STREAMLIT APP ==================

st.title("📂 KMZ Rapikan HP & POLE")

uploaded_file = st.file_uploader("Upload file KMZ", type=["kmz"])

if uploaded_file:
    kmz_bytes = uploaded_file.read()

    # Parse doc.kml
    tree = parse_kml_from_kmz(kmz_bytes)

    # Bersihkan & Group
    hp_list, pole_list = clean_and_group(tree)

    # Bangun KML baru
    new_kml_tree = build_new_kml(hp_list, pole_list)

    # Update ke KMZ lama
    new_kmz_bytes = update_kmz(kmz_bytes, new_kml_tree)

    st.success("KMZ berhasil dirapikan ✅")

    st.download_button(
        "⬇️ Download KMZ hasil",
        data=new_kmz_bytes,
        file_name="rapikan.kmz",
        mime="application/vnd.google-earth.kmz"
    )
