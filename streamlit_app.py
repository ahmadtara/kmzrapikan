import streamlit as st
import ezdxf
import io
from shapely.geometry import Polygon

st.set_page_config(page_title="DXF Rapikan Teks", layout="wide")

st.title("📐 DXF Rapikan Teks di Tengah Kotak")

uploaded_file = st.file_uploader("Upload file DXF", type=["dxf"])

if uploaded_file is not None:
    # Baca DXF dari buffer (BytesIO)
    data = uploaded_file.read()
    buffer = io.BytesIO(data)
    doc = ezdxf.read(buffer)

    msp = doc.modelspace()

    st.success("✅ File DXF berhasil dibaca")

    # Cari polyline yang berbentuk kotak
    kotak_list = []
    for e in msp.query("LWPOLYLINE"):
        if e.closed and len(e) >= 4:
            points = [(p[0], p[1]) for p in e]
            polygon = Polygon(points)
            if polygon.is_valid and polygon.area > 0:
                kotak_list.append((polygon.centroid.x, polygon.centroid.y))

    # Tambahkan teks di tengah kotak
    counter = 1
    for cx, cy in kotak_list:
        label = f"NN-{counter:02d}"
        msp.add_text(
            label,
            dxfattribs={"height": 1.0}
        ).set_pos((cx, cy), align="MIDDLE_CENTER")
        counter += 1

    # Simpan hasil ke buffer baru
    output_buffer = io.BytesIO()
    doc.write(output_buffer)
    output_buffer.seek(0)

    st.download_button(
        "⬇️ Download DXF Rapih",
        data=output_buffer,
        file_name="DXF_RAPIH.dxf",
        mime="application/dxf"
    )
