import ezdxf
import math
from shapely.geometry import Polygon, Point

def is_rectangle(polygon, angle_tol=10, aspect_ratio_tol=0.2):
    """Cek apakah polygon adalah persegi panjang"""
    if len(polygon) != 5:  # 4 titik + 1 titik penutup
        return False

    coords = polygon[:-1]
    if len(coords) != 4:
        return False

    # Hitung vektor sisi
    def angle_between(v1, v2):
        dot = v1[0]*v2[0] + v1[1]*v2[1]
        mag1 = math.hypot(v1[0], v1[1])
        mag2 = math.hypot(v2[0], v2[1])
        cosang = dot / (mag1 * mag2)
        return math.degrees(math.acos(max(-1, min(1, cosang))))

    for i in range(4):
        p1, p2, p3 = coords[i], coords[(i+1)%4], coords[(i+2)%4]
        v1 = (p2[0]-p1[0], p2[1]-p1[1])
        v2 = (p3[0]-p2[0], p3[1]-p2[1])
        ang = angle_between(v1, v2)
        if not (90-angle_tol <= ang <= 90+angle_tol):
            return False

    # Cek aspek rasio
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    width = max(xs)-min(xs)
    height = max(ys)-min(ys)
    if width == 0 or height == 0:
        return False
    aspect = max(width/height, height/width)
    if aspect > 10:  # terlalu panjang → abaikan
        return False

    return True

def move_texts_to_rectangles(input_file, output_file, target_layer="KOTAK"):
    doc = ezdxf.readfile(input_file)
    msp = doc.modelspace()

    rectangles = []
    for e in msp:
        if e.dxftype() == "LWPOLYLINE" and e.closed:
            points = [(p[0], p[1]) for p in e]
            if target_layer and e.dxf.layer != target_layer:
                continue
            if is_rectangle(points):
                poly = Polygon(points)
                if 2 < poly.bounds[2]-poly.bounds[0] < 50 and 2 < poly.bounds[3]-poly.bounds[1] < 50:
                    rectangles.append((poly, e))

    texts = [e for e in msp if e.dxftype() in ["TEXT", "MTEXT"]]

    assigned = 0
    for text in texts:
        pt = Point(text.dxf.insert[0], text.dxf.insert[1])
        for poly, entity in rectangles:
            if poly.contains(pt):
                cx, cy = poly.centroid.x, poly.centroid.y
                text.dxf.insert = (cx, cy)

                # Sesuaikan tinggi teks agar muat
                minx, miny, maxx, maxy = poly.bounds
                box_w = maxx - minx
                box_h = maxy - miny
                max_size = min(box_w, box_h) * 0.4
                if text.dxf.height > max_size:
                    text.dxf.height = max_size

                assigned += 1
                break

    print(f"📦 Jumlah kotak terdeteksi: {len(rectangles)}")
    print(f"🔤 Jumlah teks terdeteksi: {len(texts)}")
    print(f"✅ {assigned} teks berhasil dirapikan ke tengah kotak.")

    doc.saveas(output_file)

# === Jalankan ===
move_texts_to_rectangles("PKB001962.dxf", "output_rapi.dxf", target_layer="KOTAK")
