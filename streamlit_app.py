import streamlit as st
import tempfile, os
from lxml import etree as ET
from shapely.geometry import Point, Polygon
import zipfile

st.title("📍 Pindahkan HP ke Tengah Kotak (Path 4 Titik)")

uploaded_file = st.file_uploader("Upload file KML", type=["kml"])

if uploaded_file is not None:
    # Simpan file sementara
    with tempfile.NamedTemporaryFile(delete=False, suffix=".kml") as tmp:
        tmp.write(uploaded_file.read())
        kml_file = tmp.name

    # Parse file
    parser = ET.XMLParser(recover=True, encoding="utf-8")
    tree = ET.parse(kml_file, parser=parser)
    root = tree.getroot()
    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    # --- Ambil kotak dari folder KOTAK ---
    kotak_polygons = []
    kotak_centroids = []

    for folder in root.findall(".//kml:Folder", ns):
        fname = folder.find("kml:name", ns)
        if fname is not None and fname.text == "KOTAK":
            for placemark in folder.findall("kml:Placemark", ns):
                line = placemark.find(".//kml:LineString", ns)
                if line is not None:
                    coords_text = line.find("kml:coordinates", ns).text.strip()
                    coords = [(float(x.split(",")[0]), float(x.split(",")[1])) 
                              for x in coords_text.split()]
                    if len(coords) == 4:  # path 4 titik → kotak
                        # bentuk polygon manual
                        poly = Polygon(coords + [coords[0]])  # tutup poly
                        kotak_polygons.append(poly)
                        kotak_centroids.append(poly.centroid)

    # --- Ambil HP ---
    hp_points = []
    for folder in root.findall(".//kml:Folder", ns):
        fname = folder.find("kml:name", ns)
        if fname is not None and fname.text == "HP":
            for placemark in folder.findall("kml:Placemark", ns):
                point = placemark.find(".//kml:Point", ns)
                if point is not None:
                    coords_text = point.find("kml:coordinates", ns).text.strip()
                    lon, lat, *_ = map(float, coords_text.split(","))
                    hp_points.append((placemark, Point(lon, lat)))

    # --- Pindahkan HP ke centroid kotak ---
    moved_count = 0
    for placemark, pt in hp_points:
        for poly, centroid in zip(kotak_polygons, kotak_centroids):
            if poly.contains(pt):
                new_coords = f"{centroid.x},{centroid.y},0"
                point_el = placemark.find(".//kml:Point/kml:coordinates", ns)
                if point_el is not None:
                    point_el.text = new_coords
                    moved_count += 1
                break

    # Simpan hasil
    out_dir = tempfile.mkdtemp()
    new_kml = os.path.join(out_dir, "hp_mid_kotak.kml")
    tree.write(new_kml, encoding="utf-8", xml_declaration=True)

    with open(new_kml, "rb") as f:
        st.download_button("📥 Download Hasil KML", f, file_name="hp_mid_kotak.kml")

    st.success(f"✅ Selesai! {moved_count} titik HP dipindahkan ke tengah kotak.")
