import streamlit as st
import ezdxf
from shapely.geometry import Polygon
import math
import tempfile
import os
import numpy as np

st.set_page_config(page_title="Rapikan Teks DXF Kapling", layout="wide")

# =========================
# Helper Functions
# =========================

def text_polygon(x, y, text, height, rotation, width_factor=1.0):
    """Bentuk bounding box teks sebagai polygon shapely"""
    text_length = len(text) * height * width_factor * 0.6
    w, h = text_length, height
    pts = [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)]

    rad = math.radians(rotation)
    rot_pts = [(x + px*math.cos(rad) - py*math.sin(rad),
                y + px*math.sin(rad) + py*math.cos(rad)) for px, py in pts]
    return Polygon(rot_pts)


def shortest_edge_angle(poly: Polygon):
    """Hitung sudut sisi terpendek polygon"""
    coords = list(poly.exterior.coords)
    min_len = 1e9
    best_angle = 0
    for i in range(len(coords)-1):
        x1, y1 = coords[i]
        x2, y2 = coords[i+1]
        dx, dy = x2-x1, y2-y1
        length = math.hypot(dx, dy)
        if length < min_len and length > 1e-6:
            min_len = length
            best_angle = math.degrees(math.atan2(dy, dx))
    return best_angle


def fit_text_in_polygon(poly, text, init_height=2.5, margin=0.9, mode="shortest"):
    """
    Cari posisi teks dalam polygon:
    - mulai dari centroid
    - auto scale
    - auto rotate (ikut mode)
    - geser sedikit kalau nabrak garis
    """
    cx, cy = poly.centroid.x, poly.centroid.y
    search_offsets = [(0,0),(1,0),(-1,0),(0,1),(0,-1),
                      (1,1),(-1,1),(1,-1),(-1,-1)]

    # pilih rotasi sesuai mode
    if mode == "shortest":
        base_rot = shortest_edge_angle(poly)
        rotations = [base_rot, base_rot+90]
    else:  # horizontal / vertical
        rotations = [0, 90]

    for rotation in rotations:
        h = init_height
        for _ in range(50):  # iterasi scale
            for dx, dy in search_offsets:
                tx, ty = cx + dx*h*0.3, cy + dy*h*0.3
                tp = text_polygon(tx, ty, text, h, rotation)
                if poly.contains(tp.buffer(-0.01)):  # aman dalam polygon
                    return tx, ty, h, rotation
            h *= 0.9
    return cx, cy, init_height*0.3, rotations[0]  # fallback


def process_dxf(doc, mode="shortest"):
    msp = doc.modelspace()

    # Ambil polygon dari LWPOLYLINE tertutup
    polygons = []
    for e in msp.query("LWPOLYLINE"):
        if e.closed and len(e) >= 3:
            pts = [(p[0], p[1]) for p in e]
            poly = Polygon(pts)
            if poly.is_valid:
                polygons.append(poly)

    texts = list(msp.query("TEXT MTEXT"))

    adjusted = 0
    for t in texts:
        try:
            text_str = t.dxf.text
            x, y = t.dxf.insert[0], t.dxf.insert[1]
        except Exception:
            continue

        # cari polygon terdekat
        nearest_poly = None
        nearest_dist = 1e9
        for poly in polygons:
            dist = poly.centroid.distance(Polygon([(x,y)]))
            if dist < nearest_dist:
                nearest_poly = poly
                nearest_dist = dist

        if nearest_poly:
            tx, ty, h, rot = fit_text_in_polygon(nearest_poly, text_str, init_height=t.dxf.height, mode=mode)
            t.dxf.insert = (tx, ty)
            t.dxf.height = h
            t.dxf.rotation = rot
            adjusted += 1

    st.success(f"✅ {adjusted} teks berhasil dirapikan.")
    return doc

# =========================
# Streamlit UI
# =========================

st.title("📐 Rapikan Teks DXF Kapling (Posisi Tetap, Auto Scale & Rotate)")

uploaded_file = st.file_uploader("Unggah file DXF", type=["dxf"])
mode = st.radio("Mode rotasi teks", ["shortest", "horizontal"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        doc = ezdxf.readfile(tmp_path)
        doc = process_dxf(doc, mode=mode)

        doc.saveas(tmp_path)

        with open(tmp_path, "rb") as f:
            st.download_button(
                "💾 Download DXF Hasil",
                data=f.read(),
                file_name="rapi_kapling.dxf",
                mime="application/dxf"
            )

    except Exception as e:
        st.error(f"❌ Gagal memproses file DXF: {e}")
    finally:
        os.unlink(tmp_path)
