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

# ====== MENU 3: Rename NN di folder HP ======
elif menu == "Rename NN di HP":
    st.subheader("🔤 Ubah nama NN → NN-01, NN-02, ... di folder HP")

    uploaded_file = st.file_uploader("Upload file KML/KMZ", type=["kml", "kmz"])
    start_num = st.number_input("Nomor awal", min_value=1, value=1, step=1)
    pad_width = st.number_input("Jumlah digit (padding)", min_value=1, value=2, step=1)
    prefix = st.text_input("Prefix yang dicari", value="NN")

    if uploaded_file is not None:
        # Simpan sementara
        import tempfile, os, zipfile
        from lxml import etree as ET

        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[-1]) as tmp:
            tmp.write(uploaded_file.read())
            file_path = tmp.name

        # Jika KMZ → ekstrak KML
        extract_dir = tempfile.mkdtemp()
        if file_path.lower().endswith(".kmz"):
            with zipfile.ZipFile(file_path, 'r') as z:
                z.extractall(extract_dir)
                files = z.namelist()
                kml_name = next((f for f in files if f.lower().endswith(".kml")), None)
                if not kml_name:
                    st.error("❌ Tidak ada file .kml di dalam KMZ.")
                    st.stop()
                kml_file = os.path.join(extract_dir, kml_name)
        else:
            # KML langsung
            kml_file = file_path

        # Parse KML dengan lxml (lebih toleran)
        parser = ET.XMLParser(recover=True, encoding="utf-8")
        tree = ET.parse(kml_file, parser=parser)
        root = tree.getroot()
        ns = {"kml": "http://www.opengis.net/kml/2.2"}

        # Cari fol


# =========================
# MENU 2: Generate Kotak Kapling
# =========================
elif menu == "Generate Kotak Kapling":
    st.subheader("📐 Buat Kotak Rumah/Kapling dari Boundary")

    uploaded_file = st.file_uploader("Upload file KML/KMZ", type=["kml", "kmz"])

    size_x = st.number_input("Ukuran X (derajat)", value=0.00005, format="%.6f")
    size_y = st.number_input("Ukuran Y (derajat)", value=0.00005, format="%.6f")

    if uploaded_file is not None:
        # Simpan sementara
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[-1]) as tmp:
            tmp.write(uploaded_file.read())
            file_path = tmp.name

        # Kalau KMZ → ekstrak ke KML
        if file_path.endswith(".kmz"):
            extract_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(file_path, 'r') as z:
                z.extractall(extract_dir)
                files = z.namelist()
                kml_name = next((f for f in files if f.lower().endswith(".kml")), None)
            kml_file = os.path.join(extract_dir, kml_name)
        else:
            kml_file = file_path

        # Parse KML
        parser = ET.XMLParser(recover=True, encoding="utf-8")
        tree = ET.parse(kml_file, parser=parser)
        root = tree.getroot()
        ns = {"kml": "http://www.opengis.net/kml/2.2"}

        # Cari polygon boundary pertama
        polygon_el = root.find(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns)
        if polygon_el is None:
            st.error("❌ Tidak ada Polygon di file KML.")
        else:
            coords_text = polygon_el.text.strip()
            coords = []
            for c in coords_text.split():
                lon, lat, *_ = map(float, c.split(","))
                coords.append((lon, lat))
            boundary = Polygon(coords)

            if st.button("Generate Kotak dari Boundary"):
                minx, miny, maxx, maxy = boundary.bounds

                # Buat grid kotak
                kotak_list = []
                x = minx
                while x < maxx:
                    y = miny
                    while y < maxy:
                        rect = Polygon([
                            (x, y),
                            (x, y + size_y),
                            (x + size_x, y + size_y),
                            (x + size_x, y),
                            (x, y)
                        ])
                        if boundary.intersects(rect):
                            kotak_list.append(rect)
                        y += size_y
                    x += size_x

                # Susun ke KML
                document = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
                doc_el = ET.SubElement(document, "Document")

                for i, rect in enumerate(kotak_list, 1):
                    pm = ET.SubElement(doc_el, "Placemark")
                    ET.SubElement(pm, "name").text = f"Kotak {i}"
                    line = ET.SubElement(pm, "LineString")
                    ET.SubElement(line, "tessellate").text = "1"
                    ET.SubElement(line, "coordinates").text = " ".join([f"{x},{y},0" for x,y in rect.exterior.coords])

                extract_dir = tempfile.mkdtemp()
                new_kml = os.path.join(extract_dir, "kapling.kml")
                ET.ElementTree(document).write(new_kml, encoding="utf-8", xml_declaration=True)

                output_kmz = os.path.join(extract_dir, "kapling.kmz")
                with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as z:
                    z.write(new_kml, "doc.kml")

                with open(output_kmz, "rb") as f:
                    st.download_button("📥 Download KMZ Kotak", f, "kapling.kmz",
                                       mime="application/vnd.google-earth.kmz")

