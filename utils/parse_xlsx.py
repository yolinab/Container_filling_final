import pandas as pd
from typing import List, Tuple, Dict
import re

def print_parsed_pallets(pallets_data):
    """
    Print pallet data in simple CSV-like rows:
    pallet_type,length,width,height,count
    And print total number of individual pallets.
    """
    total = 0

    print("pallet_type,length,width,height,count")  # header

    for p in pallets_data:
        print(f"{p['pallet_type']},{p['length']},{p['width']},{p['height']},{p['count']}")
        total += p["count"]

    print(f"\nTOTAL_PALLETS,{total}")


def _find_col(df, candidates):
    """
    Helper: find the first existing column whose normalized name
    starts with any of the candidate strings.
    """
    norm_cols = {c.lower().strip(): c for c in df.columns}

    for cand in candidates:
        cand = cand.lower().strip()
        for norm_name, orig_name in norm_cols.items():
            if norm_name.startswith(cand):
                return orig_name

    raise KeyError(f"None of the candidate columns {candidates} found in {list(df.columns)}")


def _parse_pallet_size_str(size_str: str) -> Tuple[int, int, int]:
    """
    Parse a pallet size string like '1.15x1.15x1.01', '1.15x1.15x1.01cm',
    or '1,15x1,15x1,01 ' into integer dimensions in centimetres.

    Assumes the numbers are in metres with decimal separators '.' or ','.
    """
    s = str(size_str).strip().lower()

    # Remove units and other trailing text
    s = s.replace("cm", "")

    # Normalise decimal comma to dot
    s = s.replace(",", ".")

    # Split on x / X / ×
    parts = re.split(r"[x×]", s)
    parts = [p.strip() for p in parts if p.strip()]

    if len(parts) != 3:
        raise ValueError(f"Cannot parse pallet size string: '{size_str}'")

    # Convert metres to centimetres and round
    def to_cm(p: str) -> int:
        val = float(p)
        return int(round(val * 100))

    L = to_cm(parts[0])
    W = to_cm(parts[1])
    H = to_cm(parts[2])
    return L, W, H


def parse_pallet_excel(
    excel_path: str,
    sheet_name=0
) -> Tuple[List[int], List[int], List[int], List[Dict]]:
    """
    Parse the pallet Excel file (Edelman order export) and return:

        lengths:  list[int]  (one entry per individual pallet)
        widths:   list[int]
        heights:  list[int]
        pallets_data: list[dict] with metadata per pallet *type* row

    Expected layout (based on current order export):

        Column (e.g. F): "Pallet size"            -> string like "1.15x1.15x1.01"
        Column (e.g. Q): "Total order full pallets" -> how many full pallets of this type are ordered
        Optional: "Productname"/"Item"/"Pallet type" used as human-readable type label.

    Parameters
    ----------
    excel_path : str
        Path to the Excel file.
    sheet_name : str | int, default 0
        Sheet name or index passed to pandas.read_excel.
    """
    # Read the sheet
    df = pd.read_excel(excel_path, sheet_name=sheet_name)

    # Identify columns robustly
    col_pallet_size = _find_col(df, ["Pallet size", "size"])
    col_count       = _find_col(df, ["Total order full pallets", "full pallets", "order full pallets"])
    col_pallet_type = _find_col(df, ["pallet type", "type", "productname", "product name", "item"])

    # Drop rows with empty/NaN pallet size
    df = df.dropna(subset=[col_pallet_size])

    # Drop rows where count is NaN or 0
    df = df.dropna(subset=[col_count])
    df = df[df[col_count] > 0]

    pallets_data: List[Dict] = []

    for _, row in df.iterrows():
        size_str = row[col_pallet_size]
        try:
            length, width, height = _parse_pallet_size_str(size_str)
        except Exception:
            # Skip rows with unparseable size strings
            continue

        count = int(row[col_count])

        pallets_data.append({
            "pallet_size": str(size_str).strip(),
            "length": length,
            "width": width,
            "height": height,
            "pallet_type": str(row[col_pallet_type]),
            "count": count,
        })

    # Expand into one entry per physical pallet
    lengths: List[int] = []
    widths:  List[int] = []
    heights: List[int] = []

    for p in pallets_data:
        n = p["count"]
        lengths.extend([p["length"]] * n)
        widths.extend([p["width"]] * n)
        heights.extend([p["height"]] * n)

    #################################
    print_parsed_pallets(pallets_data)
    #################################

    return lengths, widths, heights, pallets_data


import pandas as pd
from typing import List, Tuple, Dict, Any, Optional
import re


def _find_col_optional(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """
    Return first matching column name, or None if not found.
    Matching is prefix-based on normalised names (lower/strip).
    """
    norm_cols = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        cand = cand.lower().strip()
        for norm_name, orig_name in norm_cols.items():
            if norm_name.startswith(cand):
                return orig_name
    return None


def _find_col_required(df: pd.DataFrame, candidates: List[str]) -> str:
    col = _find_col_optional(df, candidates)
    if col is None:
        raise KeyError(f"None of the candidate columns {candidates} found in {list(df.columns)}")
    return col


def _parse_pallet_size_str(size_str: str) -> Tuple[int, int, int]:
    """
    Parse strings like '1.15x1.15x1.01', '1,15x1,15x1,01', optionally with 'cm'.
    Assumes metres -> converts to cm.
    """
    s = str(size_str).strip().lower()
    s = s.replace("cm", "").replace(",", ".")
    parts = re.split(r"[x×]", s)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) != 3:
        raise ValueError(f"Cannot parse pallet size string: '{size_str}'")

    def to_cm(p: str) -> int:
        return int(round(float(p) * 100))

    L = to_cm(parts[0])
    W = to_cm(parts[1])
    H = to_cm(parts[2])
    return L, W, H


def parse_pallet_excel_v2(
    excel_path: str,
    sheet_name: Any = 0,
    return_per_pallet_meta: bool = True,
) -> Tuple[List[int], List[int], List[int], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    New format for multi-container/subset model:

    Returns:
      lengths, widths, heights: one entry per physical pallet (cm)
      pallets_data: aggregated per type row
      meta_per_pallet: one dict per physical pallet, aligned with lengths/widths/heights
                      so meta_per_pallet[i] describes pallet i.

    If return_per_pallet_meta=False, meta_per_pallet will be [].
    """
    df = pd.read_excel(excel_path, sheet_name=sheet_name)

    # Required columns
    col_pallet_size = _find_col_required(df, ["Pallet size", "size"])
    col_count = _find_col_required(df, ["Total order full pallets", "full pallets", "order full pallets"])

    # Optional columns (best-effort)
    col_productname = _find_col_optional(df, ["Productname", "product name", "product"])
    col_item = _find_col_optional(df, ["Item", "item"])
    col_barcode = _find_col_optional(df, ["Barcode", "bar code", "ean"])
    col_code = _find_col_optional(df, ["Code", "article", "sku"])
    col_pallet_type = _find_col_optional(df, ["pallet type", "type"])  # sometimes exists

    # Clean rows
    df = df.dropna(subset=[col_pallet_size])
    df = df.dropna(subset=[col_count])
    df = df[df[col_count] > 0]

    pallets_data: List[Dict[str, Any]] = []
    meta_per_pallet: List[Dict[str, Any]] = []

    lengths: List[int] = []
    widths: List[int] = []
    heights: List[int] = []

    pallet_global_id = 1  # stable running id across expanded pallets

    for _, row in df.iterrows():
        size_str = row[col_pallet_size]
        try:
            L_cm, W_cm, H_cm = _parse_pallet_size_str(size_str)
        except Exception:
            continue

        count = int(row[col_count])

        # Choose a human-readable label
        label_parts = []
        if col_productname and pd.notna(row[col_productname]):
            label_parts.append(str(row[col_productname]).strip())
        if col_item and pd.notna(row[col_item]):
            label_parts.append(str(row[col_item]).strip())
        if not label_parts and col_pallet_type and pd.notna(row[col_pallet_type]):
            label_parts.append(str(row[col_pallet_type]).strip())

        pallet_label = " | ".join(label_parts) if label_parts else "UNKNOWN"

        # Aggregated row info (type-level)
        type_row: Dict[str, Any] = {
            "pallet_size_raw": str(size_str).strip(),
            "length": L_cm,
            "width": W_cm,
            "height": H_cm,
            "count": count,
            "label": pallet_label,
        }
        # Keep any useful ids if present
        if col_barcode and pd.notna(row[col_barcode]):
            type_row["barcode"] = str(row[col_barcode]).strip()
        if col_code and pd.notna(row[col_code]):
            type_row["code"] = str(row[col_code]).strip()

        pallets_data.append(type_row)

        # Expand to per-physical-pallet entries
        for j in range(count):
            lengths.append(L_cm)
            widths.append(W_cm)
            heights.append(H_cm)

            if return_per_pallet_meta:
                meta: Dict[str, Any] = {
                    "pallet_id": pallet_global_id,     # 1..N expanded
                    "type_index": len(pallets_data)-1, # index into pallets_data
                    "within_type_index": j + 1,        # 1..count
                    "label": pallet_label,
                    "pallet_size_raw": str(size_str).strip(),
                    "length": L_cm,
                    "width": W_cm,
                    "height": H_cm,
                }
                if col_productname and pd.notna(row[col_productname]):
                    meta["productname"] = str(row[col_productname]).strip()
                if col_item and pd.notna(row[col_item]):
                    meta["item"] = str(row[col_item]).strip()
                if col_barcode and pd.notna(row[col_barcode]):
                    meta["barcode"] = str(row[col_barcode]).strip()
                if col_code and pd.notna(row[col_code]):
                    meta["code"] = str(row[col_code]).strip()

                meta_per_pallet.append(meta)

            pallet_global_id += 1

    if not return_per_pallet_meta:
        meta_per_pallet = []

    return lengths, widths, heights, pallets_data, meta_per_pallet


def parse_pallet_excel_v3(
    excel_path: str,
    sheet_name: Any = 0,
    return_per_pallet_meta: bool = True,
) -> Tuple[List[int], List[int], List[int], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    New format for multi-container/subset model:

    Returns:
      lengths, widths, heights: one entry per physical pallet (cm)
      pallets_data: aggregated per type row
      meta_per_pallet: one dict per physical pallet, aligned with lengths/widths/heights
                      so meta_per_pallet[i] describes pallet i.

    If return_per_pallet_meta=False, meta_per_pallet will be [].
    """
    df = pd.read_excel(excel_path, sheet_name=sheet_name)

    # Required columns
    col_pallet_size = _find_col_required(df, ["Pallet size", "size"])
    col_count = _find_col_required(df, ["Total order full pallets", "full pallets", "order full pallets"])

    # Optional columns (best-effort)
    col_productname = _find_col_optional(df, ["Productname", "product name", "product"])
    col_item = _find_col_optional(df, ["Item", "item"])
    col_barcode = _find_col_optional(df, ["Barcode", "bar code", "ean"])
    col_code = _find_col_optional(df, ["Code", "article", "sku"])
    col_pallet_type = _find_col_optional(df, ["pallet type", "type"])  # sometimes exists

    # NEW: Optional weight column (best-effort)
    # Common names in Edelman exports: "External Net weight", sometimes "External net weight"
    col_weight = _find_col_optional(df, [
        "External Net weight", "external net weight",
        "External net weight", "external weight",
        "Net weight", "net weight",
        "Weight", "weight"
    ])

    # Clean rows
    df = df.dropna(subset=[col_pallet_size])
    df = df.dropna(subset=[col_count])
    df = df[df[col_count] > 0]

    pallets_data: List[Dict[str, Any]] = []
    meta_per_pallet: List[Dict[str, Any]] = []

    lengths: List[int] = []
    widths: List[int] = []
    heights: List[int] = []

    pallet_global_id = 1  # stable running id across expanded pallets

    for _, row in df.iterrows():
        size_str = row[col_pallet_size]
        try:
            L_cm, W_cm, H_cm = _parse_pallet_size_str(size_str)
        except Exception:
            continue

        count = int(row[col_count])

        # NEW: parse weight (best-effort)
        weight_kg: Optional[float] = None
        if col_weight and pd.notna(row[col_weight]):
            try:
                # handle strings like "1.234,5" or "1234.5"
                raw = str(row[col_weight]).strip().replace(",", ".")
                weight_kg = float(raw)
            except Exception:
                weight_kg = None

        # Choose a human-readable label
        label_parts = []
        if col_productname and pd.notna(row[col_productname]):
            label_parts.append(str(row[col_productname]).strip())
        if col_item and pd.notna(row[col_item]):
            label_parts.append(str(row[col_item]).strip())
        if not label_parts and col_pallet_type and pd.notna(row[col_pallet_type]):
            label_parts.append(str(row[col_pallet_type]).strip())

        pallet_label = " | ".join(label_parts) if label_parts else "UNKNOWN"

        # Aggregated row info (type-level)
        type_row: Dict[str, Any] = {
            "pallet_size_raw": str(size_str).strip(),
            "length": L_cm,
            "width": W_cm,
            "height": H_cm,
            "count": count,
            "label": pallet_label,
            # NEW
            "weight_kg": weight_kg,
        }
        # Keep any useful ids if present
        if col_barcode and pd.notna(row[col_barcode]):
            type_row["barcode"] = str(row[col_barcode]).strip()
        if col_code and pd.notna(row[col_code]):
            type_row["code"] = str(row[col_code]).strip()

        pallets_data.append(type_row)

        # Expand to per-physical-pallet entries
        for j in range(count):
            lengths.append(L_cm)
            widths.append(W_cm)
            heights.append(H_cm)

            if return_per_pallet_meta:
                meta: Dict[str, Any] = {
                    "pallet_id": pallet_global_id,     # 1..N expanded
                    "type_index": len(pallets_data)-1, # index into pallets_data
                    "within_type_index": j + 1,        # 1..count
                    "label": pallet_label,
                    "pallet_size_raw": str(size_str).strip(),
                    "length": L_cm,
                    "width": W_cm,
                    "height": H_cm,
                    # NEW
                    "weight_kg": weight_kg,
                }
                if col_productname and pd.notna(row[col_productname]):
                    meta["productname"] = str(row[col_productname]).strip()
                if col_item and pd.notna(row[col_item]):
                    meta["item"] = str(row[col_item]).strip()
                if col_barcode and pd.notna(row[col_barcode]):
                    meta["barcode"] = str(row[col_barcode]).strip()
                if col_code and pd.notna(row[col_code]):
                    meta["code"] = str(row[col_code]).strip()

                meta_per_pallet.append(meta)

            pallet_global_id += 1

    if not return_per_pallet_meta:
        meta_per_pallet = []

    return lengths, widths, heights, pallets_data, meta_per_pallet