import os
import zipfile
import tempfile
import streamlit as st
from shapely.ops import unary_union
from shapely.geometry import Point, LineString, Polygon
from lxml import etree as ET
import simplekml
# Ambang batas jarak pole ke kabel (meter)

st.title("📌 KMZ Tools")

menu = st.sidebar.radio("Pilih Menu", [
    "Rapikan HP ke Boundary",
    "Rename NN di HP",
    "Urutkan POLE ke Line"
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

        # Cari folder HP
        def find_folder_by_name(el, name):
            for f in el.findall(".//kml:Folder", ns):
                n = f.find("kml:name", ns)
                if n is not None and (n.text or "").strip() == name:
                    return f
            return None

        hp_folder = find_folder_by_name(root, "HP")
        if hp_folder is None:
            st.error("❌ Folder 'HP' tidak ditemukan di KML/KMZ.")
            st.stop()

        # Kumpulkan placemark NN
        nn_placemarks = []
        for pm in hp_folder.findall("kml:Placemark", ns):
            nm = pm.find("kml:name", ns)
            if nm is None:
                continue
            text = (nm.text or "").strip()
            # cocokkan yang diawali prefix (NN, NN-xx, NN xx, dsb)
            if text.upper().startswith(prefix.upper()):
                nn_placemarks.append(nm)

        if not nn_placemarks:
            st.warning("Tidak ada Placemark berawalan 'NN' di folder HP.")
            st.stop()

        # Rename berurutan sesuai urutan di file
        counter = int(start_num)
        for nm in nn_placemarks:
            nm.text = f"{prefix}-{str(counter).zfill(int(pad_width))}"
            counter += 1

        # Tulis ulang KML
        out_dir = tempfile.mkdtemp()
        new_kml = os.path.join(out_dir, "renamed.kml")
        tree.write(new_kml, encoding="utf-8", xml_declaration=True)

        # Jika asalnya KMZ → buat KMZ baru; kalau KML → tetap bisa kasih KMZ juga
        output_kmz = os.path.join(out_dir, "renamed.kmz")
        with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(new_kml, "doc.kml")

        # Unduhan
        with open(output_kmz, "rb") as f:
            st.download_button("📥 Download KMZ (NN sudah di-rename)", f,
                               file_name="NN_renamed.kmz",
                               mime="application/vnd.google-earth.kmz")
            
# ====== MENU 4: Urutkan POLE ke Line ======
elif menu == "Urutkan POLE ke Line":
    st.subheader("🔀 Urutkan POLE ke Line")

    uploaded_file = st.file_uploader("Upload file KMZ", type=["kmz"])
    if uploaded_file is not None:
        tmp_path = os.path.join(tempfile.gettempdir(), uploaded_file.name)
        with open(tmp_path, "wb") as f:
            f.write(uploaded_file.read())

        # 👉 Input nama pole custom
        custom_prefix = st.text_input("Prefix nama POLE baru", value="POLE")

        if st.button("Proses"):
            try:
                tree, _ = parse_kmz(tmp_path)
                ns = {"kml": "http://www.opengis.net/kml/2.2"}
                doc = tree.getroot()
                result = {}

                # loop setiap LINE
                for line_folder in doc.findall(".//kml:Folder", ns):
                    line_name_el = line_folder.find("kml:name", ns)
                    if line_name_el is None:
                        continue
                    line_name = line_name_el.text
                    if not line_name or not line_name.upper().startswith("LINE"):
                        continue

                    # Ambil POLE di dalam LINE ini
                    poles = []
                    for subfolder in line_folder.findall("kml:Folder", ns):
                        sf_name = subfolder.find("kml:name", ns)
                        if sf_name is not None and "POLE" in sf_name.text.upper():
                            for pm in subfolder.findall("kml:Placemark", ns):
                                name_el = pm.find("kml:name", ns)
                                name = name_el.text if name_el is not None else "Unnamed"
                                geom = extract_geometry(pm)
                                if isinstance(geom, Point):
                                    poles.append((name, geom))

                    # cari distribution cable
                    cable = None
                    for pm in line_folder.findall("kml:Placemark", ns):
                        nm = (pm.find("kml:name", ns).text or "").upper()
                        if "DISTRIBUTION CABLE" in nm:
                            cable = extract_geometry(pm)

                    # cari boundary
                    boundaries = []
                    for pm in line_folder.findall("kml:Placemark", ns):
                        nm = (pm.find("kml:name", ns).text or "").upper()
                        if "BOUNDARY" in nm:
                            boundaries.append((nm, extract_geometry(pm)))

                    # assign POLE ke kabel / boundary
                    assigned = []
                    for name, p in poles:
                        ok = False
                        if cable and isinstance(cable, LineString):
                            d = p.distance(cable)
                            if d <= DIST_THRESHOLD / 111320:  # derajat ~ meter
                                assigned.append((name, p, cable.project(p)))
                                ok = True
                        if not ok and boundaries:
                            for bname, boundary in boundaries:
                                if isinstance(boundary, Polygon) and p.within(boundary):
                                    assigned.append((name, p, p.x))
                                    ok = True
                                    break

                    # urutkan
                    if cable and isinstance(cable, LineString):
                        assigned.sort(key=lambda x: x[2])
                    else:
                        assigned.sort(key=lambda x: x[2])

                    result[line_name] = {"POLE": assigned}

                # export hasil
                output_kmz = os.path.join(tempfile.gettempdir(), "output_pole_per_line.kmz")
                export_kmz(result, output_kmz, prefix=custom_prefix)

                st.success("✅ Selesai diurutkan dan diekspor ke KMZ")
                with open(output_kmz, "rb") as f:
                    st.download_button("📥 Download Hasil KMZ", f, file_name="output_pole_per_line.kmz")

            except Exception as e:
                st.error(f"❌ Error: {e}")

