import streamlit as st
import zipfile
from io import BytesIO
from lxml import etree as ET
import pandas as pd

st.set_page_config(page_title="Urutkan POLE", page_icon="📍", layout="wide")

st.title("📍 Urutkan POLE per LINE dari KMZ")

# Upload file KMZ
uploaded_file = st.file_uploader("Upload file KMZ", type=["kmz"])

def extract_placemarks_from_kml(kml_data):
    """
    Ekstrak semua Placemark dari KML dengan lxml + recover=True
    """
    parser = ET.XMLParser(recover=True, encoding="utf-8")
    root = ET.fromstring(kml_data, parser=parser)
    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    placemarks = root.findall(".//kml:Placemark", ns)
    data = []

    for pm in placemarks:
        # ambil nama POLE
        name = pm.findtext("kml:name", default="(no name)", namespaces=ns)

        # ambil folder induk (LINE)
        parent = pm.getparent()
        line_name = None
        while parent is not None:
            if parent.tag.endswith("Folder"):
                folder_name = parent.findtext("kml:name", default="", namespaces=ns)
                if folder_name:
                    line_name = folder_name
                    break
            parent = parent.getparent()

        # ambil koordinat
        coords = pm.find(".//kml:coordinates", ns)
        if coords is not None and coords.text:
            coords_text = coords.text.strip()
            lon, lat, *_ = coords_text.split(",")
            data.append([line_name if line_name else "UNKNOWN", name, float(lat), float(lon)])

    return data

if uploaded_file is not None:
    try:
        with zipfile.ZipFile(uploaded_file, "r") as kmz:
            # cari doc.kml
            kml_filename = None
            for name in kmz.namelist():
                if name.endswith(".kml"):
                    kml_filename = name
                    break

            if not kml_filename:
                st.error("❌ Tidak ditemukan file .kml di dalam KMZ")
            else:
                # baca isi doc.kml
                kml_data = kmz.read(kml_filename)
                data = extract_placemarks_from_kml(kml_data)

                if not data:
                    st.warning("⚠ Tidak ada Placemark dengan koordinat ditemukan.")
                else:
                    df = pd.DataFrame(data, columns=["LINE", "Nama", "Latitude", "Longitude"])

                    # urutkan per LINE + Nama (atau bisa ubah jadi by Latitude/Longitude)
                    df_sorted = df.sort_values(by=["LINE", "Nama"]).reset_index(drop=True)

                    st.success("✅ Data berhasil dibaca dan diurutkan!")
                    st.dataframe(df_sorted)

                    # download hasil sebagai Excel
                    towrite = BytesIO()
                    df_sorted.to_excel(towrite, index=False, sheet_name="POLE")
                    towrite.seek(0)
                    st.download_button(
                        "⬇️ Download Hasil (Excel)",
                        data=towrite,
                        file_name="urutkan_pole.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

    except Exception as e:
        st.error(f"❌ Error saat memproses KMZ: {e}")
