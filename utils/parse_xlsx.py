# utils/pallet_excel_parser.py

import pandas as pd
from typing import List, Tuple, Dict


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


def parse_pallet_excel(
    excel_path: str,
    sheet_name=0
) -> Tuple[List[int], List[int], List[int], List[Dict]]:
    """
    Parse the pallet Excel file and return:

        lengths:  list[int]  (one entry per individual pallet)
        widths:   list[int]
        heights:  list[int]
        pallets_data: list[dict] with metadata per pallet *type* row

    Expected layout (based on your screenshot):

        Column A: "Pallet size"   (string)
        Column B: "Lenght" (typo) (int)
        Column C: "Width"         (int)
        Column D: "Height"        (int)
        Column E: "Pallet type"   (string)
        Column F: "# pallets"     (int)
        Last row: "Total"         (summary) -> ignored

    Parameters
    ----------
    excel_path : str
        Path to the Excel file.
    sheet_name : str | int, default 0
        Sheet name or index passed to pandas.read_excel.

    Returns
    -------
    lengths, widths, heights : list[int]
        Flattened lists with one entry per pallet (respecting '# pallets').
    pallets_data : list[dict]
        One dict per row/type with keys:
            'pallet_size', 'length', 'width', 'height',
            'pallet_type', 'count'
    """
    # Read the sheet
    df = pd.read_excel(excel_path, sheet_name=sheet_name)

    # --- Identify columns robustly (in case names change slightly) ---
    col_pallet_size = _find_col(df, ["pallet size", "size"])
    col_length      = _find_col(df, ["lenght", "length"])   # handle typo
    col_width       = _find_col(df, ["width"])
    col_height      = _find_col(df, ["height"])
    col_pallet_type = _find_col(df, ["pallet type", "type"])
    col_count       = _find_col(df, ["# pallets", "pallets", "count"])

    # --- Drop 'Total' or empty rows ---
    # Anything where pallet size contains "total" (case-insensitive) will be removed
    mask_total = df[col_pallet_size].astype(str).str.contains("total", case=False, na=False)
    df = df[~mask_total]

    # Also drop rows where count is NaN or 0
    df = df.dropna(subset=[col_count])
    df = df[df[col_count] > 0]

    # --- Build per-type data (one dict per row) ---
    pallets_data = []
    for _, row in df.iterrows():
        pallets_data.append({
            "pallet_size": str(row[col_pallet_size]),
            "length": int(row[col_length]),
            "width": int(row[col_width]),
            "height": int(row[col_height]),
            "pallet_type": str(row[col_pallet_type]),
            "count": int(row[col_count])
        })

    # --- Expand into one entry per physical pallet ---
    lengths: List[int] = []
    widths:  List[int] = []
    heights: List[int] = []

    for p in pallets_data:
        n = p["count"]
        lengths.extend([p["length"]] * n)
        widths.extend([p["width"]] * n)
        heights.extend([p["height"]] * n)

    return lengths, widths, heights, pallets_data


def write_parsed_pallets_to_csv(
    lengths: List[int],
    widths: List[int],
    heights: List[int],
    csv_path: str = "test_output_of_parse.csv"
) -> None:
    """
    Given the flat parsed lists (one entry per pallet), write them to a CSV.

    Columns:
        pallet_index, length, width, height
    """
    data = {
        "pallet_index": list(range(len(lengths))),
        "length": lengths,
        "width": widths,
        "height": heights,
    }
    df = pd.DataFrame(data)
    df.to_csv(csv_path, index=False)
    print(f"Parsed pallet list written to CSV: {csv_path}")


def parse_pallet_excel_and_dump_csv(
    excel_path: str,
    csv_path: str = "test_output_of_parse.csv",
    sheet_name=0
) -> Tuple[List[int], List[int], List[int], List[Dict]]:
    """
    Convenience function:
      - parse the Excel file
      - write a CSV snapshot of the flattened pallets
      - return the parsed data
    """
    lengths, widths, heights, pallets_data = parse_pallet_excel(excel_path, sheet_name=sheet_name)
    write_parsed_pallets_to_csv(lengths, widths, heights, csv_path)
    return lengths, widths, heights, pallets_data


# Simple manual test
if __name__ == "__main__":
    excel_path = "sample_instances/input_pallets.xlsx" 
    csv_path   = "test_output_of_parse.csv"

    lengths, widths, heights, pallets_data = parse_pallet_excel_and_dump_csv(
        excel_path,
        csv_path=csv_path
    )

    print(f"Parsed {len(pallets_data)} pallet types")
    print(f"Total individual pallets: {len(lengths)}")
    print("(length, width, height):")
    for i in range(len(lengths)):
        print(lengths[i], widths[i], heights[i])