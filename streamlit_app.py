import streamlit as st
import ezdxf
import tempfile
from collections import Counter

st.set_page_config(page_title="DXF Entity Analyzer", layout="wide")
st.title("🔍 Analisis Struktur DXF")

uploaded_file = st.file_uploader("Upload file DXF", type=["dxf"])

if uploaded_file:
    # Simpan file sementara
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    # Baca DXF
    try:
        doc = ezdxf.readfile(tmp_path)
    except Exception as e:
        st.error(f"Gagal membaca DXF: {e}")
        st.stop()

    msp = doc.modelspace()

    # Ambil semua entity
    entities = list(msp)
    entity_types = [e.dxftype() for e in entities]

    counter = Counter(entity_types)

    st.subheader("📦 Jumlah Entity per Tipe")
    for etype, count in counter.items():
        st.write(f"- **{etype}** : {count}")

    st.success(f"Total entity terdeteksi: {len(entities)}")

    # Contoh preview beberapa entity pertama
    st.subheader("🔎 Contoh Entity Pertama")
    for e in entities[:10]:
        st.json({
            "type": e.dxftype(),
            "layer": e.dxf.layer if hasattr(e.dxf, "layer") else None,
            "color": e.dxf.color if hasattr(e.dxf, "color") else None,
        })
