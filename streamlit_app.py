import os
import zipfile
import tempfile
import streamlit as st
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
from lxml import etree as ET   # 👉 pakai lxml agar support recover=True



st.title("📌 KMZ Tools")

menu = st.sidebar.radio("Pilih Menu", [
    "Rapikan HP ke Boundary",
    "Generate Kotak Kapling",
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
            

# ====== MENU 4: Urutkan POLE ke Line ======
elif menu == "Urutkan POLE ke Line":
    st.subheader("📍 Urutkan POLE per LINE (pedoman: Distribution Cable + Boundary fallback)")

    uploaded_file = st.file_uploader("Upload file KML/KMZ", type=["kml", "kmz"])
    prefix = st.text_input("Prefix Nama Pole", value="MR.OATKRP.P")
    start_num = st.number_input("Nomor awal (reset tiap LINE)", min_value=1, value=1, step=1)
    pad_width = st.number_input("Jumlah digit (padding)", min_value=1, value=3, step=1)
    dist_threshold_m = st.number_input("Batas jarak ke kabel (meter)", min_value=0, value=30, step=5)
    use_boundary = st.checkbox("Gunakan Boundary (jika ada)", value=True)
    fallback_to_nearest = st.checkbox("Jika jauh dari kabel & di luar boundary → masukkan ke LINE terdekat", value=True)

    if uploaded_file is not None:
        # ===== Helper =====
        from lxml import etree as ET
        import simplekml
        from shapely.geometry import Point, LineString, Polygon

        ns = {"kml": "http://www.opengis.net/kml/2.2"}

        def m_to_deg(m):
            # pendekatan kasar: 1 derajat ≈ 111,320 m
            return m / 111_320.0

        def parse_kml_or_kmz(file_like):
            # Simpan dulu
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[-1]) as tmp:
                tmp.write(file_like.read())
                file_path = tmp.name

            # Jika KMZ → ekstrak ke KML
            if file_path.lower().endswith(".kmz"):
                extract_dir = tempfile.mkdtemp()
                with zipfile.ZipFile(file_path, 'r') as z:
                    z.extractall(extract_dir)
                    # cari doc.kml atau *.kml
                    kml_name = None
                    # Prefer doc.kml jika ada
                    for r, d, files in os.walk(extract_dir):
                        for f in files:
                            if f.lower() == "doc.kml":
                                kml_name = os.path.join(r, f)
                                break
                    if kml_name is None:
                        for r, d, files in os.walk(extract_dir):
                            for f in files:
                                if f.lower().endswith(".kml"):
                                    kml_name = os.path.join(r, f)
                                    break
                    if not kml_name:
                        st.error("❌ Tidak ada file .kml di dalam KMZ.")
                        st.stop()
                kml_file = kml_name
            else:
                kml_file = file_path

            parser = ET.XMLParser(recover=True, encoding="utf-8")
            tree = ET.parse(kml_file, parser=parser)
            return tree

        def extract_point(pm):
            coords_el = pm.find(".//kml:Point/kml:coordinates", ns)
            if coords_el is None or not (coords_el.text or "").strip():
                return None
            lon, lat, *_ = map(float, coords_el.text.strip().split(","))
            return Point(lon, lat)

        def extract_lines_in_folder(folder):
            """Ambil semua LineString (utamakan yang ada di subfolder 'DISTRIBUTION CABLE' kalau ada)."""
            # Cari subfolder DISTRIBUTION CABLE
            target_folders = []
            for subf in folder.findall(".//kml:Folder", ns):
                nm = subf.find("kml:name", ns)
                if nm is not None and "DISTRIBUTION CABLE" in (nm.text or "").upper():
                    target_folders.append(subf)
            # Kalau tidak ada, pakai folder LINE langsung
            if not target_folders:
                target_folders = [folder]

            coords = []
            for tf in target_folders:
                for ls in tf.findall(".//kml:LineString/kml:coordinates", ns):
                    if (ls.text or "").strip():
                        for c in ls.text.strip().split():
                            lon, lat, *_ = map(float, c.split(","))
                            coords.append((lon, lat))
            # jika tidak ada, kembalikan None
            if len(coords) < 2:
                return None
            return LineString(coords)

        def extract_boundaries_in_folder(folder):
            """Ambil semua Polygon boundary di dalam folder LINE (nama mengandung 'BOUNDARY' diprioritaskan)."""
            polys_named = []
            polys_any = []
            for pm in folder.findall(".//kml:Placemark", ns):
                name = (pm.find("kml:name", ns).text if pm.find("kml:name", ns) is not None else "") or ""
                co = pm.find(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns)
                if co is not None and (co.text or "").strip():
                    coords = [tuple(map(float, c.split(",")[:2])) for c in co.text.strip().split()]
                    if len(coords) >= 3:
                        poly = Polygon(coords)
                        if "BOUNDARY" in name.upper():
                            polys_named.append(poly)
                        else:
                            polys_any.append(poly)
            return polys_named if polys_named else polys_any

        def get_all_poles(root):
            """Ambil semua titik di folder bernama 'POLE' di mana saja di dokumen."""
            poles = []
            for pm in root.findall(".//kml:Folder[kml:name='POLE']//kml:Placemark", ns):
                pt = extract_point(pm)
                if pt is not None:
                    poles.append({"name": (pm.find("kml:name", ns).text or "").strip(), "point": pt})
            return poles

        def get_line_folders(root):
            """Ambil folder yang namanya diawali 'LINE ' (LINE A/B/C/D)."""
            outs = []
            for f in root.findall(".//kml:Folder", ns):
                nm = f.find("kml:name", ns)
                if nm is not None and (nm.text or "").strip().upper().startswith("LINE"):
                    outs.append(f)
            return outs

        # ===== Proses utama =====
        tree = parse_kml_or_kmz(uploaded_file)
        root = tree.getroot()

        # Kumpulkan semua POLE
        poles = get_all_poles(root)
        if not poles:
            st.error("❌ Folder 'POLE' tidak ditemukan atau tidak ada titiknya.")
            st.stop()

        # Ambil semua LINE folders
        line_folders = get_line_folders(root)
        if not line_folders:
            st.error("❌ Folder LINE A/B/C/D tidak ditemukan.")
            st.stop()

        # Siapkan struktur hasil: { line_name: [ {point, t, dist_m}, ... ] }
        classified = { (lf.find('kml:name', ns).text or 'LINE').strip(): [] for lf in line_folders }

        # Hitung assignment terbaik per pole (hanya 1 line per pole)
        threshold_deg = m_to_deg(dist_threshold_m)
        for pole in poles:
            p = pole["point"]
            best = None  # (score_tuple, line_name, t_along, dist_deg)

            for lf in line_folders:
                line_name = (lf.find("kml:name", ns).text or "LINE").strip()
                cable = extract_lines_in_folder(lf)
                boundaries = extract_boundaries_in_folder(lf) if use_boundary else []

                inside_boundary = any(poly.contains(p) for poly in boundaries) if boundaries else False
                dist_deg = p.distance(cable) if cable is not None else None
                t_along = cable.project(p) if cable is not None else None

                # Skema skor:
                # 1) Prioritas in-boundary (score group 0), urutkan oleh t_along jika ada kabel
                # 2) Kalau tidak di boundary, tapi dekat kabel <= threshold (group 1), urutkan oleh dist & t
                # 3) Kalau masih tidak, dan fallback_to_nearest True, pilih kabel terdekat (group 2)
                if inside_boundary:
                    score = (0, t_along if t_along is not None else float("inf"))
                elif (cable is not None and dist_deg is not None and dist_deg <= threshold_deg):
                    score = (1, dist_deg, t_along if t_along is not None else float("inf"))
                elif fallback_to_nearest and (cable is not None and dist_deg is not None):
                    score = (2, dist_deg, t_along if t_along is not None else float("inf"))
                else:
                    continue  # tidak layak untuk line ini

                if (best is None) or (score < best[0]):
                    best = (score, line_name, t_along, dist_deg)

            if best is not None:
                _, line_name, t_along, dist_deg = best
                classified[line_name].append({"point": p, "t": t_along, "dist_deg": dist_deg})

        # Urutkan dalam tiap LINE mengikuti alur kabel (t). Jika tidak ada kabel, fallback sort by X (lon)
        for lf in line_folders:
            line_name = (lf.find("kml:name", ns).text or "LINE").strip()
            # cek apakah line punya cable
            has_cable = extract_lines_in_folder(lf) is not None
            if has_cable:
                classified[line_name].sort(key=lambda d: (float("inf") if d["t"] is None else d["t"]))
            else:
                classified[line_name].sort(key=lambda d: d["point"].x)

        # Export KMZ: per LINE ada subfolder "POLE", nama di-rename prefix+padding, counter reset tiap LINE
        kml = simplekml.Kml()
        total = 0
        for lf in line_folders:
            line_name = (lf.find("kml:name", ns).text or "LINE").strip()
            items = classified.get(line_name, [])
            f_line = kml.newfolder(name=line_name)
            f_pole = f_line.newfolder(name="POLE")

            counter = int(start_num)
            for rec in items:
                p = rec["point"]
                new_name = f"{prefix}{str(counter).zfill(int(pad_width))}"
                f_pole.newpoint(name=new_name, coords=[(p.x, p.y)])
                counter += 1
                total += 1

        # Simpan & unduh
        out_dir = tempfile.mkdtemp()
        out_kmz = os.path.join(out_dir, "POLE_sorted_per_LINE.kmz")
        kml.savekmz(out_kmz)

        with open(out_kmz, "rb") as f:
            st.success(f"✅ Berhasil: {total} POLE diurutkan & di-rename ke folder LINE masing-masing.")
            st.download_button("📥 Download KMZ (POLE per LINE)", f,
                               file_name="POLE_sorted.kmz",
                               mime="application/vnd.google-earth.kmz")

