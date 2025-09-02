import streamlit as st
import ezdxf
import math
import tempfile
import os
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
from shapely.affinity import rotate, translate

# ====================
# Fungsi bantu
# ====================

def text_polygon(x, y, text, height, rotation, width_factor=1.0):
    """Buat bounding box teks (aproksimasi) sebagai polygon Shapely"""
    text_length = len(text) * height * width_factor * 0.6
    w, h = text_length, height
    pts = [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)]
    poly = Polygon(pts)
    return rotate(translate(poly, xoff=x, yoff=y), rotation, origin=(x, y))

def fit_text_in_polygon(poly, text, init_height=2.5, margin=0.9):
    """
    Cari posisi teks dalam polygon:
    - mulai dari centroid
    - kalau nabrak garis, coba geser beberapa titik
    - auto scale & auto rotate (0°, 90°, atau sisi panjang)
    """
    cx, cy = poly.centroid.x, poly.centroid.y
    rotations = [0, 90]

    # deteksi sisi panjang polygon (pakai bounding box terorientasi)
    minx, miny, maxx, maxy = poly.bounds
    if (maxx - minx) > (maxy - miny):
        rotations.append(0)  # horizontal
    else:
        rotations.append(90)  # vertical

    search_offsets = [(0,0),(1,0),(-1,0),(0,1),(0,-1),
                      (1,1),(-1,1),(1,-1),(-1,-1)]

    for rotation in rotations:
        h = init_height
        for _ in range(40):  # iterasi tinggi
            for dx, dy in search_offsets:
                tx, ty = cx + dx*h*0.5, cy + dy*h*0.5
                tp = text_polygon(tx, ty, text, h, rotation)
                if poly.contains(tp.buffer(-0.05)):  # aman dalam polygon
                    return tx, ty, h, rotation
            h *= 0.9
    return cx, cy, init_height*0.3, 0  # fallback


def process_dxf(input_file, output_file, texts):
    doc = ezdxf.readfile(input_file)
    msp = doc.modelspace()

    # Ambil polygon dari LWPOLYLINE
    polygons = []
    for e in msp.query("LWPOLYLINE"):
        if e.closed and len(e) >= 3:
            pts = [(p[0], p[1]) for p in e]
            poly = Polygon(pts)
            if poly.is_valid and poly.area > 1e-3:
                polygons.append(poly)

    # Tambahkan teks sesuai urutan
    for poly, text in zip(polygons, texts):
        x, y, h, rot = fit_text_in_polygon(poly, text)
        msp.add_text(
            text,
            dxfattribs={
                "height": h,
                "layer": "KAPLING_TEXT",
                "color": 6
            }
        ).set_pos((x, y), align="MIDDLE_CENTER").set_rotation(rot)

    doc.saveas(output_file)
    return polygons, texts


def preview(polygons, texts):
    """Tampilkan preview polygon + teks"""
    fig, ax = plt.subplots()
    for poly, text in zip(polygons, texts):
        x, y = poly.exterior.xy
        ax.plot(x, y, "k-")
        cx, cy = poly.centroid.x, poly.centroid.y
        ax.text(cx, cy, text, ha="center", va="center", fontsize=8, color="magenta")
    ax.set_aspect("equal")
    st.pyplot(fig)


# ====================
# Streamlit UI
# ====================

st.set_page_config(page_title="📐 Rapikan Teks DXF Kapling", layout="wide")
st.title("📐 Rapikan Teks DXF Kapling")

uploaded_file = st.file_uploader("Unggah file DXF", type=["dxf"])

if uploaded_file:
    texts_input = st.text_area("Masukkan daftar teks (pisahkan dengan koma)", "K-01,K-02,K-03")
    texts = [t.strip() for t in texts_input.split(",") if t.strip()]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp_in:
        tmp_in.write(uploaded_file.read())
        tmp_in_path = tmp_in.name

    tmp_out_path = tmp_in_path.replace(".dxf", "_out.dxf")

    try:
        polygons, used_texts = process_dxf(tmp_in_path, tmp_out_path, texts)
        st.success("✅ DXF berhasil diproses!")

        # Preview
        preview(polygons, used_texts)

        # Download hasil
        with open(tmp_out_path, "rb") as f:
            st.download_button(
                "💾 Download DXF Hasil",
                data=f.read(),
                file_name="rapi_kapling.dxf",
                mime="application/dxf"
            )

    except Exception as e:
        st.error(f"❌ Gagal memproses file DXF: {e}")

    finally:
        os.unlink(tmp_in_path)
        if os.path.exists(tmp_out_path):
            os.unlink(tmp_out_path)
