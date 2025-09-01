import streamlit as st
import ezdxf
import numpy as np
import tempfile
import os

st.set_page_config(page_title="DXF → DXF Rapikan Teks", layout="wide")

def polyline_bounds(poly):
    """Hitung bounding box dari POLYLINE/LWPOLYLINE"""
    points = [p for p in poly.get_points('xy')]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)

def center_of_bounds(bounds):
    xmin, ymin, xmax, ymax = bounds
    return (xmin + xmax) / 2, (ymin + ymax) / 2

def fit_text_height(text, bounds, margin=0.9):
    """Skalakan tinggi teks agar muat dalam kotak"""
    xmin, ymin, xmax, ymax = bounds
    box_w = xmax - xmin
    box_h = ymax - ymin
    if box_w <= 0 or box_h <= 0:
        return text.dxf.height
    factor = margin * min(box_w, box_h)
    return factor

def process_dxf(doc):
    msp = doc.modelspace()

    # kumpulkan kotak
    boxes = []
    for e in msp.query("LWPOLYLINE POLYLINE"):
        if e.closed:  # hanya polygon tertutup
            boxes.append(polyline_bounds(e))

    # kumpulkan teks
    texts = list(msp.query("TEXT MTEXT"))

    st.write(f"📦 Jumlah kotak terdeteksi: {len(boxes)}")
    st.write(f"🔤 Jumlah teks terdeteksi: {len(texts)}")

    moved = 0
    for t in texts:
        x, y = t.dxf.insert[0], t.dxf.insert[1]

        # cari kotak terdekat
        nearest_box = None
        nearest_dist = 1e9
        for b in boxes:
            cx, cy = center_of_bounds(b)
            dist = np.hypot(cx - x, cy - y)
            if dist < nearest_dist:
                nearest_box = b
                nearest_dist = dist

        if nearest_box:
            cx, cy = center_of_bounds(nearest_box)
            # pindahkan teks ke tengah kotak
            t.dxf.insert = (cx, cy)
            # sesuaikan tinggi teks agar muat
            new_h = fit_text_height(t, nearest_box, margin=0.4)
            if new_h > 0:
                t.dxf.height = new_h
            moved += 1

    st.success(f"✅ Selesai! {moved} teks berhasil dirapikan ke tengah kotak.")
    return doc


st.title("📐 DXF → DXF Rapikan Teks ke Tengah Kotak")

uploaded = st.file_uploader("Upload file DXF", type=["dxf"])
if uploaded:
    temp_in = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf")
    temp_in.write(uploaded.read())
    temp_in.close()

    try:
        doc = ezdxf.readfile(temp_in.name)
    except Exception as e:
        st.error(f"Gagal membaca DXF: {e}")
        os.unlink(temp_in.name)
        st.stop()

    # proses
    doc = process_dxf(doc)

    # simpan hasil
    temp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".dxf")
    doc.saveas(temp_out.name)
    temp_out.close()

    with open(temp_out.name, "rb") as f:
        st.download_button(
            "💾 Download DXF hasil",
            f,
            file_name="hasil_rapi.dxf",
            mime="application/dxf",
        )

    os.unlink(temp_in.name)
    os.unlink(temp_out.name)
