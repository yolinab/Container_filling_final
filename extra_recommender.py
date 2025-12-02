# extra_recommender.py

import pandas as pd
import subprocess
from pathlib import Path

EXCEL_PATH = "/Users/yolina/Desktop/Container-filling_v1/Input_pallets.xlsx"
EXTRA_MODEL = "/Users/yolina/Desktop/Container-filling_v1/extra_select.mzn"
OUTPUT_DZN = Path("/Users/yolina/Desktop/Container-filling_v1/extra_instance.dzn")


def run_minizinc(model, data_path):
    """Run MiniZinc and return stdout."""
    result = subprocess.run(
        ["minizinc", "--solver", "chuffed", model, data_path],
        text=True,
        capture_output=True,
        check=True
    )
    return result.stdout


def parse_add_vector(output):
    """Parses: add = [2, 1, 0]"""
    for line in output.splitlines():
        if line.startswith("add"):
            inside = line.split("[")[1].split("]")[0]
            nums = [int(x.strip()) for x in inside.split(",") if x.strip()]
            return nums
    return None


def run_extra_recommender(free_len):
    """
    Reads Excel → pallet types → runs extra_select.mzn → writes new DZN.
    """

    df = pd.read_excel(EXCEL_PATH)


    # df = df.fillna(0)
    # df = df[df["# pallets"] > 0]

    df = df.dropna(subset=["Lenght", "Width", "Height"])   # remove blank rows
    df = df[df["# pallets"] > 0]                              # must be chosen at least once
    df = df[(df["Lenght"] > 0) & (df["Width"] > 0) & (df["Height"] > 0)]  


    if df.empty:
        print("No pallet types available → nothing to recommend.")
        return None

    # Build arrays for MiniZinc
    len_arr = df["Lenght"].astype(int).tolist()
    wid_arr = df["Width"].astype(int).tolist()
    hgt_arr = df["Height"].astype(int).tolist()
    max_add = [20] * len(len_arr)   # cap to avoid insane numbers

    T = len(len_arr)
    BUF = 5  # same as main model

    # Write data file for extra_select.mzn
    extra_dzn_path = Path("extra_instance.dzn")
    with extra_dzn_path.open("w") as f:
        f.write(f"T = {T};\n")
        f.write(f"len = {len_arr};\n")
        f.write(f"wid = {wid_arr};\n")
        f.write(f"hgt = {hgt_arr};\n")
        f.write(f"BUF = {BUF};\n")
        f.write(f"free_len = {int(free_len)};\n")
        f.write(f"max_add = {max_add};\n")

    print(f"Extra instance written: {extra_dzn_path}")

    # Run MiniZinc
    out = run_minizinc(EXTRA_MODEL, extra_dzn_path)
    print("MiniZinc recommendation:\n", out)

    add_vector = parse_add_vector(out)

    if add_vector is None:
        print("MiniZinc returned no add[] vector.")
        return None

    # Build the new merged DZN
    # Original + extra amounts
    merged_sizes = []
    df_original = df.copy()
    df_original["add"] = add_vector

    for _, row in df_original.iterrows():
        count_total = int(row["# pallets"] + row["add"])
        for _ in range(count_total):
            merged_sizes.append((int(row["Lenght"]), int(row["Width"]), int(row["Height"])))

    # Write new DZN including extras
    with OUTPUT_DZN.open("w") as f:

        # container + buffer parameters your model needs
        f.write(f"N = {len(merged_sizes)};\n")
        f.write(f"W = {235};\n")
        f.write(f"L = {1203};\n")
        f.write(f"H = {270};\n")
        f.write(f"BUF = {BUF};\n")

        f.write("len = [")
        f.write(",".join(str(L) for (L, W, H) in merged_sizes))
        f.write("];\n")

        f.write("wid = [")
        f.write(",".join(str(W) for (L, W, H) in merged_sizes))
        f.write("];\n")

        f.write("hgt = [")
        f.write(",".join(str(H) for (L, W, H) in merged_sizes))
        f.write("];\n")

    print(f"Extended DZN written: {OUTPUT_DZN}")
    return OUTPUT_DZN