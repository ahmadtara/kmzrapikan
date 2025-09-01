import streamlit as st
import ezdxf
import math
import os
from shapely.geometry import Polygon, Point

st.set_page_config(page_title="Rapikan Teks DXF", layout="wide")

def get_polygons(doc):
    polygons = []
    for entity in doc.modelspace().query("LWPOLYLINE POLYLINE"):
        try:
            if entity.dxftype() == "LWPOLYLINE" and entity.closed:
                points = [(p[0], p[1]) for p in entity.get_points()]
                polygons.append(Polygon(points))
            elif entity.dxftype() == "POLYLINE" and entity.is_closed:
                points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                polygons.append(Polygon(points))
        except Exception:
            continue
    return polygons

def get_best_fit_text_height(text, box_w, box_h):
    """Hitung tinggi teks agar muat dalam kotak"""
    if not text:
        return 1.0
    # estimasi lebar teks per karakter ~0.6 * tinggi
    est_height_x = (box_w / (len(text) * 0.6))
    est_height_y = box_h
    return min(est_height_x, est_height_y) * 0.8  # sedikit margin

def get_longest_side_angle(polygon):
    """Ambil sudut sisi terpanjang polygon"""
    coords = list(polygon.exterior.coords)
    max_len = 0
    best_angle = 0
    for i in range(len(coords) - 1):
        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]
        length = math.hypot(x2 - x1, y2 - y1)
        if length > max_len:
            max_len = length
            best_angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
    return best_angle

def process_dxf(input_path, output_path):
    doc = ezdxf.readfile(input_path)
    msp = doc.modelspace()
    polygons = get_polygons(doc)

    text_entities = [e for e in msp.query("TEXT") if e.dxf.color == 6 or e.dxf.layer.upper() == "FEATURE_LABEL"]

    fixed_count = 0
    for text in text_entities:
        pt = Point(text.dxf.insert[0], text.dxf.insert[1])

        nearest_poly = None
        nearest_dist = 1e9
        for poly in polygons:
            if poly.contains(pt):
                nearest_poly = poly
                break
            else:
                dist = pt.distance(poly)
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest_poly = poly

        if nearest_poly:
            minx, miny, maxx, maxy = nearest_poly.bounds
            center_x, center_y = (minx + maxx) / 2, (miny + maxy) / 2
            width, height = (maxx - minx), (maxy - miny)

            # ukur tinggi teks otomatis
            new_height = get_best_fit_text_height(text.dxf.text, width, height)

            # rotasi sesuai sisi terpanjang
            angle = get_longest_side_angle(nearest_poly)

            text.dxf.insert = (center_x, center_y)
            text.dxf.height = new_height
            text.dxf.rotation = angle
            fixed_count += 1

    doc.saveas(output_path)
    return len(polygons), len(text_entities), fixed_count

st.title("📐 Rapikan Teks DXF ke Tengah Kotak")

uploaded_file = st.file_uploader("Upload file DXF", type=["dxf"])
if uploaded_file:
    input_path = uploaded_file.name
    with open(input_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    output_path = "rapi_output.dxf"
    kotak, teks, sukses = process_dxf(input_path, output_path)

    st.success(f"📦 Jumlah kotak terdeteksi: {kotak}\n\n🔤 Jumlah teks terdeteksi: {teks}\n\n✅ {sukses} teks berhasil dirapikan ke tengah kotak.")

    with open(output_path, "rb") as f:
        st.download_button("📥 Download Hasil DXF", f, file_name="rapi_output.dxf")
