
from __future__ import annotations

import io
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Almacén 360",
    page_icon="📦",
    layout="wide",
)

BASE = Path(__file__).resolve().parent

# -----------------------------
# Utilidades
# -----------------------------
def norm_text(value):
    s = unicodedata.normalize("NFKD", str(value).strip().lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s).strip()

ALIASES = {
    "sku": ["sku", "codigo sku", "código sku", "codigo producto", "producto", "articulo", "artículo", "referencia"],
    "ubicacion": ["ubicacion", "ubicación", "direccion", "dirección", "locacion", "locación", "location", "slot", "posicion", "posición"],
    "movimientos": ["movimientos", "movimiento", "cantidad movimientos", "cantidad", "frecuencia", "picks", "picking", "total movimientos"],
    "ciclo": ["ciclo", "cycle", "periodo", "período", "escenario", "fecha ciclo"],
}

COLORS = {
    "Sin movimientos": "#64748b",
    "Bajo": "#22c55e",
    "Medio": "#eab308",
    "Alto": "#f97316",
    "Muy alto": "#ef4444",
}

def read_excel_bytes(data: bytes):
    return pd.read_excel(io.BytesIO(data), sheet_name=None, header=None, dtype=object, engine="openpyxl")

def detect_header(raw: pd.DataFrame) -> int:
    for i in range(min(20, len(raw))):
        vals = [norm_text(x) for x in raw.iloc[i].tolist()]
        hits = 0
        for aliases in ALIASES.values():
            if any(norm_text(a) in vals for a in aliases):
                hits += 1
        if hits >= 2:
            return i
    return 0

def movement_table(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    h = detect_header(raw)
    headers = []
    for i, x in enumerate(raw.iloc[h].tolist()):
        if pd.isna(x) or str(x).strip() == "":
            headers.append(f"Columna_{i+1}")
        else:
            headers.append(str(x).strip())
    df = raw.iloc[h+1:].copy()
    df.columns = headers
    return df.dropna(how="all").reset_index(drop=True)

def guess_columns(df: pd.DataFrame):
    result = {}
    for key, aliases in ALIASES.items():
        found = None
        for col in df.columns:
            if norm_text(col) in {norm_text(a) for a in aliases}:
                found = col
                break
        result[key] = found
    return result

def clean_movements(df: pd.DataFrame, mapping: dict):
    needed = ["sku", "ubicacion", "movimientos"]
    if any(mapping.get(k) is None for k in needed):
        return pd.DataFrame(), pd.DataFrame()

    cols = {mapping[k]: k for k in needed}
    if mapping.get("ciclo") is not None:
        cols[mapping["ciclo"]] = "ciclo"

    out = df[list(cols.keys())].rename(columns=cols).copy()
    if "ciclo" not in out.columns:
        out["ciclo"] = "Ciclo 1"

    out["sku"] = out["sku"].fillna("").astype(str).str.strip()
    out["ubicacion"] = out["ubicacion"].fillna("").astype(str).str.strip().str.upper()
    out["ciclo"] = out["ciclo"].fillna("Ciclo 1").astype(str).str.strip()
    out["movimientos"] = pd.to_numeric(
        out["movimientos"].astype(str).str.replace(",", ".", regex=False),
        errors="coerce",
    )

    bad = out[
        (out["sku"] == "")
        | (out["ubicacion"] == "")
        | out["movimientos"].isna()
        | (out["movimientos"] < 0)
    ].copy()

    good = out.drop(index=bad.index).reset_index(drop=True)
    return good, bad.reset_index(drop=True)

def build_layout(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    def looks_like_location(v):
        s = str(v).strip().upper()
        return bool(re.fullmatch(r"[A-Z]{1,4}[-_ ]?\d{1,5}[A-Z0-9_-]*", s))

    best_start = 0
    for r in range(min(30, len(raw))):
        hits = sum(looks_like_location(v) for v in raw.iloc[r].tolist() if pd.notna(v))
        if hits >= 2:
            best_start = r
            break

    grid = raw.iloc[best_start:].copy().reset_index(drop=True)
    grid = grid.dropna(axis=1, how="all").fillna("")
    grid.columns = [f"C{i+1}" for i in range(grid.shape[1])]
    return grid

def extract_locations(grid: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in range(len(grid)):
        for c in range(grid.shape[1]):
            s = str(grid.iat[r, c]).strip().upper()
            if not s or s == "NAN":
                continue
            if re.fullmatch(r"[A-Z]{1,4}[-_ ]?\d{1,5}[A-Z0-9_-]*", s):
                rows.append((s, r, c))
    return pd.DataFrame(rows, columns=["ubicacion", "fila", "columna"])

def classify(x, q1, q2, q3):
    if x <= 0:
        return "Sin movimientos"
    if x <= q1:
        return "Bajo"
    if x <= q2:
        return "Medio"
    if x <= q3:
        return "Alto"
    return "Muy alto"

def file_or_none(name):
    p = BASE / name
    return p.read_bytes() if p.exists() else None

# -----------------------------
# Tema
# -----------------------------
with st.sidebar:
    st.markdown("## 🎨 Apariencia")
    theme = st.radio("Tema", ["Oscuro", "Claro"], horizontal=True)

if theme == "Oscuro":
    bg = "#0b1220"
    panel = "#111827"
    text = "#e5e7eb"
    title = "#f8fafc"
    border = "#334155"
    other = "#1e293b"
    aisle = "#334155"
else:
    bg = "#f8fafc"
    panel = "#ffffff"
    text = "#1f2937"
    title = "#0f172a"
    border = "#cbd5e1"
    other = "#e2e8f0"
    aisle = "#cbd5e1"

st.markdown(
    f"""
    <style>
    :root {{
        --app-bg: {bg};
        --panel-bg: {panel};
        --app-text: {text};
        --app-border: {border};
        --app-muted: {"#94a3b8" if theme == "Oscuro" else "#64748b"};
        --upload-bg: {"#111827" if theme == "Oscuro" else "#ffffff"};
        --upload-btn-bg: {"#1f2937" if theme == "Oscuro" else "#f8fafc"};
        --upload-text: {"#f8fafc" if theme == "Oscuro" else "#111827"};
        --upload-muted: {"#cbd5e1" if theme == "Oscuro" else "#475569"};
    }}

    .stApp {{
        background-color: var(--app-bg) !important;
        color: var(--app-text) !important;
    }}

    [data-testid="stSidebar"] {{
        background-color: var(--panel-bg) !important;
    }}

    [data-testid="stMetric"] {{
        background: var(--panel-bg) !important;
        border: 1px solid var(--app-border) !important;
        border-radius: 12px !important;
        padding: 10px !important;
    }}

    /* ===== FILE UPLOADER =====
       Streamlit has changed the internal DOM several times.
       These selectors intentionally cover both old and new versions.
    */
    div[data-testid="stFileUploader"] {{
        color: var(--upload-text) !important;
    }}

    div[data-testid="stFileUploader"] section,
    section[data-testid="stFileUploaderDropzone"],
    div[data-testid="stFileUploaderDropzone"] {{
        background: var(--upload-bg) !important;
        background-color: var(--upload-bg) !important;
        border: 1px solid var(--app-border) !important;
        border-radius: 10px !important;
        color: var(--upload-text) !important;
    }}

    div[data-testid="stFileUploader"] section > div,
    div[data-testid="stFileUploader"] section div,
    section[data-testid="stFileUploaderDropzone"] > div,
    section[data-testid="stFileUploaderDropzone"] div,
    div[data-testid="stFileUploaderDropzone"] > div,
    div[data-testid="stFileUploaderDropzone"] div {{
        background: transparent !important;
        background-color: transparent !important;
        color: var(--upload-text) !important;
    }}

    div[data-testid="stFileUploader"] p,
    div[data-testid="stFileUploader"] span,
    div[data-testid="stFileUploader"] small,
    div[data-testid="stFileUploader"] label,
    section[data-testid="stFileUploaderDropzone"] p,
    section[data-testid="stFileUploaderDropzone"] span,
    section[data-testid="stFileUploaderDropzone"] small,
    div[data-testid="stFileUploaderDropzone"] p,
    div[data-testid="stFileUploaderDropzone"] span,
    div[data-testid="stFileUploaderDropzone"] small {{
        color: var(--upload-muted) !important;
    }}

    div[data-testid="stFileUploader"] button,
    section[data-testid="stFileUploaderDropzone"] button,
    div[data-testid="stFileUploaderDropzone"] button {{
        background: var(--upload-btn-bg) !important;
        background-color: var(--upload-btn-bg) !important;
        color: var(--upload-text) !important;
        border: 1px solid var(--app-border) !important;
        box-shadow: none !important;
        opacity: 1 !important;
    }}

    div[data-testid="stFileUploader"] button *,
    section[data-testid="stFileUploaderDropzone"] button *,
    div[data-testid="stFileUploaderDropzone"] button * {{
        color: var(--upload-text) !important;
    }}

    div[data-testid="stFileUploader"] svg,
    section[data-testid="stFileUploaderDropzone"] svg,
    div[data-testid="stFileUploaderDropzone"] svg {{
        color: var(--upload-text) !important;
        fill: currentColor !important;
        stroke: currentColor !important;
        opacity: .9 !important;
    }}

    /* Selects / inputs */
    [data-baseweb="select"] > div {{
        background-color: var(--panel-bg) !important;
        color: var(--app-text) !important;
        border-color: var(--app-border) !important;
    }}

    [data-baseweb="input"] {{
        background-color: var(--panel-bg) !important;
        color: var(--app-text) !important;
    }}

    h1,h2,h3,h4,p,span,label {{
        color: var(--app-text);
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📦 Almacén 360")
st.caption("Mapa de calor · Ciclos · Clasificación ABC · Validación de datos · Recomendaciones logísticas")

# -----------------------------
# Archivos
# -----------------------------
with st.sidebar:
    st.markdown("## 1 · Archivos")
    layout_file = st.file_uploader("Layout del almacén", type=["xlsx", "xlsm"])
    movement_file = st.file_uploader("SKUs y movimientos", type=["xlsx", "xlsm"])
    st.caption("Podés cargar nuevos archivos cuando quieras.")

default_layout = file_or_none("layout_profesor.xlsx")
default_mov = file_or_none("movimientos_profesor.xlsx")

layout_bytes = layout_file.getvalue() if layout_file else default_layout
mov_bytes = movement_file.getvalue() if movement_file else default_mov

if layout_bytes is None or mov_bytes is None:
    st.info(
        "Para comenzar, cargá los dos Excel desde la barra lateral. "
        "Si querés que aparezcan datos de ejemplo automáticamente, dejá en GitHub "
        "`layout_profesor.xlsx` y `movimientos_profesor.xlsx` junto a `app.py`."
    )
    st.stop()

try:
    layout_sheets = read_excel_bytes(layout_bytes)
    movement_sheets = read_excel_bytes(mov_bytes)
except Exception as e:
    st.error(f"No se pudieron leer los Excel: {e}")
    st.stop()

with st.sidebar:
    layout_sheet = st.selectbox("Hoja del layout", list(layout_sheets.keys()))
    movement_sheet = st.selectbox("Hoja de movimientos", list(movement_sheets.keys()))

grid = build_layout(layout_sheets[layout_sheet])
raw_mov = movement_table(movement_sheets[movement_sheet])

if grid.empty:
    st.error("No pude interpretar la hoja de layout seleccionada.")
    st.stop()
if raw_mov.empty:
    st.error("No pude interpretar la hoja de movimientos seleccionada.")
    st.stop()

guessed = guess_columns(raw_mov)

with st.sidebar:
    st.markdown("## 2 · Columnas")
    st.caption("Si un Excel nuevo usa otros nombres, elegí manualmente qué significa cada columna.")
    options = list(raw_mov.columns)

    mapping = {}
    for key in ["sku", "ubicacion", "movimientos", "ciclo"]:
        choices = ["(ninguna)"] + options
        default = guessed.get(key)
        index = choices.index(default) if default in choices else 0
        selected = st.selectbox(key.capitalize(), choices, index=index, key=f"map_{key}")
        mapping[key] = None if selected == "(ninguna)" else selected

mov, bad = clean_movements(raw_mov, mapping)

if mov.empty:
    st.warning("No hay movimientos válidos con las columnas seleccionadas.")
    st.stop()

locations = extract_locations(grid)
if locations.empty:
    st.error("No encontré códigos de ubicación dentro del layout.")
    st.stop()

# -----------------------------
# Edición y filtros
# -----------------------------
with st.expander("✏️ Editar movimientos antes de analizar", expanded=False):
    st.caption("Podés cambiar valores o agregar filas. Así probás nuevos ciclos sin modificar el código.")
    edited = st.data_editor(mov, num_rows="dynamic", use_container_width=True, hide_index=True)
    mov = edited.copy()
    mov["movimientos"] = pd.to_numeric(mov["movimientos"], errors="coerce").fillna(0)

cycle_values = sorted(mov["ciclo"].astype(str).unique())

with st.sidebar:
    st.markdown("## 3 · Filtros")
    selected_cycles = st.multiselect("Ciclos", cycle_values, default=cycle_values)
    sku_values = sorted(mov["sku"].astype(str).unique())
    selected_skus = st.multiselect("SKUs", sku_values, default=[])

if not selected_cycles:
    st.info("Seleccioná al menos un ciclo.")
    st.stop()

filtered = mov[mov["ciclo"].astype(str).isin(selected_cycles)].copy()
if selected_skus:
    filtered = filtered[filtered["sku"].astype(str).isin(selected_skus)]

activity = filtered.groupby("ubicacion", as_index=False)["movimientos"].sum()
master = locations.merge(activity, on="ubicacion", how="left")
master["movimientos"] = master["movimientos"].fillna(0)

unmatched = filtered[~filtered["ubicacion"].isin(locations["ubicacion"])].copy()

positive = master.loc[master["movimientos"] > 0, "movimientos"]
if len(positive):
    q1, q2, q3 = [float(positive.quantile(q)) for q in [0.25, 0.50, 0.75]]
else:
    q1 = q2 = q3 = 0.0

master["nivel"] = master["movimientos"].apply(lambda x: classify(float(x), q1, q2, q3))

# -----------------------------
# Indicadores
# -----------------------------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Movimientos", f"{filtered['movimientos'].sum():,.0f}")
c2.metric("Ubicaciones", f"{len(locations):,}")
c3.metric("Ubicaciones activas", f"{(master['movimientos'] > 0).sum():,}")
c4.metric("SKUs", f"{filtered['sku'].nunique():,}")
c5.metric("Sin coincidencia", f"{unmatched['ubicacion'].nunique():,}")

# -----------------------------
# Mapa de calor
# -----------------------------
st.subheader("🔥 Mapa de calor del almacén")
st.caption("Los colores se recalculan según los movimientos del ciclo o filtro elegido.")

legend_cols = st.columns(5)
for col, (name, color) in zip(legend_cols, COLORS.items()):
    col.markdown(f"<span style='color:{color};font-size:22px'>●</span> **{name}**", unsafe_allow_html=True)

lookup = master.drop_duplicates("ubicacion").set_index("ubicacion")
fig = go.Figure()

for r in range(len(grid)):
    for c in range(grid.shape[1]):
        cell = str(grid.iat[r, c]).strip().upper()
        if not cell or cell == "NAN":
            continue

        if cell in lookup.index:
            rec = lookup.loc[cell]
            color = COLORS[rec["nivel"]]
            hover = (
                f"<b>{cell}</b><br>"
                f"Movimientos: {rec['movimientos']:,.0f}<br>"
                f"Nivel: {rec['nivel']}<extra></extra>"
            )
            label = cell
        else:
            color = aisle if ("PASILLO" in cell or "AISLE" in cell) else other
            hover = f"{cell}<extra></extra>"
            label = "·" if ("PASILLO" in cell or "AISLE" in cell) else cell

        fig.add_trace(
            go.Scatter(
                x=[c],
                y=[r],
                mode="markers+text",
                marker=dict(
                    symbol="square",
                    size=32,
                    color=color,
                    line=dict(color=border, width=1),
                ),
                text=[label],
                textfont=dict(size=9, color=text),
                hovertemplate=hover,
                showlegend=False,
            )
        )

fig.update_layout(
    height=max(420, min(950, 48 * len(grid) + 100)),
    margin=dict(l=10, r=10, t=10, b=10),
    paper_bgcolor=bg,
    plot_bgcolor=bg,
    font=dict(color=text),
    dragmode=False,
    xaxis=dict(
        visible=False,
        range=[-0.8, grid.shape[1] - 0.2],
        fixedrange=True,
    ),
    yaxis=dict(
        visible=False,
        range=[len(grid) - 0.2, -0.8],
        fixedrange=True,
    ),
)

# En la app el mapa queda completamente fijo:
# sin barra de herramientas, sin zoom, sin paneo y sin autoscale.
# El hover sigue mostrando información.
plot_config = {
    "scrollZoom": False,
    "doubleClick": False,
    "displaylogo": False,
    "displayModeBar": False,
    "responsive": True,
    "staticPlot": False,
}

# En Streamlit reciente, un clic sobre una celda puede seleccionar el punto.
# Si la versión no devuelve una selección, el hover sigue funcionando igualmente.
try:
    map_event = st.plotly_chart(
        fig,
        use_container_width=True,
        config=plot_config,
        on_select="rerun",
        selection_mode="points",
        key="mapa_calor_principal",
    )
except TypeError:
    map_event = None
    st.plotly_chart(
        fig,
        use_container_width=True,
        config=plot_config,
        key="mapa_calor_principal_fallback",
    )

# Mostrar información del punto seleccionado sin mover el mapa.
clicked_location = None
try:
    pts = map_event.selection.points if map_event is not None else []
    if pts:
        # Cada trace corresponde a una celda del layout y contiene el texto de ubicación.
        point = pts[0]
        curve = point.get("curve_number", point.get("curveNumber"))
        if curve is not None and 0 <= int(curve) < len(fig.data):
            candidate = fig.data[int(curve)].text[0]
            if candidate and candidate != "·":
                candidate = str(candidate).strip().upper()
                if candidate in set(master["ubicacion"]):
                    clicked_location = candidate
except Exception:
    clicked_location = None

if clicked_location:
    click_row = master[master["ubicacion"] == clicked_location].iloc[0]
    click_skus = (
        filtered[filtered["ubicacion"] == clicked_location]
        .groupby("sku", as_index=False)["movimientos"]
        .sum()
        .sort_values("movimientos", ascending=False)
    )
    with st.container(border=True):
        st.markdown(f"### 📍 {clicked_location}")
        c_a, c_b, c_c = st.columns(3)
        c_a.metric("Movimientos", f"{click_row['movimientos']:,.0f}")
        c_b.metric("Nivel", str(click_row["nivel"]))
        c_c.metric("SKUs", f"{len(click_skus)}")
        if len(click_skus):
            st.dataframe(click_skus, use_container_width=True, hide_index=True)


# Descarga opcional: fuera de la app el usuario sí puede abrir el mapa
# y usar las herramientas de zoom si lo necesita.
download_fig = go.Figure(fig)
download_fig.update_layout(dragmode="zoom")
download_fig.update_xaxes(fixedrange=False)
download_fig.update_yaxes(fixedrange=False)
html_map = download_fig.to_html(
    full_html=True,
    include_plotlyjs="cdn",
    config={
        "scrollZoom": True,
        "displaylogo": False,
        "responsive": True,
    },
)
st.download_button(
    "⬇️ Descargar mapa interactivo (HTML)",
    data=html_map.encode("utf-8"),
    file_name="mapa_calor_almacen.html",
    mime="text/html",
    help="Abre este archivo en el navegador para hacer zoom sin modificar la vista de la aplicación.",
)

# -----------------------------
# Consulta ubicación
# -----------------------------
st.subheader("🔎 Consulta por ubicación")
loc_options = sorted(master["ubicacion"].unique())
selected_loc = st.selectbox("Ubicación", loc_options)
loc_info = master[master["ubicacion"] == selected_loc].iloc[0]
st.info(
    f"**{selected_loc}** · {loc_info['movimientos']:,.0f} movimientos · "
    f"Nivel: **{loc_info['nivel']}**"
)
loc_skus = (
    filtered[filtered["ubicacion"] == selected_loc]
    .groupby("sku", as_index=False)["movimientos"]
    .sum()
    .sort_values("movimientos", ascending=False)
)
st.dataframe(loc_skus, use_container_width=True, hide_index=True)

# -----------------------------
# Tabs
# -----------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["📈 Ciclos", "📦 ABC", "✅ Validación", "⬇️ Exportar"]
)

with tab1:
    cycle_summary = (
        mov.groupby("ciclo", as_index=False)
        .agg(
            movimientos=("movimientos", "sum"),
            skus=("sku", "nunique"),
            ubicaciones=("ubicacion", "nunique"),
        )
    )
    st.dataframe(cycle_summary, use_container_width=True, hide_index=True)
    if len(cycle_summary) > 1:
        st.bar_chart(cycle_summary.set_index("ciclo")["movimientos"])
    else:
        st.caption("Agregá otro valor en la columna Ciclo para comparar escenarios.")

with tab2:
    sku_summary = (
        filtered.groupby("sku", as_index=False)["movimientos"]
        .sum()
        .sort_values("movimientos", ascending=False)
    )
    total = sku_summary["movimientos"].sum()
    if total > 0:
        sku_summary["%"] = 100 * sku_summary["movimientos"] / total
        sku_summary["% acumulado"] = sku_summary["%"].cumsum()
        sku_summary["ABC"] = np.where(
            sku_summary["% acumulado"] <= 80,
            "A",
            np.where(sku_summary["% acumulado"] <= 95, "B", "C"),
        )
        if len(sku_summary):
            sku_summary.loc[sku_summary.index[0], "ABC"] = "A"
    else:
        sku_summary["%"] = 0
        sku_summary["% acumulado"] = 0
        sku_summary["ABC"] = "C"

    st.dataframe(sku_summary, use_container_width=True, hide_index=True)

    st.markdown("#### Recomendación logística")
    st.write(
        "Los SKUs **A** son los de mayor participación en los movimientos del período. "
        "Conviene revisar si están en posiciones de fácil acceso y cercanas a las zonas de picking. "
        "La app no afirma una reubicación óptima porque para eso también se necesitan datos de "
        "capacidad, peso, compatibilidad, ocupación y recorridos reales."
    )

with tab3:
    st.write(f"Filas válidas: **{len(mov)}**")
    st.write(f"Filas descartadas: **{len(bad)}**")
    st.write(f"Ubicaciones de movimientos que no aparecen en el layout: **{unmatched['ubicacion'].nunique()}**")

    if len(unmatched):
        st.markdown("#### Movimientos sin ubicación coincidente")
        st.dataframe(unmatched, use_container_width=True, hide_index=True)

    if len(bad):
        st.markdown("#### Filas descartadas")
        st.dataframe(bad, use_container_width=True, hide_index=True)

with tab4:
    export = master[["ubicacion", "fila", "columna", "movimientos", "nivel"]].copy()
    csv = export.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Descargar análisis CSV",
        data=csv,
        file_name="mapa_calor_resultado.csv",
        mime="text/csv",
    )

st.caption(
    "Almacén 360 · Herramienta de apoyo al análisis logístico. "
    "Las recomendaciones deben validarse con criterio operativo."
)
