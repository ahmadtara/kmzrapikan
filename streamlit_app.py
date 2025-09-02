import streamlit as st
import ezdxf
from shapely.geometry import Polygon, Point
import math
import io

# --- Fungsi bantu ---
def text_polygon(x, y, text, height, rotation, width_factor=1.0):
    text_length = len(text) * height * width_factor * 0.6
    w, h = text_length, height
    pts = [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)]

    rad = math.radians(rotation)
    rot_pts = [(x + px*math.cos(rad) - py*math.sin(rad),
                y + px*math.sin(rad) + py*math.cos(rad)) for px, py in pts]
    return Polygon(rot_pts)

def fit_text_in_polygon(poly, text, init_height=2.5, margin=0.9, mode="shortest"):
    cx, cy = poly.centroid.x, poly.centroid.y
    search_offsets = [(0,0),(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)]

    # pilih mode rotasi
    rotations = [0] if mode == "horizontal" else [0, 90]

    for rotation in rotations:
        h = init_height
        for _ in range(50):
            for dx, dy in search_offsets:
                tx, ty = cx + dx*h*0.3, cy + dy*h*0.3
                tp = text_polygon(tx, ty, text, h, rotation)
                if poly.contains(tp.buffer(-0.01)):
                    return tx, ty, h, rotation
            h *= 0.9
    return cx, cy, init_height*0.3, 0

# --- Proses DXF ---
def process_dxf(doc, mode="shortest"):
    msp = doc.modelspace()

    # Ambil polygon
    polygons = []
    for e in msp.query("LWPOLYLINE"):
        if e.closed and len(e) >= 3:
            pts = [(p[0], p[1]) for p in e]
            poly = Polygon(pts)
            if poly.is_valid:
                polygons.append(poly)

    # Ambil teks
    texts = list(msp.query("TEXT")) + list(msp.query("MTEXT")) \
          + list(msp.query("ATTRIB")) + list(msp.query("ATTDEF"))

    st.info(f"📌 Ditemukan {len(polygons)} polygon & {len(texts)} teks di file.")

    adjusted = 0
    for t in texts:
        try:
            if t.dxftype() == "MTEXT":
                text_str = t.text
                x, y = t.dxf.insert[:2]
            else:
                text_str = t.dxf.text
                x, y = t.dxf.insert[:2]
        except Exception:
            continue

        # cari polygon terdekat
        nearest_poly = None
        nearest_dist = 1e9
        for poly in polygons:
            dist = poly.centroid.distance(Point(x, y))
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

# --- Debug Entities ---
def debug_entities(doc):
    msp = doc.modelspace()
    all_entities = list(msp)
    st.write("📌 Jumlah total entitas:", len(all_entities))

    text_like = []
    for e in all_entities:
        if e.dxftype() in ["TEXT", "MTEXT", "ATTRIB", "ATTDEF"]:
            text_like.append(e)

    st.write("📌 Jumlah entitas teks-like:", len(text_like))
    for e in text_like[:20]:  # tampilkan contoh max 20
        try:
            if e.dxftype() == "MTEXT":
                txt = e.text
            else:
                txt = e.dxf.text
        except:
            txt = "(tidak bisa dibaca)"
        st.write(f"➡️ {e.dxftype()} | Layer: {e.dxf.layer} | Isi: {txt[:50]}")

# --- Streamlit UI ---
st.title("📐 DXF Kapling Rapi")

uploaded_file = st.file_uploader("Upload file DXF", type=["dxf"])
mode = st.radio("Mode rotasi teks", ["shortest", "horizontal"])

action = st.selectbox("Pilih Aksi", ["Rapikan Teks", "Debug Entities"])

if uploaded_file is not None:
    doc = ezdxf.read(uploaded_file)

    if action == "Rapikan Teks":
        new_doc = process_dxf(doc, mode=mode)
        buf = io.BytesIO()
        new_doc.saveas(buf)
        st.download_button("💾 Download DXF hasil", data=buf.getvalue(), file_name="rapi_kapling.dxf")
    elif action == "Debug Entities":
        debug_entities(doc)
