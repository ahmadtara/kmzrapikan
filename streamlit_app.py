import ezdxf
from shapely.geometry import Polygon
import math
import sys
import os

# --- Fungsi bantu ---
def text_polygon(x, y, text, height, rotation, width_factor=1.0):
    """Bentuk bounding box teks sebagai polygon shapely"""
    text_length = len(text) * height * width_factor * 0.6
    w, h = text_length, height
    pts = [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)]

    rad = math.radians(rotation)
    rot_pts = [
        (x + px*math.cos(rad) - py*math.sin(rad),
         y + px*math.sin(rad) + py*math.cos(rad))
        for px, py in pts
    ]
    return Polygon(rot_pts)

def fit_text_in_polygon(poly, text, init_height=2.5, margin=0.9, min_height=0.5):
    """
    Cari posisi teks dalam polygon:
    - mulai dari centroid
    - kalau nabrak garis, geser sedikit
    - auto scale & auto rotate
    """
    cx, cy = poly.centroid.x, poly.centroid.y
    search_offsets = [(0,0),(1,0),(-1,0),(0,1),(0,-1),
                      (1,1),(-1,1),(1,-1),(-1,-1)]

    for rotation in [0, 90]:  # coba horizontal dulu, lalu vertical
        h = init_height
        while h > min_height:
            for dx, dy in search_offsets:
                tx, ty = cx + dx*h*0.3, cy + dy*h*0.3
                tp = text_polygon(tx, ty, text, h, rotation)
                if poly.contains(tp.buffer(-0.01)):  # cek aman dalam polygon
                    return tx, ty, h, rotation
            h *= margin  # perkecil kalau gagal
    return cx, cy, min_height, 0  # fallback

# --- Proses DXF ---
def process_dxf(input_file, output_file, texts):
    try:
        doc = ezdxf.readfile(input_file)
    except Exception as e:
        print(f"❌ Gagal baca DXF: {e}")
        sys.exit(1)

    msp = doc.modelspace()

    # Buat layer khusus teks jika belum ada
    if "KAPLING_TEXT" not in doc.layers:
        doc.layers.new(name="KAPLING_TEXT")

    # Ambil polygon dari LWPOLYLINE
    polygons = []
    for e in msp.query("LWPOLYLINE"):
        if e.closed and len(e) >= 3:
            pts = [(p[0], p[1]) for p in e]
            poly = Polygon(pts)
            if poly.is_valid and poly.area > 1e-3:
                polygons.append(poly)

    if not polygons:
        print("⚠️ Tidak ada polygon valid ditemukan!")
        return

    # Tambah teks ke tiap polygon (cocokkan jumlah)
    for i, poly in enumerate(polygons):
        label = texts[i] if i < len(texts) else f"LOT-{i+1}"
        x, y, h, rot = fit_text_in_polygon(poly, label)
        msp.add_text(
            label,
            dxfattribs={
                "height": h,
                "layer": "KAPLING_TEXT",
                "color": 6  # magenta
            }
        ).set_pos((x, y), align="MIDDLE_CENTER").set_rotation(rot)

    doc.saveas(output_file)
    print(f"✅ Selesai! Hasil disimpan di {output_file}")

# --- Contoh pemakaian ---
if __name__ == "__main__":
    input_dxf = sys.argv[1] if len(sys.argv) > 1 else "kapling_input.dxf"
    output_dxf = sys.argv[2] if len(sys.argv) > 2 else "rapi_kapling.dxf"
    texts = [f"NN-{i}" for i in range(120, 140)]
    process_dxf(input_dxf, output_dxf, texts)
