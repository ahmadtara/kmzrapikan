import streamlit as st
import ezdxf
import numpy as np
import math
import tempfile
import os

st.set_page_config(page_title="Rapikan Teks DXF Kapling", layout="wide")

# =======================
# Helper Functions
# =======================

def polyline_bounds_and_angle(poly):
    """Hitung bounding box & sudut rotasi polyline"""
    try:
        pts = [tuple(v) for v in poly.get_points("xy")]
    except Exception:
        pts = [tuple(v[:2]) for v in poly.points()]
    xs, ys = zip(*pts)
    xmin, ymin, xmax, ymax = min(xs), min(ys), max(xs), max(ys)

    if len(pts) >= 2:
        dx = pts[1][0] - pts[0][0]
        dy = pts[1][1] - pts[0][1]
        angle = math.degrees(math.atan2(dy, dx))
    else:
        angle = 0
    return (xmin, ymin, xmax, ymax), angle


def fit_text_in_box(text_entity, box_bounds, margin=0.8):
    """Atur tinggi, lebar, dan rotasi teks agar muat dalam kotak"""
    x1, y1, x2, y2 = box_bounds
    box_w = abs(x2 - x1) * margin
    box_h = abs(y2 - y1) * margin

    text_str = text_entity.dxf.text
    n_chars = max(len(text_str), 1)

    # tinggi awal
    h = min(text_entity.dxf.height, box_h)

    # estimasi panjang teks (faktor 0.6 perkiraan proporsi font)
    est_len = n_chars * h * 0.6
    width_factor = 1.0

    # kalau teks lebih lebar dari kotak -> kurangi width_factor
    if est_len > box_w:
        width_factor = max(box_w / est_len, 0.5)  # minimal 0.5 biar masih kebaca

    # update tinggi & width_factor
    text_entity.dxf.height = h
    text_entity.dxf.width = width_factor

    # cek lagi, kalau masih lebih lebar -> rotate vertical
    final_len = n_chars * h * width_factor * 0.6
    if final_len > box_w:
        text_entity.dxf.rotation = 90  # vertikal
    else:
        text_entity.dxf.rotation = 0   # default horizontal

    # posisikan ke tengah kotak
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    text_entity.dxf.insert = (cx, cy)


def process_dxf(doc):
    msp = doc.modelspace()

    # Ambil semua polyline sebagai kotak
    boxes = []
    for e in msp.query("LWPOLYLINE POLYLINE"):
        try:
            bounds, angle = polyline_bounds_and_angle(e)
            boxes.append({"bounds": bounds, "angle": angle})
        except Exception:
            continue

    texts = list(msp.query("TEXT MTEXT"))

    st.write(f"📦 Jumlah kotak (polyline) terdeteksi: {len(boxes)}")
    st.write(f"🔤 Jumlah teks terdeteksi: {len(texts)}")

    adjusted = 0
    for t in texts:
        try:
            x, y = t.dxf.insert[0], t.dxf.insert[1]
        except Exception:
            continue

        # Cari kotak terdekat
        nearest_box = None
        nearest_dist = 1e9
        for b in boxes:
            xmin, ymin, xmax, ymax = b["bounds"]
            cx = (xmin + xmax) / 2
            cy = (ymin + ymax) / 2
            dist = np.hypot(cx - x, cy - y)
            if dist < nearest_dist:
                nearest_box = b
                nearest_dist = dist

        if nearest_box:
            # rapikan teks agar muat dalam kotak
            fit_text_in_box(t, nearest_box["bounds"], margin=0.8)
            adjusted += 1

    st.success(f"✅ Selesai! {adjusted} teks berhasil disesuaikan.")
    return doc

# =======================
# Streamlit UI
# =======================

st.title("📐 Rapikan Teks DXF Kapling (Auto Scale, Width Factor, Rotate Vertical jika nabrak)")

uploaded_file = st.file_uploader("Unggah file DXF", type=["dxf"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        doc = ezdxf.readfile(tmp_path)
        doc = process_dxf(doc)

        doc.saveas(tmp_path)

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
