from utils.pipeline import  run_box_placement, run_multi_container_placement, compute_container_metrics
from utils.visualize_boxes import plot_modelA, plot_modelAA
from models.A_box_placement_model import BoxPlacementModel
import time

W, L, H = 235, 1203, 270
BUF = 0

"""
This version of the code replaces the original continuous 3D pallet placement model with a discretised slot-based formulation,
removing rotations and simplifying geometric constraints to dramatically reduce search complexity. 
All placement, overlap, and stacking rules were rewritten to operate on grid indices instead of centimetres. 
The plotting system was redesigned accordingly, making the pipeline stable and fast while preserving realistic behaviour. 
The prototype recommender (Model B) was removed from the pipeline so we can focus on a clean, reliable Model A that can soon scale to multi-container allocation. 
The end result is a far more efficient, solver-friendly engine ready for the next development stage.
"""

# Last save before 2D refactor attempt?


def main():

    excel_path = "sample_instances/input_large.xlsx"

    start_time = time.time()

    containers = run_multi_container_placement(
        excel_path,
        W, L, H, BUF,
        solver="ortools",
        time_limit_per_container=30,
        step_x=5, step_y=5,
        unload_limit=4,
    )

    end_time = time.time()
    print(f"Solved {len(containers)} container(s) in {end_time - start_time:.2f}s")

    for i, c in enumerate(containers, start=1):
        print(f"\n--- Container {i} ---")
        model = c["model"]
        # you can print stats here if you want:
        
        metrics = compute_container_metrics(model, W, L, H)

        print(f"  Loaded pallets: {model.loaded_cnt_expr.value()}")
        print(f"  Used footprint: {metrics['used_y']} / {L} cm")
        print(f"  Used height:    {metrics['used_z']} / {H} cm")
        print(f"  Fill (volume):  {metrics['fill_pct_volume']:.1f}%")
        print(f"  Fill (effective): {metrics['fill_pct_effective']:.1f}%")

        # plot (pass loaded_meta if you want labels)
        plot_modelAA(model, W, L, H, pallets_data=c.get("pallets_data"), loaded_meta=c.get("loaded_meta"))



if __name__ == "__main__":
    main()
    