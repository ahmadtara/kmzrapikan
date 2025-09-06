import os
import zipfile
import tempfile
import streamlit as st
from shapely.geometry import Point, LineString, Polygon
from lxml import etree as ET

st.title("📌 Pindahkan HP ke Tengah Kotak (Path)")

# Fungsi parsing koordinat
def parse_coordinates(coord_text):
    coords = []
    for c in coord_text.strip().split():
        lon, lat, *_ = map(float, c.split(","))
        coords.append((lon, lat))
    return coords

# Fungsi utama
def process_kml(kml_file, output_kml):
    parser = ET.XMLParser(recover=True, encoding="utf-8")
    tree = ET.parse(kml_file, parser=parser)
    root = tree.getroot()
    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    kotak_paths = []
    hp_points = []

    # Cari folder KOTAK → LineString
    for folder in root.findall(".//kml:Folder", ns):
        fname = folder.find("kml:name", ns)
        if fname is not None and fname.text == "KOTAK":
            for placemark in folder.findall("kml:Placemark", ns):
                line = placemark.find(".//kml:LineString", ns)
                if line is not None:
                    coords_text = line.find("kml:coordinates", ns).text.strip()
                    coords = parse_coordinates(coords_text)
                    if len(coords) >= 2:  # minimal 2 titik
                        # Tutup jadi polygon kalau belum tertutup
                        if coords[0] != coords[-1]:
                            coords.append(coords[0])
                        polygon = Polygon(coords)
                        if polygon.is_valid:
                            kotak_paths.append((placemark, polygon))

    # Cari folder HP → Point
    for folder in root.findall(".//kml:Folder", ns):
        fname = folder.find("kml:name", ns)
        if fname is not None and fname.text == "HP":
            for placemark in folder.findall("kml:Placemark", ns):
                point = placemark.find(".//kml:Point", ns)
                if point is not None:
                    coords_text = point.find("kml:coordinates", ns).text.strip()
                    lon, lat, *_ = map(float, coords_text.split(","))
                    hp_points.append((placemark, Point(lon, lat)))

    moved_count = 0
    for placemark, polygon in kotak_paths:
        centroid = polygon.centroid
        # Cari HP terdekat ke centroid
        nearest_hp = None
        nearest_dist = float("inf")
        for hp_pm, hp_point in hp_points:
            d = centroid.distance(hp_point)
            if d < nearest_dist:
                nearest_dist = d
                nearest_hp = (hp_pm, hp_point)

        if nearest_hp:
            hp_pm, hp_point = nearest_hp
            # Update koordinat HP ke centroid
            point_el = hp_pm.find(".//kml:Point/kml:coordinates", ns)
            if point_el is not None:
                point_el.text = f"{centroid.x},{centroid.y},0"
                moved_count += 1

    # Simpan hasil
    tree.write(output_kml, encoding="utf-8", xml_declaration=True)
    return moved_count

# Upload file
uploaded_file = st.file_uploader("Upload file KML atau KMZ", type=["kml", "kmz"])

if uploaded_file:
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.read())

        # Jika KMZ → ekstrak KML
        if file_path.lower().endswith(".kmz"):
            with zipfile.ZipFile(file_path, "r") as z:
                z.extractall(tmpdir)
                files = z.namelist()
                kml_name = next((f for f in files if f.lower().endswith(".kml")), None)
                if not kml_name:
                    st.error("❌ Tidak ada file .kml di dalam KMZ.")
                    st.stop()
                kml_file = os.path.join(tmpdir, kml_name)
        else:
            kml_file = file_path

        output_kml = os.path.join(tmpdir, "output.kml")
        moved_count = process_kml(kml_file, output_kml)

        if moved_count > 0:
            st.success(f"✅ Selesai! {moved_count} titik HP dipindahkan ke tengah kotak.")
            with open(output_kml, "rb") as f:
                st.download_button("⬇️ Download KML Hasil", f, "output.kml")
        else:
            st.warning("⚠️ Tidak ada titik HP yang berhasil dipindahkan.")
