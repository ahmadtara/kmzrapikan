import streamlit as st
import ezdxf
import numpy as np
import math
import tempfile
import os
from shapely.geometry import Polygon, Point
from shapely.affinity import rotate, scale, translate

st.set_page_config(page_title="Rapikan Teks DXF Kapling", layout="wide")

# =======================
# Helper Functions
# =======================

def polyline_to_polygon(poly):
    """Konversi polyline/LWPOLYLINE jadi shapely Polygon"""
    try:
        pts = [tuple(v) for v in poly.get_points("xy")]
    except Exception:
        pts = [tuple(v[:2]) for v in poly.points()]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return Polygon(pts)


def text_polygon(x, y, text, height, rotation):
    """Bentuk polygon teks (kotak bounding box) berdasarkan posisi, tinggi, dan rotasi"""
    # estimasi lebar teks (0.6 * tinggi * jumlah karakter)
    width = len(text) * height * 0.6
    box = Polygon([(0,0), (width,0), (width,height), (0,height)])
    # transformasi: rotate → translate ke posisi (x,y)
    box = rotate(box, rotation, origin=(0,0), use_radians=False)
    box = translate(box, xoff=x, yoff=y)
    return box


def fit_text_in_polygon(poly, text, init_height=2.5, margin=0.9):
    """
    Cari tinggi & rotasi teks agar muat dalam polygon.
    1. Coba horizontal
    2. Kalau gagal, coba vertical (90°)
    3. Scale down sampai muat
    """
    cx, cy = poly.centroid.x, poly.centroid.y

    for rotation in [0, 90]:
        h = init_height
        for _ in range(50):  # coba iterasi scale down
            tp = text_polygon(cx, cy, text, h, rotation)
            if poly.contains(tp):
                return cx, cy, h, rotation
            h *= 0.9  # perkecil
    # fallback: pasang di centroid, ukuran minimal
    return cx, cy, init_height*0.3, 0


def process_dxf(doc):
    msp = doc.modelspace()

    # Ambil semua polyline jadi polygon kapling
    polygons = []
    for e in msp.query("LWPOLYLINE POLYLINE"):
        try:
            poly = polyline_to_polygon(e)
            if poly.is_valid and poly.area > 0:
                polygons.append(poly)
        except Exception:
            continue

    texts = list(msp.query("TEXT MTEXT"))

    st.write(f"📦 Jumlah kapling (polygon) terdeteksi: {len(polygons)}")
    st.write(f"🔤 Jumlah teks terdeteksi: {len(texts)}")

    adjusted = 0
    for t in texts:
        try:
            label = t.dxf.text
        except Exception:
            continue

        # cari polygon terdekat ke teks
        x, y = t.dxf.insert[0], t.dxf.insert[1]
        p = Point(x,y)
        nearest_poly = min(polygons, key=lambda g: p.distance(g))

        # atur ulang posisi + tinggi + rotasi
        cx, cy, h, rot = fit_text_in_polygon(nearest_poly, label, init_height=t.dxf.height)

        t.dxf.insert = (cx, cy)
        t.dxf.height = h
        t.dxf.rotation = rot

        adjusted += 1

    st.success(f"✅ {adjusted} teks berhasil disesuaikan (auto scale + auto rotate supaya masuk polygon).")
    return doc


# =======================
# Streamlit UI
# =======================

st.title("📐 Rapikan Teks DXF Kapling (Polygon-aware)")

uploaded_file = st.file_uploader("Unggah file DXF", type=["dxf"])

if uploaded_file:
    # Simpan sementara file asli
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        # Buka DXF asli
        doc = ezdxf.readfile(tmp_path)
        doc = process_dxf(doc)

        # Simpan kembali ke file sementara (overwrite)
        doc.saveas(tmp_path)

        # Download langsung file asli yang sudah di-rapikan
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
