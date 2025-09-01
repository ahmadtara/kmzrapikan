import streamlit as st
import ezdxf
import tempfile
from shapely.geometry import Point, Polygon
import math

st.set_page_config(page_title="Perapihan Label DXF", layout="wide")
st.title("📐 Rapikan Label DXF ke Tengah Kotak")

uploaded_file = st.file_uploader("Upload file DXF", type=["dxf"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    doc = ezdxf.readfile(tmp_path)
    msp = doc.modelspace()

    # --- Ambil semua kotak ---
    kotak_list = []

    # 1. LWPOLYLINE
    for e in msp.query("LWPOLYLINE"):
        if e.closed:
            points = [(p[0], p[1]) for p in e]
            kotak_list.append((Polygon(points), e))

    # 2. POLYLINE (3D polyline lama)
    for e in msp.query("POLYLINE"):
        if e.is_closed:
            points = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
            kotak_list.append((Polygon(points), e))

    # 3. Gabungan LINE → cek per layer apakah closed loop
    # (optional, agak panjang logikanya, bisa aku buat kalau perlu)

    st.write(f"📦 Jumlah kotak terdeteksi: {len(kotak_list)}")

    # --- Ambil semua teks ---
    text_entities = []

    # 1. TEXT dan MTEXT
    for e in msp.query("TEXT MTEXT"):
        text_entities.append(e)

    # 2. INSERT dengan ATTRIB
    for insert in msp.query("INSERT"):
        for attrib in insert.attribs:
            text_entities.append(attrib)

    st.write(f"🔤 Jumlah teks terdeteksi: {len(text_entities)}")

    moved = 0
    for text in text_entities:
        try:
            if hasattr(text.dxf, "insert"):
                x, y, *_ = text.dxf.insert
            else:
                x, y = text.dxf.align_point.x, text.dxf.align_point.y
        except:
            continue

        point = Point(x, y)

        nearest_poly = None
        nearest_dist = float("inf")
        for poly, entity in kotak_list:
            dist = poly.distance(point)
            if dist < nearest_dist:
                nearest_poly = poly
                nearest_dist = dist

        if nearest_poly:
            cx, cy = nearest_poly.centroid.x, nearest_poly.centroid.y
            text.dxf.insert = (cx, cy)

            coords = list(nearest_poly.exterior.coords)
            if len(coords) >= 2:
                dx = coords[1][0] - coords[0][0]
                dy = coords[1][1] - coords[0][1]
                angle = math.degrees(math.atan2(dy, dx))
                text.dxf.rotation = angle

            moved += 1

    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_out:
        output_path = tmp_out.name
        doc.saveas(output_path)

    st.success(f"✅ Selesai! {moved} teks berhasil dirapikan ke tengah kotak.")

    with open(output_path, "rb") as f:
        st.download_button("⬇️ Download DXF Rapi", f, file_name="rapi.dxf", mime="application/dxf")
