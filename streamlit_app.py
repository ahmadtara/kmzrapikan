import ezdxf
from shapely.geometry import Polygon
import math

# --- Fungsi bantu ---
def text_polygon(x, y, text, height, rotation, width_factor=1.0):
    """Bentuk bounding box teks sebagai polygon shapely"""
    text_length = len(text) * height * width_factor * 0.6
    w, h = text_length, height
    pts = [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)]

    rad = math.radians(rotation)
    rot_pts = [(x + px*math.cos(rad) - py*math.sin(rad),
                y + px*math.sin(rad) + py*math.cos(rad)) for px, py in pts]
    return Polygon(rot_pts)

def fit_text_in_polygon(poly, text, init_height=2.5, margin=0.9):
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
        for _ in range(50):  # iterasi sampai dapat ukuran pas
            for dx, dy in search_offsets:
                tx, ty = cx + dx*h*0.3, cy + dy*h*0.3
                tp = text_polygon(tx, ty, text, h, rotation)
                if poly.contains(tp.buffer(-0.01)):  # cek aman dalam polygon
                    return tx, ty, h, rotation
            h *= 0.9  # kalau gagal, perkecil
    return cx, cy, init_height*0.3, 0  # fallback

# --- Proses DXF ---
def process_dxf(input_file, output_file, texts):
    doc = ezdxf.readfile(input_file)
    msp = doc.modelspace()

    # Ambil polygon dari LWPOLYLINE
    polygons = []
    for e in msp.query("LWPOLYLINE"):
        if e.closed and len(e) >= 3:
            pts = [(p[0], p[1]) for p in e]
            poly = Polygon(pts)
            if poly.is_valid:
                polygons.append(poly)

    # Tambah teks ke tiap polygon
    for poly, text in zip(polygons, texts):
        x, y, h, rot = fit_text_in_polygon(poly, text)
        msp.add_text(
            text,
            dxfattribs={
                "height": h,
                "layer": "KAPLING_TEXT",
                "color": 6  # magenta
            }
        ).set_pos((x, y), align="MIDDLE_CENTER").set_rotation(rot)

    doc.saveas(output_file)

# --- Contoh pemakaian ---
if __name__ == "__main__":
    input_dxf = "kapling_input.dxf"
    output_dxf = "rapi_kapling.dxf"
    texts = [f"NN-{i}" for i in range(120, 140)]  # contoh teks
    process_dxf(input_dxf, output_dxf, texts)
