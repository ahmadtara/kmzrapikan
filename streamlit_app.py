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
    Skalakan tinggi teks agar muat dalam kotak.
    Posisi teks tidak diubah.
    """
    x1, y1, x2, y2 = box_bounds
    box_h = abs(y2 - y1) * margin
    # tinggi teks baru = minimum antara tinggi asli dan tinggi kotak
    return min(text_entity.dxf.height, box_h)


def process_dxf(doc, auto_vertical=True):
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
            # ---- SCALE TEKS sesuai orientasi kotak ----
            new_h = fit_text_height_within_box(t, nearest_box["bounds"], margin=0.9)
            t.dxf.height = new_h

            xmin, ymin, xmax, ymax = nearest_box["bounds"]
            box_w = abs(xmax - xmin) * 0.9
            box_h = abs(ymax - ymin) * 0.9

            text_len = len(t.dxf.text)
            est_w = text_len * t.dxf.height * 0.6  # estimasi panjang teks

            if auto_vertical and est_w > box_w:
                # Kalau masih kepanjangan → rotate vertical
                t.dxf.rotation = nearest_box["angle"] + 90
                # scale ulang biar muat ke tinggi box
                if text_len > 0:
                    t.dxf.height = min(t.dxf.height, box_h / (text_len * 0.6))
            else:
                # Normal sejajar kotak
                t.dxf.rotation = nearest_box["angle"]

            adjusted += 1

    st.success(f"✅ {adjusted} teks berhasil disesuaikan (auto scale + auto rotate vertical jika nabrak).")
    return doc

# =======================
# Streamlit UI
# =======================

st.title("📐 Rapikan Teks DXF Kapling (Posisi Tetap, Hanya Scale & Rotate)")

uploaded_file = st.file_uploader("Unggah file DXF", type=["dxf"])
auto_vertical = st.checkbox("Aktifkan auto-rotate vertical jika teks kepanjangan", value=True)

if uploaded_file:
    # Simpan sementara file asli
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        # Buka DXF asli
        doc = ezdxf.readfile(tmp_path)
        doc = process_dxf(doc, auto_vertical=auto_vertical)

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
