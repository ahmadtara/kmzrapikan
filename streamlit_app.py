import streamlit as st
import zipfile
import os
import math
import tempfile
import ezdxf
from xml.etree import ElementTree as ET
from pyproj import Transformer
import numpy as np

st.set_page_config(page_title="KMZ → DXF Rapi", layout="wide")

def extract_kmz(kmz_file):
    with zipfile.ZipFile(kmz_file, 'r') as zf:
        kml_filename = [n for n in zf.namelist() if n.endswith('.kml')][0]
        with zf.open(kml_filename) as kml_file:
            tree = ET.parse(kml_file)
    return tree

def parse_coordinates(coord_string):
    coords = []
    for coord in coord_string.strip().split():
        lon, lat, *_ = map(float, coord.split(','))
        coords.append((lon, lat))
    return coords

def rotate_points(points, angle_rad):
    """Rotasi semua titik berdasarkan sudut (radian)."""
    rotation_matrix = np.array([
        [math.cos(angle_rad), -math.sin(angle_rad)],
        [math.sin(angle_rad),  math.cos(angle_rad)]
    ])
    rotated = []
    for x, y in points:
        vec = np.array([x, y])
        rot = rotation_matrix @ vec
        rotated.append((rot[0], rot[1]))
    return rotated

def create_dxf(coords_list, texts, output_dxf):
    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    kotak_count = 0
    teks_count = 0

    for coords in coords_list:
        poly = msp.add_lwpolyline(coords, close=True, dxfattribs={"layer": "KOTAK"})
        kotak_count += 1

    for text, box in texts:
        if not box:
            continue
        min_x = min(p[0] for p in box)
        max_x = max(p[0] for p in box)
        min_y = min(p[1] for p in box)
        max_y = max(p[1] for p in box)

        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        box_w = max_x - min_x
        box_h = max_y - min_y

        # ukuran teks adaptif biar tidak tabrakan
        tinggi_teks = min(box_h * 0.4, box_w / (len(text) * 0.6))

        if tinggi_teks <= 0:
            continue

        txt = msp.add_text(
            text,
            dxfattribs={"height": tinggi_teks, "style": "Standard"}
        )
        txt.set_placement((center_x, center_y), align="MIDDLE_CENTER")
        teks_count += 1

    doc.saveas(output_dxf)
    return kotak_count, teks_count

def kmz_to_dxf(kmz_file, output_dxf):
    tree = extract_kmz(kmz_file)
    root = tree.getroot()

    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

    coords_list = []
    texts = []

    # ambil semua poligon
    for placemark in root.findall(".//kml:Placemark", ns):
        polygon = placemark.find(".//kml:Polygon", ns)
        name = placemark.find("kml:name", ns)

        if polygon is not None:
            coord_string = polygon.find(".//kml:coordinates", ns).text
            coords = parse_coordinates(coord_string)
            coords_proj = [transformer.transform(lon, lat) for lon, lat in coords]
            coords_list.append(coords_proj)

            if name is not None:
                texts.append((name.text, coords_proj))

    # cari sudut rotasi terbaik → rata-rata sisi terpanjang biar peta lurus
    all_edges = []
    for coords in coords_list:
        for i in range(len(coords)):
            x1, y1 = coords[i]
            x2, y2 = coords[(i + 1) % len(coords)]
            dx, dy = x2 - x1, y2 - y1
            if dx == dy == 0:
                continue
            angle = math.atan2(dy, dx)
            all_edges.append(angle)

    if all_edges:
        # pilih orientasi dominan (kelipatan 90 derajat)
        avg_angle = np.median(all_edges)
        best_angle = round(avg_angle / (math.pi / 2)) * (math.pi / 2)
    else:
        best_angle = 0

    # rotasi semua koordinat
    rotated_coords_list = []
    for coords in coords_list:
        rotated_coords_list.append(rotate_points(coords, -best_angle))

    rotated_texts = []
    for text, coords in texts:
        rotated_texts.append((text, rotate_points(coords, -best_angle)))

    kotak_count, teks_count = create_dxf(rotated_coords_list, rotated_texts, output_dxf)
    return kotak_count, teks_count

# STREAMLIT UI
st.title("📐 KMZ → DXF Rapi")

uploaded_file = st.file_uploader("Upload file KMZ", type=["kmz"])

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".kmz") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_out:
        output_path = tmp_out.name

    kotak_count, teks_count = kmz_to_dxf(tmp_path, output_path)

    st.success(f"📦 Jumlah kotak terdeteksi: {kotak_count}\n\n🔤 Jumlah teks dirapikan: {teks_count}")
    with open(output_path, "rb") as f:
        st.download_button("⬇️ Download DXF", f, file_name="hasil_rapi.dxf")
