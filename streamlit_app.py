import streamlit as st
import zipfile
import os
import tempfile
import re
from lxml import etree

# ======= Konfigurasi =======
VALID_PREFIXES = {"kml", "gx", "atom"}  # yang kita pertahankan
NS_URLS = {
    "gx":   "http://www.google.com/kml/ext/2.2",
    "atom": "http://www.w3.org/2005/Atom",
}
KML_DEFAULT_NS = b'http://www.opengis.net/kml/2.2'

# ======= Util regex pada RAW XML (bytes) =======
TAG_PREFIX_RE = re.compile(br'(<\s*/?\s*)([A-Za-z_][\w\.-]*):([A-Za-z_][\w\.-]*)(\b)', re.M)
ATTR_PREFIX_RE = re.compile(br'(\s)([A-Za-z_][\w\.-]*):([A-Za-z_][\w\.-]*)(\s*=)', re.M)
DECLARED_PREFIX_RE = re.compile(br'\bxmlns:([A-Za-z_][\w\.-]*)="[^"]*"', re.M)
DECLARED_DEFAULT_RE = re.compile(br'\bxmlns="[^"]*"', re.M)
USED_PREFIX_IN_TAGS_RE = re.compile(br'</?\s*([A-Za-z_][\w\.-]*):[A-Za-z_][\w\.-]*', re.M)
USED_PREFIX_IN_ATTRS_RE = re.compile(br'\s([A-Za-z_][\w\.-]*):[A-Za-z_][\w\.-]*\s*=', re.M)
OPEN_KML_TAG_RE = re.compile(br'<\s*kml\b[^>]*>', re.M)

def _find_open_kml_tag(raw: bytes):
    m = OPEN_KML_TAG_RE.search(raw)
    return (m.start(), m.end(), m.group(0)) if m else (None, None, None)

def strip_unknown_prefixes_in_markup(raw: bytes, unknown_prefixes: set) -> bytes:
    # Hapus prefix di nama tag
    def _tag_sub(m):
        lead, pfx, local, tail = m.groups()
        if pfx in unknown_prefixes:
            return lead + local + tail
        return m.group(0)
    raw = TAG_PREFIX_RE.sub(_tag_sub, raw)

    # Hapus prefix di nama atribut
    def _attr_sub(m):
        sp, pfx, attr, eq = m.groups()
        if pfx in unknown_prefixes:
            return sp + attr + eq
        return m.group(0)
    raw = ATTR_PREFIX_RE.sub(_attr_sub, raw)
    return raw

def ensure_namespaces_on_root(raw: bytes, need_gx: bool, need_atom: bool) -> bytes:
    s, e, open_tag = _find_open_kml_tag(raw)
    if open_tag is None:
        return raw

    new_open = open_tag

    # Default xmlns
    if not DECLARED_DEFAULT_RE.search(open_tag):
        new_open = new_open[:-1] + b' xmlns="' + KML_DEFAULT_NS + b'">'

    # gx
    if need_gx and b'xmlns:gx=' not in new_open:
        new_open = new_open[:-1] + b' xmlns:gx="' + NS_URLS["gx"].encode() + b'">'

    # atom
    if need_atom and b'xmlns:atom=' not in new_open:
        new_open = new_open[:-1] + b' xmlns:atom="' + NS_URLS["atom"].encode() + b'">'

    if new_open != open_tag:
        raw = raw[:s] + new_open + raw[s+len(open_tag):]
    return raw

def sanitize_raw_xml(raw: bytes) -> bytes:
    # Prefix yang dipakai
    used = set()
    used.update([m.group(1) for m in USED_PREFIX_IN_TAGS_RE.finditer(raw)])
    used.update([m.group(1) for m in USED_PREFIX_IN_ATTRS_RE.finditer(raw)])

    declared = set(DECLARED_PREFIX_RE.findall(raw))

    # Butuh gx/atom?
    need_gx = b'gx' in used
    need_atom = b'atom' in used

    # Unknown prefix = dipakai tapi tidak dideklarasikan dan bukan valid
    unknown = {p for p in used if p not in declared and p.decode() not in VALID_PREFIXES}

    # Rontokkan prefix unknown
    if unknown:
        raw = strip_unknown_prefixes_in_markup(raw, unknown)

    # Pastikan root <kml> punya xmlns default + gx/atom bila perlu
    raw = ensure_namespaces_on_root(raw, need_gx=need_gx, need_atom=need_atom)

    return raw

def postprocess_with_lxml(clean_raw: bytes) -> bytes:
    parser = etree.XMLParser(remove_blank_text=True, recover=True)
    root = etree.fromstring(clean_raw, parser)

    # Tambah namespace via lxml (jaga-jaga)
    if root.tag.endswith("kml") or root.tag.endswith("}kml"):
        if "}" not in root.tag:
            root.set("xmlns", KML_DEFAULT_NS.decode())
        if "xmlns:gx" not in root.attrib:
            root.set("xmlns:gx", NS_URLS["gx"])
        if "xmlns:atom" not in root.attrib:
            root.set("xmlns:atom", NS_URLS["atom"])

    tree = etree.ElementTree(root)
    return etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding="UTF-8")

def process_kmz_bytes(kmz_bytes: bytes, output_kml_path: str, output_kmz_path: str):
    with tempfile.TemporaryDirectory() as extract_dir:
        tmp_kmz = os.path.join(extract_dir, "uploaded.kmz")
        with open(tmp_kmz, "wb") as f:
            f.write(kmz_bytes)

        # Ekstrak KMZ
        with zipfile.ZipFile(tmp_kmz, 'r') as kmz:
            kmz.extractall(extract_dir)

        # Cari file KML utama
        main_kml = None
        for r, _, files in os.walk(extract_dir):
            for fn in files:
                if fn.lower().endswith(".kml"):
                    main_kml = os.path.join(r, fn)
                    break
            if main_kml:
                break
        if not main_kml:
            raise FileNotFoundError("Tidak ada file .kml di dalam KMZ")

        # Bersihkan RAW
        with open(main_kml, "rb") as f:
            raw = f.read()
        clean_raw = sanitize_raw_xml(raw)

        # Pretty print pakai lxml
        final_xml = postprocess_with_lxml(clean_raw)

        # Simpan
        with open(main_kml, "wb") as f:
            f.write(final_xml)
        with open(output_kml_path, "wb") as f:
            f.write(final_xml)

        # Repack jadi KMZ
        with zipfile.ZipFile(output_kmz_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for folder, _, files in os.walk(extract_dir):
                for file in files:
                    fp = os.path.join(folder, file)
                    arcname = os.path.relpath(fp, extract_dir)
                    zf.write(fp, arcname)

# ======= Streamlit UI =======
st.title("🗺️ Pembersih KMZ dari Unbound Prefix")

uploaded = st.file_uploader("Upload file KMZ", type=["kmz"])

if uploaded:
    out_kml = "clean_output.kml"
    out_kmz = "clean_output.kmz"

    if st.button("🚀 Bersihkan"):
        try:
            process_kmz_bytes(uploaded.read(), out_kml, out_kmz)
            st.success("✅ Berhasil! KML dibersihkan dan KMZ sudah aman dari unbound prefix.")

            with open(out_kml, "rb") as f:
                st.download_button("⬇️ Download KML Bersih", f, file_name="clean.kml")

            with open(out_kmz, "rb") as f:
                st.download_button("⬇️ Download KMZ Bersih", f, file_name="clean.kmz")

        except Exception as e:
            st.error(f"Gagal memproses: {e}")
