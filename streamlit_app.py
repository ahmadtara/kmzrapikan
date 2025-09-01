import streamlit as st
import ezdxf
import tempfile
from shapely.geometry import Point, Polygon
import math

st.set_page_config(page_title="Perapihan Label DXF", layout="wide")
st.title("📐 Rapikan Label DXF ke Tengah Kotak")

uploaded_file = st.file_uploader("Upload file DXF", type=["dxf"])

def collect_polygons(msp):
    kotak_list = []

    # 1. Ambil semua POLYLINE tertutup
    for e in msp.query("LWPOLYLINE"):
        if e.closed:
            pts = [(p[0], p[1]) for p in e]
            poly = Polygon(pts)
            if poly.is_valid and poly.area > 0:
                kotak_list.append(poly)

    # 2. Ambil kotak dari gabungan LINE
    lines = list(msp.query("LINE"))
    used = set()
    for i, l1 in enumerate(lines):
        if i in used:
            continue
        connected = [(l1.dxf.start.x, l1.dxf.start.y),
                     (l1.dxf.end.x, l1.dxf.end.y)]
        members = [i]

        # Cari garis lain yang nyambung
        for j, l2 in enumerate(lines):
            if j in used or j == i:
                continue
            pts = [(l2.dxf.start.x, l2.dxf.start.y),
                   (l2.dxf.end.x, l2.dxf.end.y)]
            if any(p in connected for p in pts):
                connected.extend(pts)
                members.append(j)

        unique_pts = list(set(connected))
        if len(unique_pts) == 4:  # kemungkinan kotak
            poly = Polygon(unique_pts)
            if poly.is_valid and poly.area > 0:
                kotak_list.append(poly)
                used.update(members)

    # 3. Bongkar INSERT (block reference)
    for insert in msp.query("INSERT"):
        try:
            for e in insert.virtual_entities():
                if e.dxftype() == "LWPOLYLINE" and e.closed:
                    pts = [(p[0], p[1]) for p in e]
                    poly = Polygon(pts)
                    if poly.is_valid and poly.area > 0:
                        kotak_list.append(poly)
                elif e.dxftype() == "LINE":
                    pts = [(e.dxf.start.x, e.dxf.start.y),
                           (e.dxf.end.x, e.dxf.end.y)]
                    # (opsional: bisa diproses mirip step 2 kalau perlu)
        except Exception:
            continue

    return kotak_list

if uploaded_file:
    # Simpan file sementara
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    # Baca DXF
    doc = ezdxf.readfile(tmp_path)
    msp = doc.modelspace()

    # Kumpulkan semua kotak
    kotak_list = collect_polygons(msp)

    # Ambil semua TEXT & MTEXT
    text_entities = list(msp.query("TEXT MTEXT"))

    moved = 0
    for text in text_entities:
        # Ambil posisi text
        try:
            x, y, *_ = text.dxf.insert
        except Exception:
            continue
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
            # Hitung centroid kotak
            cx, cy = nearest_poly.centroid.x, nearest_poly.centroid.y

            # Geser text ke tengah kotak
            text.dxf.insert = (cx, cy)

            # Rotasi teks mengikuti arah sisi pertama
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

    st.write(f"📦 Jumlah kotak terdeteksi: {len(kotak_list)}")
    st.write(f"🔤 Jumlah teks terdeteksi: {len(text_entities)}")
    st.success(f"✅ Selesai! {moved} teks berhasil dirapikan ke tengah kotak.")

    with open(output_path, "rb") as f:
        st.download_button("⬇️ Download DXF Rapi", f, file_name="rapi.dxf", mime="application/dxf")
