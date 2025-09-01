import streamlit as st
import tempfile, os, math
import ezdxf
from ezdxf.enums import TextEntityAlignment, MTextAttachmentPoint
from shapely.geometry import Polygon, Point

st.set_page_config(page_title="DXF: Rapikan Teks di Tengah Kotak", layout="wide")
st.title("📐 Rapikan Teks ke Tengah Kotak (DXF)")

# ---- util geometry ----
def close_ring(coords):
    if len(coords) >= 3 and coords[0] != coords[-1]:
        coords = coords + [coords[0]]
    return coords

def poly_from_lwpoly(e):
    # ambil XY saja; abaikan bulge
    pts = [(p[0], p[1]) for p in e.get_points("xy")]
    pts = close_ring(pts)
    return Polygon(pts) if len(pts) >= 4 else None

def poly_from_polyline(e):
    pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
    pts = close_ring(pts)
    return Polygon(pts) if len(pts) >= 4 else None

def is_rectangle_coords(coords, angle_tol_deg=12):
    """coords: 5 titik (tertutup). True jika 4 sisi & tiap sudut ~90°"""
    if len(coords) != 5:
        return False
    # buang titik duplikat berturut-turut
    core = [coords[0]]
    for p in coords[1:]:
        if p != core[-1]:
            core.append(p)
    if len(core) != 5:
        return False
    c = core[:-1]
    if len(c) != 4:
        return False

    def ang(v1, v2):
        dot = v1[0]*v2[0] + v1[1]*v2[1]
        m1 = math.hypot(v1[0], v1[1])
        m2 = math.hypot(v2[0], v2[1])
        if m1 == 0 or m2 == 0:
            return 0
        cos = max(-1.0, min(1.0, dot/(m1*m2)))
        return math.degrees(math.acos(cos))

    for i in range(4):
        x1,y1 = c[i]
        x2,y2 = c[(i+1)%4]
        x3,y3 = c[(i+2)%4]
        v1 = (x2-x1, y2-y1)
        v2 = (x3-x2, y3-y2)
        a = ang(v1, v2)
        if not (90-angle_tol_deg <= a <= 90+angle_tol_deg):
            return False
    return True

def rect_side_lengths(coords):
    """kembalikan (width, height) berdasarkan 4 sisi."""
    c = coords[:-1]
    lens = []
    for i in range(4):
        x1,y1 = c[i]
        x2,y2 = c[(i+1)%4]
        lens.append(math.hypot(x2-x1, y2-y1))
    lens.sort(reverse=True)
    return lens[0], lens[1]  # panjang, lebar

def rect_orientation(coords):
    """sudut sisi terpanjang (derajat)"""
    c = coords[:-1]
    best_len = -1
    best_ang = 0
    for i in range(4):
        x1,y1 = c[i]; x2,y2 = c[(i+1)%4]
        L = math.hypot(x2-x1, y2-y1)
        if L > best_len:
            best_len = L
            best_ang = math.degrees(math.atan2(y2-y1, x2-x1))
    return best_ang

def best_text_height(s, box_w, box_h, margin=0.85):
    """Estimasi tinggi teks agar muat di kotak (TEXT/MTEXT).
       Lebar per karakter ~ 0.6 * height."""
    n = max(1, len(s))
    h_by_w = box_w / (0.6 * n)
    h_by_h = box_h
    return max(1e-6, min(h_by_w, h_by_h) * margin)

# ---- UI Controls (punya default aman) ----
st.sidebar.header("Pengaturan")
min_side = st.sidebar.number_input("Min sisi kotak (unit gambar)",  value=2.0, min_value=0.0, step=0.5)
max_side = st.sidebar.number_input("Max sisi kotak (unit gambar)",  value=50.0, min_value=0.0, step=1.0)
angle_tol = st.sidebar.slider("Toleransi sudut kotak (°)", 5, 20, 12)
capture_factor = st.sidebar.slider("Ambang jarak teks→kotak (d/minSide)", 0.1, 2.0, 0.5, 0.05)
margin_factor = st.sidebar.slider("Margin isi teks (% dari muatan)", 0.60, 0.95, 0.85, 0.01)
only_pink = st.sidebar.checkbox("Hanya teks warna pink (AutoCAD color=6)", value=True)
layer_text_filter = st.sidebar.text_input("Filter layer teks (opsional, mis. FEATURE_LABEL)", value="FEATURE_LABEL")

uploaded = st.file_uploader("Upload DXF", type=["dxf"])

if uploaded:
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = os.path.join(tmpdir, "input.dxf")
        with open(in_path, "wb") as f:
            f.write(uploaded.read())

        doc = ezdxf.readfile(in_path)
        msp = doc.modelspace()

        # --- kumpulkan RECTANGLES saja ---
        rectangles = []
        for e in msp.query("LWPOLYLINE"):
            try:
                poly = poly_from_lwpoly(e)
                if not poly or not poly.is_valid or poly.area <= 0:
                    continue
                coords = list(poly.exterior.coords)
                if not is_rectangle_coords(coords, angle_tol):
                    continue
                w, h = rect_side_lengths(coords)
                if not (min_side <= min(w,h) <= max_side and min_side <= max(w,h) <= max_side*10):
                    continue
                rectangles.append((poly, coords, w, h))
            except Exception:
                pass

        for e in msp.query("POLYLINE"):
            try:
                poly = poly_from_polyline(e)
                if not poly or not poly.is_valid or poly.area <= 0:
                    continue
                coords = list(poly.exterior.coords)
                if not is_rectangle_coords(coords, angle_tol):
                    continue
                w, h = rect_side_lengths(coords)
                if not (min_side <= min(w,h) <= max_side and min_side <= max(w,h) <= max_side*10):
                    continue
                rectangles.append((poly, coords, w, h))
            except Exception:
                pass

        # --- kumpulkan TEKS ---
        def text_ok(t):
            if only_pink and getattr(t.dxf, "color", 256) != 6:
                return False
            if layer_text_filter.strip():
                return (t.dxf.layer or "").upper() == layer_text_filter.strip().upper()
            return True

        texts = [t for t in msp.query("TEXT MTEXT") if text_ok(t)]

        # --- pasangkan teks ke kotak terdekat (tanpa lari jauh) ---
        moved = 0
        for t in texts:
            try:
                px, py = t.dxf.insert[0], t.dxf.insert[1]
            except Exception:
                continue
            pt = Point(px, py)

            best_idx = -1
            best_score = 1e9
            contained_idx = -1

            for idx, (poly, coords, w, h) in enumerate(rectangles):
                if poly.contains(pt):
                    contained_idx = idx
                    break
                # jarak dinormalisasi agar tidak lari ke kotak jauh
                d = poly.distance(pt)
                min_side_len = max(min(w, h), 1e-6)
                score = d / min_side_len
                if score < best_score:
                    best_score = score
                    best_idx = idx

            if contained_idx != -1:
                idx = contained_idx
            else:
                # hanya ambil kalau dekat (<= capture_factor)
                if best_score > capture_factor:
                    continue
                idx = best_idx

            poly, coords, w, h = rectangles[idx]
            cx, cy = poly.centroid.x, poly.centroid.y
            angle = rect_orientation(coords)

            # ukuran kotak berdasarkan sisi-sisi (bukan bounding box aksis)
            box_w, box_h = max(w, h), min(w, h)

            # hitung tinggi teks yang pas
            text_str = t.plain_text() if t.dxftype() == "MTEXT" else t.dxf.text
            height_fit = best_text_height(text_str, box_w, box_h, margin=margin_factor)

            # tempatkan + rotasi + align center
            if t.dxftype() == "TEXT":
                # set alignment ke middle_center lalu tempatkan
                t.set_placement((cx, cy), align=TextEntityAlignment.MIDDLE_CENTER)
                t.dxf.height = float(height_fit)
                t.dxf.rotation = float(angle)
            else:  # MTEXT
                t.set_location(insert=(cx, cy), rotation=float(angle))
                t.dxf.attachment_point = MTextAttachmentPoint.MIDDLE_CENTER
                t.dxf.char_height = float(height_fit)

            moved += 1

        # simpan hasil
        out_path = os.path.join(tmpdir, "rapi.dxf")
        doc.saveas(out_path)

        st.success(f"📦 Kotak terdeteksi: {len(rectangles)} | 🔤 Teks diproses: {len(texts)} | ✅ Teks berhasil dirapikan: {moved}")
        with open(out_path, "rb") as f:
            st.download_button("⬇️ Download DXF Rapi", f, file_name="rapi.dxf", mime="application/dxf")
