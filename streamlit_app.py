import streamlit as st
import ezdxf
import tempfile
from shapely.geometry import Polygon, Point
import math

st.set_page_config(page_title="📐 Rapikan Label DXF", layout="wide")
st.title("📐 Rapikan Label DXF ke Tengah Kotak")

uploaded_file = st.file_uploader("Upload file DXF", type=["dxf"])

if uploaded_file:
    # Simpan file sementara
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    # Baca DXF
    doc = ezdxf.readfile(tmp_path)
    msp = doc.modelspace()

    kotak_list = []

    # Ambil kotak dari LWPOLYLINE
    for e in msp.query("LWPOLYLINE"):
        points = [(p[0], p[1]) for p in e]
        if e.closed and len(points) >= 4:
            poly = Polygon(points)
            if poly.is_valid and poly.area > 0:
                kotak_list.append(poly)

    # Ambil kotak dari POLYLINE
    for e in msp.query("POLYLINE"):
        points = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
        if len(points) >= 4:
            if points[0] != points[-1]:  # tutup loop
                points.append(points[0])
            poly = Polygon(points)
            if poly.is_valid and poly.area > 0:
                kotak_list.append(poly)

    # Ambil semua teks (TEXT & MTEXT) di layer FEATURE_LABEL
    text_entities = [t for t in msp.query("TEXT MTEXT") if t.dxf.layer == "FEATURE_LABEL"]

    moved = 0
    for text in text_entities:
        if text.dxftype() == "TEXT":
            x, y = text.dxf.insert[0], text.dxf.insert[1]
        else:  # MTEXT
            x, y = text.dxf.insert[0], text.dxf.insert[1]

        point = Point(x, y)

        # Cari kotak terdekat
        nearest_poly = None
        nearest_dist = float("inf")
        for poly in kotak_list:
            dist = poly.distance(point)
            if dist < nearest_dist:
                nearest_poly = poly
                nearest_dist = dist

        if nearest_poly:
            # Geser teks ke centroid kotak
            cx, cy = nearest_poly.centroid.x, nearest_poly.centroid.y
            text.dxf.insert = (cx, cy)
            text.dxf.rotation = 0  # reset rotasi biar lurus
            moved += 1

    # Simpan hasil rapikan
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_out:
        output_path = tmp_out.name
        doc.saveas(output_path)

    st.info(f"📦 Jumlah kotak terdeteksi: {len(kotak_list)}")
    st.info(f"🔤 Jumlah teks terdeteksi: {len(text_entities)}")
    st.success(f"✅ Selesai! {moved} teks berhasil dirapikan ke tengah kotak.")

    with open(output_path, "rb") as f:
        st.download_button("⬇️ Download DXF Rapi", f, file_name="rapi.dxf", mime="application/dxf")
