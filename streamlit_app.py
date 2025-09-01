import streamlit as st
import ezdxf
from shapely.geometry import Polygon, Point
import math
import io

st.set_page_config(page_title="Rapikan Label DXF", layout="wide")

st.title("📐 Rapikan Label Homepass di DXF")

uploaded_file = st.file_uploader("Upload file DXF", type=["dxf"])

def main_angle_of_polygon(poly):
    """Cari sudut sisi terpanjang polygon"""
    max_len = 0
    best_angle = 0
    coords = list(poly.exterior.coords)
    for i in range(len(coords)-1):
        x1, y1 = coords[i]
        x2, y2 = coords[i+1]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length > max_len:
            max_len = length
            best_angle = math.degrees(math.atan2(dy, dx))
    return best_angle

if uploaded_file:
    # Baca DXF
    in_bytes = uploaded_file.read()
    temp_input = io.BytesIO(in_bytes)
    doc = ezdxf.read(temp_input)
    msp = doc.modelspace()

    # Ambil polyline & teks
    polylines = [e for e in msp.query("LWPOLYLINE")]
    texts = [e for e in msp.query("TEXT")] + [e for e in msp.query("MTEXT")]

    # Simpan centroid polygon
    poly_centroids = []
    for pl in polylines:
        pts = [(p[0], p[1]) for p in pl]
        if len(pts) > 2:
            try:
                polygon = Polygon(pts)
                if polygon.is_valid and not polygon.is_empty:
                    centroid = polygon.centroid
                    poly_centroids.append((polygon, centroid))
            except Exception:
                pass

    # Geser & putar teks
    for t in texts:
        if isinstance(t.dxf.insert, tuple):
            x, y = t.dxf.insert[0], t.dxf.insert[1]
        else:
            x, y = t.dxf.insert.x, t.dxf.insert.y
        point = Point(x, y)

        target_poly = None
        for poly, centroid in poly_centroids:
            if poly.contains(point):
                target_poly = poly
                t.dxf.insert = (centroid.x, centroid.y, 0)
                t.dxf.rotation = main_angle_of_polygon(poly)
                break

    # Simpan hasil ke buffer
    output_buf = io.BytesIO()
    doc.write(output_buf)
    output_buf.seek(0)

    st.success("✅ File berhasil dirapikan!")
    st.download_button(
        label="⬇️ Download DXF Rapi",
        data=output_buf,
        file_name="DXF_RAPI.dxf",
        mime="application/dxf"
    )
