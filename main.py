# Main entry point for running the box placement model test

from tests.test_A_box_placement_model import run_box_placement_test, print_model_solution
from utils.parse_xlsx import parse_pallet_excel
from models.A_box_placement_model import BoxPlacementModel
from utils.visualize_boxes import plot_boxes_3d
import time

W, L, H = 235, 1203, 270
BUF = 5

def plot_solution(model):

    # 2) Build the `boxes` list from model variable values
    boxes = []
    for p in range(model.num_boxes):
        boxes.append({
            "id": p + 1,
            "x": model.x[p].value(),
            "y": model.y[p].value(),
            "z": model.z[p].value(),
            # effective dimensions after rotation
            "w": model.eff_wid[p].value(),
            "l": model.eff_len[p].value(),
            # height is fixed input, not a decision var
            "h": model.heights[p],
        })

    # 3) Plot the solution
    plot_boxes_3d(W, L, H, boxes)

def main():
    excel_path = "sample_instances/input_pallets.xlsx"  # adjust path
    lengths, widths, heights, pallets_data = parse_pallet_excel(excel_path)
    model = BoxPlacementModel(lengths, widths, heights, W, L, H, BUF)
    
    start_time = time.perf_counter()
    solved = model.solve(solver="ortools", time_limit=60)
    end_time = time.perf_counter()
    print(f"Solved in {end_time - start_time:.2f} seconds")

    if solved:
        print_model_solution(model)
        plot_solution(model)
    else:
        print("No solution found, skipping printing/plotting.")
        return


if __name__ == "__main__":
    main()