import os
import zipfile
import tempfile
import streamlit as st
from shapely.ops import unary_union
from shapely.geometry import Point, LineString, Polygon
from lxml import etree as ET
import simplekml
# Ambang batas jarak pole ke kabel (meter)
DIST_THRESHOLD = 30  


def parse_kmz(kmz_path):
    """Extract KMZ ke folder sementara dan parse KML utama"""
    tmpdir = tempfile.mkdtemp()
    with zipfile.ZipFile(kmz_path, 'r') as zf:
        zf.extractall(tmpdir)

    # Cari file .kml
    kml_file = None
    for root, dirs, files in os.walk(tmpdir):
        for f in files:
            if f.endswith('.kml'):
                kml_file = os.path.join(root, f)
                break
    if not kml_file:
        raise FileNotFoundError("KML file tidak ditemukan dalam KMZ")

    # Pakai parser yang lebih toleran
    parser = ET.XMLParser(recover=True, encoding="utf-8")
    tree = ET.parse(kml_file, parser=parser)
    return tree, tmpdir


def extract_geometry(placemark):
    """Ambil Point / LineString / Polygon dari Placemark"""
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    geom = placemark.find(".//kml:Point/kml:coordinates", ns)
    if geom is not None:
        lon, lat, *_ = map(float, geom.text.strip().split(","))
        return Point(lon, lat)

    geom = placemark.find(".//kml:LineString/kml:coordinates", ns)
    if geom is not None:
        coords = []
        for c in geom.text.strip().split():
            lon, lat, *_ = map(float, c.split(","))
            coords.append((lon, lat))
        return LineString(coords)

    geom = placemark.find(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns)
    if geom is not None:
        coords = []
        for c in geom.text.strip().split():
            lon, lat, *_ = map(float, c.split(","))
            coords.append((lon, lat))
        return Polygon(coords)

    return None


def classify_poles(tree):
    """Klasifikasikan POLE ke dalam masing-masing LINE"""
    ns = {"kml": "http://www.opengis.net/kml/2.2"}
    doc = tree.getroot()

    # ambil semua POLE global
    poles = []
    for folder in doc.findall(".//kml:Folder", ns):
    fname = folder.find("kml:name", ns)
    if fname is not None and "POLE" in fname.text.upper():
        for pm in folder.findall(".//kml:Placemark", ns):
            name_el = pm.find("kml:name", ns)
            name = name_el.text if name_el is not None else "Unnamed"
            geom = extract_geometry(pm)
            if isinstance(geom, Point):
                poles.append((name, geom))


    result = {}
    # loop setiap LINE utama (A, B, C, D)
    for line_folder in doc.findall(".//kml:Folder", ns):
        line_name = line_folder.find("kml:name", ns).text
        if not line_name or not line_name.upper().startswith("LINE"):
            continue

        # cari distribution cable di line ini
        cable = None
        for pm in line_folder.findall(".//kml:Placemark", ns):
            nm = (pm.find("kml:name", ns).text or "").upper()
            if "DISTRIBUTION CABLE" in nm:
                cable = extract_geometry(pm)

        # cari boundary di line ini
        boundaries = []
        for pm in line_folder.findall(".//kml:Placemark", ns):
            nm = (pm.find("kml:name", ns).text or "").upper()
            if "BOUNDARY" in nm:
                boundaries.append((nm, extract_geometry(pm)))

        assigned = []
        for name, p in poles:
            ok = False
            # cek ke kabel dulu
            if cable and isinstance(cable, LineString):
                d = p.distance(cable)
                if d <= DIST_THRESHOLD / 111320:  # approx degree to meter
                    assigned.append((name, p, cable.project(p)))
                    ok = True
            # kalau tidak kena kabel, cek boundary
            if not ok and boundaries:
                for bname, boundary in boundaries:
                    if isinstance(boundary, Polygon) and p.within(boundary):
                        line_key = bname[0].upper()  # huruf depannya A/B/C/D
                        if line_key in line_name.upper():
                            assigned.append((name, p, p.x))  # pakai X utk urut
                            ok = True
                            break

        # urutkan sesuai kabel kalau ada, kalau tidak pakai X
        if cable and isinstance(cable, LineString):
            assigned.sort(key=lambda x: x[2])
        else:
            assigned.sort(key=lambda x: x[2])

        result[line_name] = {"POLE": assigned}

    return result


def export_kmz(classified, output_path, prefix="POLE", padding=3):
    """Export hasil ke KMZ baru, folder per LINE"""
    kml = simplekml.Kml()
    for line_name, content in classified.items():
        f_line = kml.newfolder(name=line_name)
        poles = content.get("POLE", [])
        f_pole = f_line.newfolder(name="POLE")
        for i, (old_name, p, _) in enumerate(poles, 1):
            new_name = f"{prefix}{str(i).zfill(padding)}"
            f_pole.newpoint(name=new_name, coords=[(p.x, p.y)])
    kml.savekmz(output_path)




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
                classified = classify_poles(tree)

                output_kmz = os.path.join(tempfile.gettempdir(), "output_pole_per_line.kmz")
                export_kmz(classified, output_kmz, prefix=custom_prefix)

                st.success("✅ Selesai diurutkan dan diekspor ke KMZ")
                with open(output_kmz, "rb") as f:
                    st.download_button("📥 Download Hasil KMZ", f, file_name="output_pole_per_line.kmz")

            except Exception as e:
                st.error(f"❌ Error: {e}")


