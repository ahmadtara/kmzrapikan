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
    """
    Hitung bounding box dan sudut rotasi (derajat) dari POLYLINE/LWPOLYLINE.
    Angle dihitung dari sisi bawah kotak relatif sumbu X.
    """
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

def fit_text_height_within_box(text_entity, box_bounds, margin=0.9):
    """
    Skalakan tinggi teks agar muat dalam kotak, tanpa mengubah posisi.
    margin: persentase ruang kosong dalam kotak
    """
    x1, y1, x2, y2 = box_bounds
    box_w = abs(x2 - x1) * margin
    box_h = abs(y2 - y1) * margin
    try:
        text_w = len(text_entity.dxf.text) * text_entity.dxf.height * 0.6
        text_h = text_entity.dxf.height
    except Exception:
        return text_entity.dxf.height
    scale = min(box_w / max(text_w, 1e-6), box_h / max(text_h, 1e-6))
    return max(0.1, text_entity.dxf.height * scale)

def process_dxf(doc):
    msp = doc.modelspace()

    # Ambil semua polyline sebagai kotak sementara
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
            # Scale tinggi teks agar muat kotak
            new_h = fit_text_height_within_box(t, nearest_box["bounds"], margin=0.9)
            t.dxf.height = new_h
            # Rotate teks sesuai kotak
            try:
                t.dxf.rotation = nearest_box["angle"]
            except Exception:
                pass
            adjusted += 1

    st.success(f"✅ Selesai! {adjusted} teks berhasil disesuaikan agar muat kotak.")
    return doc

# =======================
# Streamlit UI
# =======================

st.title("📐 Rapikan Teks DXF Kapling (Tetap di Template Asli)")

uploaded_file = st.file_uploader("Unggah file DXF", type=["dxf"])

if uploaded_file:
    # Simpan sementara file asli
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        # Buka DXF asli
        doc = ezdxf.readfile(tmp_path)
        doc = process_dxf(doc)

        # Simpan kembali ke file sementara (overwrite)
        doc.saveas(tmp_path)

        # Download langsung file asli yang sudah di-rapikan
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
