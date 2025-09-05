import os
import zipfile
import tempfile
import streamlit as st
from lxml import etree as ET
from shapely.geometry import Point, LineString
import math

st.title("📍 Pindahkan HP ke Tengah Kotak (berdasarkan Path 4 titik)")

# Fungsi hitung centroid kotak dari 4 titik
def get_centroid(coords):
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return (sum(xs) / len(xs), sum(ys) / len(ys))

# Fungsi cari titik HP terdekat dengan LineString
def nearest_hp_to_path(hp_points, path_coords):
    path_line = LineString(path_coords)
    nearest_hp = None
    min_dist = float("inf")
    for hp in hp_points:
        pt = Point(hp["coords"])
        dist = pt.distance(path_line)
        if dist < min_dist:
            min_dist = dist
            nearest_hp = hp
    return nearest_hp

uploaded_file = st.file_uploader("Upload file KML/KMZ", type=["kml", "kmz"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[-1]) as tmp:
        tmp.write(uploaded_file.read())
        file_path = tmp.name

    extract_dir = tempfile.mkdtemp()
    if file_path.lower().endswith(".kmz"):
        with zipfile.ZipFile(file_path, 'r') as z:
            z.extractall(extract_dir)
            files = z.namelist()
            kml_name = next((f for f in files if f.lower().endswith(".kml")), None)
            if not kml_name:
                st.error("❌ Tidak ada file .kml di KMZ")
                st.stop()
            kml_file = os.path.join(extract_dir, kml_name)
    else:
        kml_file = file_path

    parser = ET.XMLParser(remove_blank_text=True, recover=True, encoding="utf-8")
    tree = ET.parse(kml_file, parser=parser)
    root = tree.getroot()

    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    # Ambil semua HP
    hp_points = []
    for folder in root.findall(".//kml:Folder", ns):
        fname = folder.find("kml:name", ns)
        if fname is not None and fname.text == "HP":
            for pm in folder.findall("kml:Placemark", ns):
                point = pm.find(".//kml:Point", ns)
                nm = pm.find("kml:name", ns)
                if point is not None:
                    coords_text = point.find("kml:coordinates", ns).text.strip()
                    lon, lat, *_ = map(float, coords_text.split(","))
                    hp_points.append({"placemark": pm, "coords": (lon, lat), "name": nm.text if nm is not None else ""})

    moved_count = 0

    # Ambil path 4 titik dari folder KOTAK
    for folder in root.findall(".//kml:Folder", ns):
        fname = folder.find("kml:name", ns)
        if fname is not None and fname.text == "KOTAK":
            for pm in folder.findall("kml:Placemark", ns):
                line = pm.find(".//kml:LineString", ns)
                if line is not None:
                    coords_text = line.find("kml:coordinates", ns).text.strip()
                    coords = [(float(c.split(",")[0]), float(c.split(",")[1])) for c in coords_text.split()]
                    if len(coords) == 4:
                        # Hitung tengah kotak
                        centroid = get_centroid(coords)
                        # Cari HP terdekat
                        nearest_hp = nearest_hp_to_path(hp_points, coords)
                        if nearest_hp:
                            # Update posisi HP ke tengah kotak
                            pt_node = nearest_hp["placemark"].find(".//kml:coordinates", ns)
                            pt_node.text = f"{centroid[0]},{centroid[1]},0"
                            moved_count += 1

    # Simpan hasil
    out_dir = tempfile.mkdtemp()
    new_kml = os.path.join(out_dir, "hp_centered.kml")
    tree.write(new_kml, encoding="utf-8", xml_declaration=True)

    output_kmz = os.path.join(out_dir, "hp_centered.kmz")
    with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(new_kml, "doc.kml")

    st.success(f"✅ Selesai! {moved_count} titik HP dipindahkan ke tengah kotak.")

    with open(output_kmz, "rb") as f:
        st.download_button("⬇️ Download KMZ Hasil", f, file_name="hp_centered.kmz",
                           mime="application/vnd.google-earth.kmz")
