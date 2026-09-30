
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
