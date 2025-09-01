import streamlit as st
import ezdxf
import tempfile
from shapely.geometry import Point, Polygon
import math

st.set_page_config(page_title="Perapihan Label DXF", layout="wide")

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

    # Ambil semua polyline (kotak)
    kotak_list = []
    for e in msp.query("LWPOLYLINE"):
        if e.closed:  # hanya polyline tertutup
            points = [(p[0], p[1]) for p in e]
            kotak_list.append((Polygon(points), e))

    # Ambil semua TEXT & MTEXT
    text_entities = list(msp.query("TEXT MTEXT"))

    moved = 0
    for text in text_entities:
        x, y, *_ = text.dxf.insert
        point = Point(x, y)

        # Cari kotak terdekat
        nearest_poly = None
        nearest_dist = float("inf")
        for poly, entity in kotak_list:
            dist = poly.distance(point)
            if dist < nearest_dist:
                nearest_poly = poly
                nearest_dist = dist

        if nearest_poly:
            # Hitung centroid kotak
            cx, cy = nearest_poly.centroid.x, nearest_poly.centroid.y

            # Geser text ke tengah kotak
            text.dxf.insert = (cx, cy)

            # Rotasi teks mengikuti orientasi kotak (ambil arah sisi pertama)
            coords = list(nearest_poly.exterior.coords)
            if len(coords) >= 2:
                dx = coords[1][0] - coords[0][0]
                dy = coords[1][1] - coords[0][1]
                angle = math.degrees(math.atan2(dy, dx))
                text.dxf.rotation = angle

            moved += 1

    # Simpan hasil rapikan
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_out:
        output_path = tmp_out.name
        doc.saveas(output_path)

    st.success(f"✅ Selesai! {moved} teks berhasil dirapikan ke tengah kotak.")

    with open(output_path, "rb") as f:
        st.download_button("⬇️ Download DXF Rapi", f, file_name="rapi.dxf", mime="application/dxf")
