# ====================================================
# 📌 DXF Rapikan Polyline jadi Kotak + Text Magenta
# Streamlit Version
# ====================================================

import streamlit as st
import ezdxf
import networkx as nx
from shapely.geometry import Polygon, Point
import math
import io

# --- Fungsi bantu ---
def text_polygon(x, y, text, height, rotation, width_factor=1.0):
    """Bentuk bounding box teks sebagai polygon shapely"""
    text_length = len(text) * height * width_factor * 0.6
    w, h = text_length, height
    pts = [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)]

    rad = math.radians(rotation)
    rot_pts = [(x + px*math.cos(rad) - py*math.sin(rad),
                y + px*math.sin(rad) + py*math.cos(rad)) for px, py in pts]
    return Polygon(rot_pts)

def place_text_inside_polygon(poly, text_entity):
    """Letakkan teks di tengah polygon, rotate jika kena garis"""
    cx, cy = poly.centroid.x, poly.centroid.y
    h = text_entity.dxf.height
    text = text_entity.dxf.text

    for rotation in [0, 90]:
        tp = text_polygon(cx, cy, text, h, rotation)
        if poly.contains(tp.buffer(-0.01)):
            return cx, cy, rotation

    return cx, cy, 0

def build_graph_from_polylines(msp):
    """Bangun graph dari semua polyline layer GARIS HOMEPASS"""
    G = nx.Graph()
    for e in msp.query("LWPOLYLINE"):
        if e.dxf.layer.upper() == "GARIS HOMEPASS":
            pts = [(p[0], p[1]) for p in e]
            for i in range(len(pts) - 1):
                p1, p2 = pts[i], pts[i+1]
                G.add_edge(p1, p2)
            if e.closed:
                G.add_edge(pts[-1], pts[0])
    return G

def extract_polygons_from_graph(G):
    """Deteksi siklus/loop pada graph → jadikan polygon"""
    cycles = nx.cycle_basis(G)
    polygons = []
    for cycle in cycles:
        if len(cycle) >= 3:
            poly = Polygon(cycle)
            if poly.is_valid and poly.area > 1.0:
                polygons.append(poly)
    return polygons

# --- Proses DXF ---
def process_dxf(file_bytes):
    doc = ezdxf.read(io.BytesIO(file_bytes))
    msp = doc.modelspace()

    # Step 1: graph dari garis layer GARIS HOMEPASS
    G = build_graph_from_polylines(msp)

    # Step 2: cari polygon dari loop
    polygons = extract_polygons_from_graph(G)

    # Step 3: ambil semua teks FEATURE_LABEL warna magenta
    texts = [e for e in msp.query("TEXT") 
             if e.dxf.color == 6 and e.dxf.layer.upper() == "FEATURE_LABEL"]

    success = 0
    for text_entity in texts:
        # cari polygon terdekat dengan centroid teks sekarang
        text_point = Point(text_entity.dxf.insert[0], text_entity.dxf.insert[1])
        nearest_poly = min(polygons, key=lambda p: p.centroid.distance(text_point))

        # rapikan posisi teks
        x, y, rot = place_text_inside_polygon(nearest_poly, text_entity)
        text_entity.dxf.insert = (x, y)
        text_entity.dxf.rotation = rot
        text_entity.dxf.color = 6
        text_entity.dxf.layer = "FEATURE_LABEL"
        success += 1

    out_buf = io.BytesIO()
    doc.write(out_buf)
    return out_buf.getvalue(), success, len(polygons)

# ====================================================
# 🚀 Streamlit UI
# ====================================================
st.title("📌 DXF Rapikan Polyline jadi Kotak + Text Magenta")

uploaded_file = st.file_uploader("Upload DXF file", type=["dxf"])

if uploaded_file is not None:
    st.info("Memproses file, tunggu sebentar...")

    dxf_bytes = uploaded_file.read()
    output_bytes, count_text, count_poly = process_dxf(dxf_bytes)

    st.success(f"✅ {count_text} teks FEATURE_LABEL dirapikan ke {count_poly} kotak hasil deteksi")

    st.download_button(
        label="⬇️ Download DXF Hasil",
        data=output_bytes,
        file_name="rapi_homepass.dxf",
        mime="application/dxf"
    )
