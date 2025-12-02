# tests/test_box_placement.py

import time

from models.A_box_placement_model import BoxPlacementModel
from utils.parse_xlsx import parse_pallet_excel, parse_pallet_excel_and_dump_csv


def run_box_placement_test():
    """Single test scenario for the BoxPlacementModel."""

    excel_path = "sample_instances/input_pallets.xlsx"  # adjust path

    lengths, widths, heights, pallets_data = parse_pallet_excel(excel_path)

    print(f"Parsed {len(pallets_data)} pallet types")
    print(f"Total individual pallets: {len(lengths)}")

    # container + buffer (hardcoded for now)
    W, L, H = 240, 120, 260
    BUF = 5

    print(f"Container: W={W}, L={L}, H={H}, BUF={BUF}")
    print("Creating model...")
    model = BoxPlacementModel(lengths, widths, heights, W, L, H, BUF)

    print("Lengths:", lengths)
    print("Widths:", widths)
    print("Heights:", heights)
    print("W,L,H,BUF =", W, L, H, BUF)

    print("Solving model...")
    start = time.perf_counter()
    solved = model.solve(solver = "ortools", time_limit=60)
    end = time.perf_counter()

    if solved:
        print("\nModel solved successfully!")
        obj = 1000 * model.max_used_height.value() \
              + model.max_y_extent.value() \
              + model.max_x_extent.value()
        print(f"Objective = {obj}")
        print(f"max_used_height = {model.max_used_height.value()}")
        print(f"max_x_extent    = {model.max_x_extent.value()}")
        print(f"max_y_extent    = {model.max_y_extent.value()}")

        print("\nFirst few boxes (idx, x, y, z, eff_len, eff_wid, h):")
        for p in range(min(10, model.num_boxes)):
            print(
                p,
                model.x[p].value(),
                model.y[p].value(),
                model.z[p].value(),
                model.eff_len[p].value(),
                model.eff_wid[p].value(),
                model.heights[p],
            )
    else:
        print("\nNo solution found.")

    print(f"Solving time: {end - start:.3f} seconds")

def print_model_solution(model):
    """
    Pretty-print all decision variable values from a solved BoxPlacementModel.
    """

    # If no solution: bail out early
    if model.max_used_height.value() is None:
        print("No solution values available (variables have no .value()).")
        return

    print("\n================= SOLUTION SUMMARY =================")

    obj = (
        1000 * model.max_used_height.value()
        + model.max_y_extent.value()
        + model.max_x_extent.value()
    )
    print(f"Objective value: {obj}")
    print(f"max_used_height = {model.max_used_height.value()}")
    print(f"max_x_extent    = {model.max_x_extent.value()}")
    print(f"max_y_extent    = {model.max_y_extent.value()}")

    print("\n================= PER-BOX VARIABLES =================")
    header = f"{'idx':>3} | {'x':>4} {'y':>4} {'z':>4} | {'rot':>3} | {'eff_len':>7} {'eff_wid':>7} {'height':>6}"
    print(header)
    print("-" * len(header))

    for p in range(model.num_boxes):
        print(
            f"{p:3d} | "
            f"{model.x[p].value():4d} "
            f"{model.y[p].value():4d} "
            f"{model.z[p].value():4d} | "
            f"{int(model.rot[p].value()):3d} | "
            f"{model.eff_len[p].value():7d} "
            f"{model.eff_wid[p].value():7d} "
            f"{model.heights[p]:6d}"
        )

    print("====================================================\n")