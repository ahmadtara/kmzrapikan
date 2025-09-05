import streamlit as st
import tempfile
import os
import zipfile
from lxml import etree as ET
from shapely.geometry import Point, Polygon, LineString

st.title("📌 Geser HP ke Tengah Kotak (Path 4 titik)")

uploaded_file = st.file_uploader("Upload file KML", type=["kml"])

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".kml") as tmp:
        tmp.write(uploaded_file.read())
        kml_path = tmp.name

    # Parse KML
    parser = ET.XMLParser(recover=True, encoding="utf-8")
    tree = ET.parse(kml_path, parser=parser)
    root = tree.getroot()
    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    # Ambil kotak (LineString 4 titik → Polygon)
    kotak_polygons = []
    kotak_centroids = []

    for folder in root.findall(".//kml:Folder", ns):
        fname = folder.find("kml:name", ns)
        if fname is not None and fname.text == "KOTAK":
            for placemark in folder.findall("kml:Placemark", ns):
                line = placemark.find(".//kml:LineString", ns)
                if line is not None:
                    coords_text = line.find("kml:coordinates", ns).text.strip()
                    coords = [
                        (float(c.split(",")[0]), float(c.split(",")[1]))
                        for c in coords_text.split()
                    ]
                    if len(coords) == 4:  # pastikan path ada 4 titik
                        poly = Polygon(coords + [coords[0]])
                        kotak_polygons.append(poly)
                        kotak_centroids.append(poly.centroid)

    # Ambil HP
    hp_points = []
    hp_folder = None
    for folder in root.findall(".//kml:Folder", ns):
        fname = folder.find("kml:name", ns)
        if fname is not None and fname.text == "HP":
            hp_folder = folder
            for placemark in folder.findall("kml:Placemark", ns):
                pname = placemark.find("kml:name", ns)
                point = placemark.find(".//kml:Point", ns)
                if point is not None:
                    coords_text = point.find("kml:coordinates", ns).text.strip()
                    lon, lat, *_ = map(float, coords_text.split(","))
                    hp_points.append((placemark, pname, Point(lon, lat)))
            break

    moved_count = 0
    if hp_folder is not None:
        for placemark, pname, pt in hp_points:
            # cek kotak terdekat
            nearest_poly = None
            nearest_dist = float("inf")
            nearest_centroid = None

            for poly, centroid in zip(kotak_polygons, kotak_centroids):
                d = poly.distance(pt)
                if d < nearest_dist:
                    nearest_dist = d
                    nearest_poly = poly
                    nearest_centroid = centroid

            if nearest_poly is not None:
                # pindahkan ke centroid kotak
                new_lon, new_lat = nearest_centroid.x, nearest_centroid.y
                coord_el = placemark.find(".//kml:coordinates", ns)
                if coord_el is not None:
                    coord_el.text = f"{new_lon},{new_lat},0"
                    moved_count += 1

    # Simpan hasil
    out_dir = tempfile.mkdtemp()
    new_kml = os.path.join(out_dir, "hp_to_kotak.kml")
    tree.write(new_kml, encoding="utf-8", xml_declaration=True)

    with open(new_kml, "rb") as f:
        st.download_button("📥 Download KML Hasil", f, file_name="hp_to_kotak.kml")

    st.success(f"✅ Selesai! {moved_count} titik HP dipindahkan ke tengah kotak terdekat.")
