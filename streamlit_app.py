import streamlit as st
import ezdxf
import io
from shapely.geometry import Polygon, Point

st.set_page_config(page_title="DXF Rapikan Teks", layout="wide")

st.title("📐 DXF Rapikan Teks (warna pink ke tengah kotak)")

uploaded_file = st.file_uploader("Upload file DXF", type=["dxf"])

if uploaded_file:
    # Baca DXF dari buffer
    data = uploaded_file.read()
    buffer = io.BytesIO(data)
    doc = ezdxf.read(buffer)

    # Ambil modelspace
    msp = doc.modelspace()

    # Ambil semua polyline (kotak)
    kotak_list = []
    for e in msp.query("LWPOLYLINE"):
        if e.closed and len(e) >= 4:
            points = [(p[0], p[1]) for p in e]
            kotak_list.append(Polygon(points))

    # Rapikan semua teks warna pink
    for text in msp.query("TEXT"):
        if text.dxf.color == 6:  # warna pink
            pos = Point(text.dxf.insert)

            # Cari kotak terdekat
            nearest_kotak = None
            nearest_dist = float("inf")
            for kotak in kotak_list:
                dist = kotak.distance(pos)
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest_kotak = kotak

            # Kalau ada kotak, pindahkan teks ke tengah
            if nearest_kotak:
                cx, cy = nearest_kotak.centroid.x, nearest_kotak.centroid.y
                text.dxf.insert = (cx, cy)
                text.dxf.halign = 1  # Tengah
                text.dxf.valign = 2  # Middle

    # Simpan hasil
    output = io.BytesIO()
    doc.write(output)
    output.seek(0)

    st.download_button(
        "💾 Download DXF Rapi",
        output,
        file_name="hasil_rapi.dxf",
        mime="application/dxf",
    )

    st.success("✅ Semua teks warna pink sudah dipindah ke tengah kotak terdekat.")
