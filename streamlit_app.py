import streamlit as st
import ezdxf
from shapely.geometry import Polygon
import math
import io

# ----------------- FUNGSI BANTU -----------------
def text_polygon(x, y, text, height, rotation, width_factor=1.0):
    """Bentuk bounding box teks sebagai polygon shapely"""
    text_length = len(text) * height * width_factor * 0.6
    w, h = text_length, height
    pts = [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)]

    rad = math.radians(rotation)
    rot_pts = [(x + px*math.cos(rad) - py*math.sin(rad),
                y + px*math.sin(rad) + py*math.cos(rad)) for px, py in pts]
    return Polygon(rot_pts)

def polygon_orientation(poly, mode="shortest"):
    """Cari orientasi polygon berdasarkan sisi tertentu"""
    coords = list(poly.exterior.coords)
    best_len, angle = None, 0
    for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length > 1e-6:
            ang = math.degrees(math.atan2(dy, dx))
            if mode == "shortest":
                if best_len is None or length < best_len:
                    best_len, angle = length, ang
            elif mode == "longest":
                if best_len is None or length > best_len:
                    best_len, angle = length, ang
    return angle

def fit_text_in_polygon(poly, text, init_height=2.5, margin=0.9, orient_mode="shortest"):
    """
    Cari posisi teks dalam polygon:
    - mulai dari centroid
    - kalau nabrak garis, geser sedikit
    - auto scale & orientasi sesuai pilihan
    """
    cx, cy = poly.centroid.x, poly.centroid.y

    if orient_mode == "horizontal":
        angle = 0
    elif orient_mode == "vertical":
        angle = 90
    elif orient_mode == "longest":
        angle = polygon_orientation(poly, "longest")
    else:
        angle = polygon_orientation(poly, "shortest")

    search_offsets = [(0,0),(1,0),(-1,0),(0,1),(0,-1),
                      (1,1),(-1,1),(1,-1),(-1,-1)]

    h = init_height
    for _ in range(50):  # iterasi sampai dapat ukuran pas
        for dx, dy in search_offsets:
            tx, ty = cx + dx*h*0.3, cy + dy*h*0.3
            tp = text_polygon(tx, ty, text, h, angle)
            if poly.contains(tp.buffer(-0.05)):  # buffer biar ga nabrak
                return tx, ty, h, angle
        h *= 0.9  # kalau gagal, perkecil
    return cx, cy, init_height*0.3, angle  # fallback

# ----------------- PROSES DXF -----------------
def process_dxf(input_bytes, texts, orient_mode="shortest"):
    doc = ezdxf.read(io.BytesIO(input_bytes))
    msp = doc.modelspace()

    polygons = []
    for e in msp.query("LWPOLYLINE"):
        if e.closed and len(e) >= 3:
            pts = [(p[0], p[1]) for p in e]
            poly = Polygon(pts)
            if poly.is_valid and poly.area > 1:
                polygons.append(poly)

    for poly, text in zip(polygons, texts):
        x, y, h, rot = fit_text_in_polygon(poly, text, orient_mode=orient_mode)
        msp.add_text(
            text,
            dxfattribs={
                "height": h,
                "layer": "KAPLING_TEXT",
                "color": 6  # magenta
            }
        ).set_pos((x, y), align="MIDDLE_CENTER").set_rotation(rot)

    out = io.BytesIO()
    doc.write(out)
    return out.getvalue()

# ----------------- STREAMLIT UI -----------------
st.title("📐 Auto Label Kapling DXF")
st.write("Upload DXF lalu otomatis diberi teks sesuai polygon.")

uploaded_file = st.file_uploader("Upload file DXF", type=["dxf"])
start_num = st.number_input("Nomor awal", min_value=1, value=1)
end_num = st.number_input("Nomor akhir", min_value=10, value=10)

orient_mode = st.selectbox(
    "Orientasi teks",
    options=["shortest", "longest", "horizontal", "vertical"],
    format_func=lambda x: {
        "shortest": "Sisi Terpendek",
        "longest": "Sisi Terpanjang",
        "horizontal": "Horizontal (0°)",
        "vertical": "Vertical (90°)"
    }[x]
)

if uploaded_file is not None:
    if st.button("Proses DXF"):
        texts = [f"NN-{i}" for i in range(start_num, end_num+1)]
        input_bytes = uploaded_file.read()
        output_bytes = process_dxf(input_bytes, texts, orient_mode=orient_mode)

        st.download_button(
            "💾 Download DXF Hasil",
            data=output_bytes,
            file_name="rapi_kapling.dxf",
            mime="application/dxf"
        )
