import streamlit as st
import zipfile
import os
import tempfile
from lxml import etree as ET
from shapely.geometry import Point, Polygon



st.title("📌 KMZ Tools")

menu = st.sidebar.radio("Pilih Menu", [
    "Rapikan HP ke Boundary",
    "Generate Kotak Kapling",
    "Rename NN di HP",
    "Urutkan Nama Pole"
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




# MENU 2: Generate Kotak Kapling dari Titik HP
# ============================================
elif menu == "Generate Kotak Kapling":
    st.subheader("📐 Buat Kotak Kapling dari Titik HP")

    uploaded_file = st.file_uploader("Upload file KML/KMZ (titik HP)", type=["kml", "kmz"])

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

        # Cari folder HP saja
        hp_folder = None
        for folder in root.findall(".//kml:Folder", ns):
            fname = folder.find("kml:name", ns)
            if fname is not None and fname.text.strip().upper() == "HP":
                hp_folder = folder
                break

        points = []
        if hp_folder is not None:
            placemarks = hp_folder.findall(".//kml:Placemark", ns)
            for pm in placemarks:
                name_el = pm.find("kml:name", ns)
                coords_el = pm.find(".//kml:Point/kml:coordinates", ns)
                if coords_el is not None:
                    lon, lat, *_ = map(float, coords_el.text.strip().split(","))
                    name = name_el.text if name_el is not None else "NN"
                    points.append((lon, lat, name))

        if len(points) == 0:
            st.error("❌ Tidak ada titik di folder HP.")
        else:
            if st.button("Generate Kotak dari Titik"):
                used = set()
                kotak_list = []

                for i, (lon, lat, name) in enumerate(points, 1):
                    # Snap ke grid
                    gx = round(lon / size_x) * size_x
                    gy = round(lat / size_y) * size_y

                    while (gx, gy) in used:
                        gx += size_x  # geser biar tidak tabrakan
                    used.add((gx, gy))

                    # Buat kotak path
                    rect = [
                        (gx - size_x/2, gy - size_y/2),
                        (gx + size_x/2, gy - size_y/2),
                        (gx + size_x/2, gy + size_y/2),
                        (gx - size_x/2, gy + size_y/2),
                        (gx - size_x/2, gy - size_y/2),
                    ]
                    kotak_list.append((rect, f"{name}-{i:02d}"))

                # Susun ke KML
                document = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
                doc_el = ET.SubElement(document, "Document")

                for rect, name in kotak_list:
                    pm = ET.SubElement(doc_el, "Placemark")
                    ET.SubElement(pm, "name").text = name
                    line = ET.SubElement(pm, "LineString")
                    ET.SubElement(line, "tessellate").text = "1"
                    ET.SubElement(line, "coordinates").text = " ".join([f"{x},{y},0" for x,y in rect])

                extract_dir = tempfile.mkdtemp()
                new_kml = os.path.join(extract_dir, "kapling.kml")
                ET.ElementTree(document).write(new_kml, encoding="utf-8", xml_declaration=True)

                output_kmz = os.path.join(extract_dir, "kapling.kmz")
                with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as z:
                    z.write(new_kml, "doc.kml")

                with open(output_kmz, "rb") as f:
                    st.download_button("📥 Download KMZ Kotak", f, "kapling.kmz",
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
            

# ====== MENU 4: Urutkan Nama Pole ======
# ====== MENU 4: Rapikan POLE per Boundary ======
elif menu == "Rapikan POLE per Boundary":
    st.subheader("📍 Rapikan POLE sesuai Boundary")

    uploaded_file = st.file_uploader("Upload file KML/KMZ", type=["kml", "kmz"])
    prefix = st.text_input("Prefix Nama Pole", value="MR.OATKRP.P")
    start_num = st.number_input("Nomor awal", min_value=1, value=1, step=1)
    pad_width = st.number_input("Jumlah digit (padding)", min_value=3, value=3, step=1)
    sort_mode = st.selectbox("Urutkan berdasarkan", ["Longitude (X)", "Latitude (Y)", "Mengikuti Alur"])

    if uploaded_file is not None:
        # Simpan sementara
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
            kml_file = file_path

        # Parse KML
        parser = ET.XMLParser(recover=True, encoding="utf-8")
        tree = ET.parse(kml_file, parser=parser)
        root = tree.getroot()
        ns = {"kml": "http://www.opengis.net/kml/2.2"}

        # Cari BOUNDARY (Polygon)
        boundaries = []
        for pm in root.findall(".//kml:Placemark", ns):
            poly = pm.find(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns)
            if poly is not None:
                coords = [tuple(map(float, c.split(",")[:2])) for c in poly.text.strip().split()]
                boundaries.append((pm.find("kml:name", ns).text if pm.find("kml:name", ns) is not None else "Boundary", Polygon(coords)))

        # Cari POLE (Point)
        poles = []
        for pm in root.findall(".//kml:Placemark", ns):
            coords_el = pm.find(".//kml:Point/kml:coordinates", ns)
            if coords_el is not None:
                lon, lat, *_ = map(float, coords_el.text.strip().split(","))
                poles.append((Point(lon, lat), pm))

        if not boundaries or not poles:
            st.error("❌ Tidak ada Boundary atau POLE ditemukan.")
            st.stop()

        # Buat struktur KML baru
        from simplekml import Kml
        kml_out = Kml()

        total_updated = 0

        for b_idx, (bname, bpoly) in enumerate(boundaries, 1):
            folder_b = kml_out.newfolder(name=f"{bname}")

            # Pilih POLE yang jatuh di dalam boundary ini
            poles_in = [(pt, pm) for pt, pm in poles if bpoly.contains(pt)]

            if not poles_in:
                continue

            # Urutkan sesuai pilihan
            if sort_mode == "Longitude (X)":
                poles_in.sort(key=lambda x: x[0].x)
            elif sort_mode == "Latitude (Y)":
                poles_in.sort(key=lambda x: x[0].y)
            else:  # Mengikuti alur (greedy nearest neighbor)
                ordered = []
                remaining = poles_in[:]
                current = remaining.pop(0)
                ordered.append(current)
                while remaining:
                    # cari titik terdekat
                    current = min(remaining, key=lambda r: current[0].distance(r[0]))
                    ordered.append(current)
                    remaining.remove(current)
                poles_in = ordered

            # Rename & tambahkan ke folder
            counter = start_num
            for pt, pm in poles_in:
                newname = f"{prefix}{str(counter).zfill(int(pad_width))}"
                folder_b.newpoint(name=newname, coords=[(pt.x, pt.y)])
                counter += 1
                total_updated += 1

        if total_updated == 0:
            st.warning("❌ Tidak ada POLE yang masuk boundary.")
        else:
            # Simpan hasil
            out_dir = tempfile.mkdtemp()
            kmz_out = os.path.join(out_dir, "POLE_rapi.kmz")
            kml_out.savekmz(kmz_out)

            with open(kmz_out, "rb") as f:
                st.success(f"✅ {total_updated} POLE berhasil dirapikan per boundary")
                st.download_button("📥 Download KMZ (Pole sudah rapi)", f,
                                   file_name="POLE_rapi.kmz",
                                   mime="application/vnd.google-earth.kmz")



