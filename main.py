# Main entry point for running the box placement model test

from tests.test_A_box_placement_model import run_box_placement_test, print_model_solution
from utils.pipeline import  run_box_placement, run_reccomend_fill, run_full_pipeline
from utils.visualize_boxes import plot_boxes_3d
from models.A_box_placement_model import BoxPlacementModel
import time

W, L, H = 235, 1203, 270
BUF = 5

def plot_solution(model):

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

    plot_boxes_3d(W, L, H, boxes)

def main():
    excel_path = "sample_instances/input_pallets.xlsx"  # adjust path
    start_time = time.time()
    modelA, free_len = run_box_placement(excel_path, W, L, H, BUF, solver="ortools", time_limit=60)

    if modelA is None:
        print("No solution found for box placement.")
        return
    
    plot_solution(modelA)
    end_time = time.time()
    print(f"Solved in {end_time - start_time:.2f} seconds")
    print(f"Free length for extra pallets: {free_len}")



if __name__ == "__main__":
    main()