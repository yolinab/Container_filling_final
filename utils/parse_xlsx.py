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