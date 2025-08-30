import zipfile
import os
import shutil
import xml.etree.ElementTree as ET
from shapely.geometry import Point, Polygon

# ==== STEP 1: Extract KMZ ====
kmz_file = "PKB001962 NEW.kmz"
extract_dir = "kmz_extract"

with zipfile.ZipFile(kmz_file, 'r') as z:
    z.extractall(extract_dir)

kml_file = os.path.join(extract_dir, "doc.kml")

# ==== STEP 2: Parse KML ====
tree = ET.parse(kml_file)
root = tree.getroot()

ns = {"kml": "http://www.opengis.net/kml/2.2"}

def get_coordinates(coord_text):
    coords = []
    for c in coord_text.strip().split():
        lon, lat, *_ = map(float, c.split(","))
        coords.append((lon, lat))
    return coords

# ==== STEP 3: Kumpulkan boundary polygons ====
boundaries = {}  # { "A01": Polygon(...) }
for placemark in root.findall(".//kml:Placemark", ns):
    name = placemark.find("kml:name", ns)
    polygon = placemark.find(".//kml:Polygon", ns)
    if name is not None and polygon is not None:
        coords_text = polygon.find(".//kml:coordinates", ns).text
        coords = get_coordinates(coords_text)
        boundaries[name.text] = Polygon(coords)

# ==== STEP 4: Kumpulkan placemark HP ====
hp_points = []
for placemark in root.findall(".//kml:Placemark", ns):
    name = placemark.find("kml:name", ns)
    point = placemark.find(".//kml:Point", ns)
    if name is not None and "HP" in name.text and point is not None:
        coords_text = point.find("kml:coordinates", ns).text.strip()
        lon, lat, *_ = map(float, coords_text.split(","))
        hp_points.append((name.text, Point(lon, lat), placemark))

# ==== STEP 5: Cek boundary mana yang cocok ====
assignments = {}
for name, point, placemark in hp_points:
    for bname, poly in boundaries.items():
        if poly.contains(point):
            assignments.setdefault(bname, []).append(placemark)
            break

# ==== STEP 6: Buat struktur folder baru ====
document = ET.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
doc_el = ET.SubElement(document, "Document")

for bname, placemarks in assignments.items():
    folder = ET.SubElement(doc_el, "Folder")
    ET.SubElement(folder, "name").text = bname
    for pm in placemarks:
        folder.append(pm)

# ==== STEP 7: Simpan hasil ====
new_kml = "output.kml"
ET.ElementTree(document).write(new_kml, encoding="utf-8", xml_declaration=True)

# Buat KMZ lagi
output_kmz = "output.kmz"
with zipfile.ZipFile(output_kmz, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(new_kml, "doc.kml")

print("Selesai! File hasil: ", output_kmz)
