import streamlit as st
import zipfile
import os
import tempfile
from lxml import etree as ET
from shapely.geometry import Point, Polygon

st.title("📌 KMZ Tools")

# === MENU ===
menu = st.sidebar.radio("Pilih Fitur", ["Rapikan HP ke Boundary", "Generate Kotak Rumah"])

uploaded_file = st.file_uploader("Upload file KMZ", type=["kmz"])

# ==== FUNGSI UTIL ====
def get_coordinates(coord_text):
    coords = []
    for c in coord_text.strip().split():
        lon, lat, *_ = map(float, c.split(","))
        coords.append((lon, lat))
    return coords

def create_house_box(lon, lat, size_x=0.00005, size_y=0.00005):
    """Buat kotak rumah di sekitar titik koordinat"""
    return [
        (lon - size_x, lat - size_y),
        (lon - size_x, lat + size_y),
        (lon + size_x, lat + size_y),
        (lon + size_x, lat - size_y),
        (lon - size_x, lat - size_y),
    ]

# ==== LOGIC ====
if uploaded_file is not None:
    # Simpan file sementara
    with tempfile.NamedTemporaryFile(delete=False, suffix=".kmz") as tmp:
        tmp.write(uploaded_file.read())
        kmz_file = tmp.name

    st.success(f"✅ File berhasil diupload: {uploaded_file.name}")

    # ==== Extract KMZ ====
    extract_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(kmz_file, 'r') as z:
        z.extractall(extract_dir)
        files = z.namelist()
        kml_name = next((f for f in files if f.lower().endswith(".kml")), None)

    if kml_name is None:
        st.error("❌ Tidak ada file .kml di dalam KMZ")
    else:
        kml_file = os.path.join(extract_dir, kml_name)
        parser = ET.XMLParser(recover=True, encoding="utf-8")
        tree = ET.parse(kml_file, parser=parser)
        root = tree.getroot()
        ns = {"kml": "http://www.opengis.net/kml/2.2"}

        # ==== MENU 1: Rapikan HP ke Boundary ====
        if menu == "Rapikan HP ke Boundary":
            # ... (kode existing kamu paste di sini persis)

            # ==== Simpan hasil ====
            new_kml = os.path.join(extract_dir, "output.kml")
            ET.ElementTree(document).write(new_kml, encoding="utf-8", xml_declaration=True)

            output_kmz = os.path.join(extract_dir, "output.kmz")
            with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as z:
                z.write(new_kml, "doc.kml")

            with open(output_kmz, "rb") as f:
                st.download_button("📥 Download KMZ Hasil", f, file_name="output.kmz")

        # ==== MENU 2: Generate Kotak Rumah dari HP ====
        elif menu == "Generate Kotak Rumah":
            # Ambil HP
            hp_points = []
            for folder in root.findall(".//kml:Folder", ns):
                fname = folder.find("kml:name", ns)
                if fname is not None and fname.text == "HP":
                    for placemark in folder.findall("kml:Placemark", ns):
                        pname = placemark.find("kml:name", ns)
                        point = placemark.find(".//kml:Point", ns)
                        if pname is not None and point is not None:
                            coords_text = point.find("kml:coordinates", ns).text.strip()
                            lon, lat, *_ = map(float, coords_text.split(","))
                            hp_points.append((pname.text, lon, lat))

            # Bangun KML baru
            document = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
            doc_el = ET.SubElement(document, "Document")
            rumah_folder = ET.SubElement(doc_el, "Folder")
            ET.SubElement(rumah_folder, "name").text = "RUMAH"

            for name, lon, lat in hp_points:
                coords = create_house_box(lon, lat)
                pm = ET.SubElement(rumah_folder, "Placemark")
                ET.SubElement(pm, "name").text = f"Rumah {name}"
                polygon = ET.SubElement(pm, "Polygon")
                outer = ET.SubElement(polygon, "outerBoundaryIs")
                linear = ET.SubElement(outer, "LinearRing")
                ET.SubElement(linear, "coordinates").text = " ".join([f"{x},{y},0" for x,y in coords])

            # Simpan hasil
            new_kml = os.path.join(extract_dir, "rumah_output.kml")
            ET.ElementTree(document).write(new_kml, encoding="utf-8", xml_declaration=True)

            output_kmz = os.path.join(extract_dir, "rumah_output.kmz")
            with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as z:
                z.write(new_kml, "doc.kml")

            with open(output_kmz, "rb") as f:
                st.download_button("📥 Download KMZ Kotak Rumah", f, file_name="rumah_output.kmz")
