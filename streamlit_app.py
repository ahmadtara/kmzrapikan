import streamlit as st
import zipfile
import os
import tempfile
from lxml import etree
from shapely.geometry import Point, LineString, Polygon
import math

# --- Fungsi parsing koordinat ---
def parse_coordinates(coord_text):
    coords = []
    for line in coord_text.strip().split():
        parts = line.split(",")
        if len(parts) >= 2:
            lon, lat = float(parts[0]), float(parts[1])
            coords.append((lon, lat))
    return coords

# --- Fungsi hitung centroid path (anggap polygon) ---
def path_centroid(coords):
    if len(coords) < 3:
        # Kalau cuma 2 titik, ambil midpoint
        x = (coords[0][0] + coords[-1][0]) / 2
        y = (coords[0][1] + coords[-1][1]) / 2
        return (x, y)
    else:
        # Tutup polygon kalau belum tertutup
        if coords[0] != coords[-1]:
            coords = coords + [coords[0]]
        poly = Polygon(coords)
        c = poly.centroid
        return (c.x, c.y)

# --- Fungsi hitung jarak Euclidean ---
def distance(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

# --- Fungsi utama bersih & pindahkan HP ---
def process_kml(input_kml, output_kml):
    parser = etree.XMLParser(remove_blank_text=True, recover=True)
    tree = etree.parse(input_kml, parser)
    root = tree.getroot()

    nsmap = {"kml": "http://www.opengis.net/kml/2.2"}

    # Ambil semua kotak (path)
    kotak_paths = []
    for folder in root.findall(".//kml:Folder", nsmap):
        name = folder.find("kml:name", nsmap)
        if name is not None and name.text and name.text.strip().upper() == "KOTAK":
            for placemark in folder.findall("kml:Placemark", nsmap):
                ls = placemark.find(".//kml:LineString/kml:coordinates", nsmap)
                if ls is not None and ls.text:
                    coords = parse_coordinates(ls.text)
                    if len(coords) >= 2:
                        centroid = path_centroid(coords)
                        kotak_paths.append((placemark, coords, centroid))

    # Ambil semua HP
    hp_points = []
    for folder in root.findall(".//kml:Folder", nsmap):
        name = folder.find("kml:name", nsmap)
        if name is not None and name.text and name.text.strip().upper() == "HP":
            for placemark in folder.findall("kml:Placemark", nsmap):
                pt = placemark.find(".//kml:Point/kml:coordinates", nsmap)
                if pt is not None and pt.text:
                    coords = parse_coordinates(pt.text)
                    if coords:
                        hp_points.append((placemark, coords[0]))

    moved = 0
    for kotak, coords, centroid in kotak_paths:
        # Cari HP terdekat
        nearest_hp = None
        nearest_dist = 1e9
        for pm, hp in hp_points:
            d = distance(hp, centroid)
            if d < nearest_dist:
                nearest_dist = d
                nearest_hp = (pm, hp)
        # Pindahkan ke centroid
        if nearest_hp:
            pm, old = nearest_hp
            new_coord = f"{centroid[0]},{centroid[1]},0"
            coord_elem = pm.find(".//kml:Point/kml:coordinates", nsmap)
            if coord_elem is not None:
                coord_elem.text = new_coord
                moved += 1

    tree.write(output_kml, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    return moved

# --- Fungsi utama Streamlit ---
st.title("📍 Pindahkan HP ke Tengah Kotak (Path)")

uploaded_file = st.file_uploader("Upload file KML atau KMZ", type=["kml", "kmz"])

if uploaded_file:
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, uploaded_file.name)
        with open(input_path, "wb") as f:
            f.write(uploaded_file.read())

        # Kalau KMZ, ekstrak dulu
        if uploaded_file.name.endswith(".kmz"):
            with zipfile.ZipFile(input_path, "r") as kmz:
                kmz.extractall(tmpdir)
            # Cari file KML utama
            for root_dir, _, files in os.walk(tmpdir):
                for file in files:
                    if file.endswith(".kml"):
                        input_path = os.path.join(root_dir, file)
                        break

        output_path = os.path.join(tmpdir, "output.kml")

        if st.button("🚀 Proses"):
            try:
                moved = process_kml(input_path, output_path)
                st.success(f"✅ Selesai! {moved} titik HP dipindahkan ke tengah kotak.")

                with open(output_path, "rb") as f:
                    st.download_button("⬇️ Download KML Hasil", f, file_name="hp_dipindahkan.kml")

            except Exception as e:
                st.error(f"Gagal memproses: {e}")
