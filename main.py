# # Main entry point for running the box placement model test

# from utils.pipeline import  run_box_placement
# from utils.visualize_boxes import plot_modelA
# from models.A_box_placement_model import BoxPlacementModel
# import time

# W, L, H = 235, 1203, 270
# BUF = 5

# """
# This version of the code replaces the original continuous 3D pallet placement model with a discretised slot-based formulation,
# removing rotations and simplifying geometric constraints to dramatically reduce search complexity. 
# All placement, overlap, and stacking rules were rewritten to operate on grid indices instead of centimetres. 
# The plotting system was redesigned accordingly, making the pipeline stable and fast while preserving realistic behaviour. 
# The prototype recommender (Model B) was removed from the pipeline so we can focus on a clean, reliable Model A that can soon scale to multi-container allocation. 
# The end result is a far more efficient, solver-friendly engine ready for the next development stage.
# """


# def main():
#     excel_path = "sample_instances/input_large.xlsx"

#     start_time = time.time()    

#     modelA, free_len, pallets_data = run_box_placement(
#     excel_path, W, L, H, BUF, solver="ortools", time_limit=10
# )

#     end_time = time.time()
#     print(f"Model A solved in {end_time - start_time:.2f} seconds.")   

#     if modelA is None:
#         return
    
#     plot_modelA(modelA, W, L, H, pallets_data=pallets_data)

#     # modelB_info = run_reccomend_fill(pallets_data, BUF, free_len, solver="ortools", time_limit=300)
#     # if modelB_info is not None:
#     #     plot_modelA_with_extras(modelA, modelB_info["add"], W, L, H, BUF)



# if __name__ == "__main__":
#     main()


# Main entry point for running the box placement model test

from utils.pipeline import  run_box_placement, run_multi_container_placement
from utils.visualize_boxes import plot_modelA, plot_modelAA
from models.A_box_placement_model import BoxPlacementModel
import time

W, L, H = 235, 1203, 270
BUF = 5

"""
This version of the code replaces the original continuous 3D pallet placement model with a discretised slot-based formulation,
removing rotations and simplifying geometric constraints to dramatically reduce search complexity. 
All placement, overlap, and stacking rules were rewritten to operate on grid indices instead of centimetres. 
The plotting system was redesigned accordingly, making the pipeline stable and fast while preserving realistic behaviour. 
The prototype recommender (Model B) was removed from the pipeline so we can focus on a clean, reliable Model A that can soon scale to multi-container allocation. 
The end result is a far more efficient, solver-friendly engine ready for the next development stage.
"""


def main():

    excel_path = "sample_instances/input_large.xlsx"

    start_time = time.time()

    containers = run_multi_container_placement(
        excel_path,
        W, L, H, BUF,
        solver="ortools",
        time_limit_per_container=10,
        step_x=10, step_y=10,
        unload_limit=4,
    )

    end_time = time.time()
    print(f"Solved {len(containers)} container(s) in {end_time - start_time:.2f}s")

    for i, c in enumerate(containers, start=1):
        print(f"\n--- Container {i} ---")
        model = c["model"]
        # you can print stats here if you want:
        print("loaded pallets:", sum(model.load[p].value() for p in range(model.num_boxes)))
        print("used length:", model.max_y_extent.value())
        print("used width :", model.max_x_extent.value())
        print("used height:", model.max_used_height.value())

        # plot (pass loaded_meta if you want labels)
        plot_modelAA(model, W, L, H, pallets_data=c.get("pallets_data"), loaded_meta=c.get("loaded_meta"))



if __name__ == "__main__":
    main()