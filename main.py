# Main entry point for running the box placement model test

from utils.pipeline import  run_box_placement, run_reccomend_fill
from utils.visualize_boxes import plot_boxes_3d, plot_modelA, plot_modelA_with_extras
from models.A_box_placement_model import BoxPlacementModel
import time

W, L, H = 235, 1203, 270
BUF = 5

"""
This version of the code implements a two-stage pipeline: 
(A) a full 3D pallet placement model (BoxPlacementModel) that computes an optimal packing inside the container, 
and (B) a simplified 1D optimization model (ReccomendFillModel) 
that recommends how many extra pallets of each type could theoretically fit in the remaining free length along the container’s Y-axis. 
Model A is complete and uses real 3D constraints (rotation, support, non-overlap, boundaries). 
Model B, however, is currently not a full packing model—it ignores x/z placement, stacking, and rotations, 
and only maximizes added volume along a single dimension. 

As a result, the visualization of added pallets is placeholder/MVP: 
extra pallets are simply drawn in a straight strip starting at the end of the main placement, not packed optimally. 
The pipeline works end-to-end, 
but Stage B and the combined visualization are still prototypes and should not be interpreted as physically accurate packing 
until the second model is extended into actual 3D placement logic.
"""


def main():
    excel_path = "sample_instances/input_small.xlsx"

    start_time = time.time()    
    modelA, free_len, pallets_data = run_box_placement(
        excel_path, W, L, H, BUF, solver="ortools", time_limit=300
    )
    end_time = time.time()
    print(f"Model A solved in {end_time - start_time:.2f} seconds.")    
    if modelA is None:
        return
    plot_modelA(modelA, W, L, H, BUF)

    modelB_info = run_reccomend_fill(pallets_data, BUF, free_len, solver="ortools", time_limit=300)
    if modelB_info is not None:
        plot_modelA_with_extras(modelA, modelB_info["add"], W, L, H, BUF)



if __name__ == "__main__":
    main()