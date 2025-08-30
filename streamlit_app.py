import streamlit as st
import zipfile
import os
import tempfile
from lxml import etree as ET
from shapely.geometry import Point, Polygon

st.title("📌 KMZ Tools")

menu = st.sidebar.radio("Pilih Menu", [
    "Rapikan HP ke Boundary",
    "Generate Kotak Kapling"
])

# =========================
# MENU 1: Rapikan HP ke Boundary
# =========================
if menu == "Rapikan HP ke Boundary":
    uploaded_file = st.file_uploader("Upload file KMZ", type=["kmz"])

    if uploaded_file is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".kmz") as tmp:
            tmp.write(uploaded_file.read())
            kmz_file = tmp.name

        st.success(f"✅ File berhasil diupload: {uploaded_file.name}")

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

            def get_coordinates(coord_text):
                coords = []
                for c in coord_text.strip().split():
                    lon, lat, *_ = map(float, c.split(","))
                    coords.append((lon, lat))
                return coords

            # Ambil boundary LINE A/B/C/D
            boundaries = {}
            for folder in root.findall(".//kml:Folder", ns):
                fname = folder.find("kml:name", ns)
                if fname is not None and fname.text.startswith("LINE "):
                    line_name = fname.text
                    boundaries[line_name] = {}
                    for placemark in folder.findall(".//kml:Placemark", ns):
                        pname = placemark.find("kml:name", ns)
                        polygon = placemark.find(".//kml:Polygon", ns)
                        if pname is not None and polygon is not None:
                            coords_text = polygon.find(".//kml:coordinates", ns).text
                            coords = get_coordinates(coords_text)
                            boundaries[line_name][pname.text] = Polygon(coords)

            # Ambil titik HP
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
                            hp_points.append((pname.text, Point(lon, lat), placemark))

            # Cek masuk boundary mana
            assignments = {}
            for line, bdict in boundaries.items():
                for bname in bdict.keys():
                    assignments.setdefault(line, {}).setdefault(bname, [])

            for name, point, placemark in hp_points:
                for line, bdict in boundaries.items():
                    for bname, poly in bdict.items():
                        if poly.contains(point):
                            assignments[line][bname].append(placemark)
                            break

            # Susun ulang KML
            document = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
            doc_el = ET.SubElement(document, "Document")

            for line, bdict in assignments.items():
                line_folder = ET.SubElement(doc_el, "Folder")
                ET.SubElement(line_folder, "name").text = line
                for bname, placemarks in bdict.items():
                    boundary_folder = ET.SubElement(line_folder, "Folder")
                    ET.SubElement(boundary_folder, "name").text = bname
                    for pm in placemarks:
                        boundary_folder.append(pm)

            new_kml = os.path.join(extract_dir, "output.kml")
            ET.ElementTree(document).write(new_kml, encoding="utf-8", xml_declaration=True)

            output_kmz = os.path.join(extract_dir, "output.kmz")
            with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as z:
                z.write(new_kml, "doc.kml")

            with open(output_kmz, "rb") as f:
                st.download_button("📥 Download KMZ Hasil", f, "output.kmz",
                                   mime="application/vnd.google-earth.kmz")

# =========================
# MENU 2: Generate Kotak Kapling
# =========================
elif menu == "Generate Kotak Kapling":
    st.subheader("📐 Buat Kotak Rumah/Kapling")

    # Input koordinat tengah (misalnya ambil dari HP atau manual)
    lon = st.number_input("Longitude", value=106.827153, format="%.6f")
    lat = st.number_input("Latitude", value=-6.175392, format="%.6f")
    size_x = st.number_input("Ukuran X (derajat)", value=0.00005, format="%.6f")
    size_y = st.number_input("Ukuran Y (derajat)", value=0.00005, format="%.6f")

    if st.button("Generate Kotak"):
        # Fungsi bikin path kotak
        def create_house_path(lon, lat, size_x=0.00005, size_y=0.00005):
            coords = [
                (lon - size_x, lat - size_y),
                (lon - size_x, lat + size_y),
                (lon + size_x, lat + size_y),
                (lon + size_x, lat - size_y),
                (lon - size_x, lat - size_y)
            ]
            return coords

        coords = create_house_path(lon, lat, size_x, size_y)

        document = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
        doc_el = ET.SubElement(document, "Document")
        pm = ET.SubElement(doc_el, "Placemark")
        ET.SubElement(pm, "name").text = "Kotak Kapling"
        line = ET.SubElement(pm, "LineString")
        ET.SubElement(line, "tessellate").text = "1"
        ET.SubElement(line, "coordinates").text = " ".join([f"{x},{y},0" for x,y in coords])

        extract_dir = tempfile.mkdtemp()
        new_kml = os.path.join(extract_dir, "kapling.kml")
        ET.ElementTree(document).write(new_kml, encoding="utf-8", xml_declaration=True)

        output_kmz = os.path.join(extract_dir, "kapling.kmz")
        with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(new_kml, "doc.kml")

        with open(output_kmz, "rb") as f:
            st.download_button("📥 Download KMZ Kotak", f, "kapling.kmz",
                               mime="application/vnd.google-earth.kmz")
