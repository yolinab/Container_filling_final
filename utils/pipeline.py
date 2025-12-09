# pipeline.py

from models.A_box_placement_model import BoxPlacementModel
from utils.parse_xlsx import parse_pallet_excel


def run_box_placement(
    excel_path,
    W,
    L,
    H,
    BUF,
    solver="ortools",
    time_limit=60,
    step_x=10,
    step_y=10,
):
    # 1) Parse Excel → lists of per-pallet dimensions (cm)
    lengths, widths, heights, pallets_data = parse_pallet_excel(excel_path)

    # 2) Build simplified discretised model (no rotations, X/Y in slots)
    model = BoxPlacementModel(
        lengths,
        widths,
        heights,
        W,
        L,
        H,
        BUF,
        step_x=step_x,
        step_y=step_y,
    )

    # 3) Solve
    solved = model.solve(
        solver=solver,
        time_limit=time_limit,
        # num_search_workers=8,  # uncomment if you want parallel OR-Tools
    )

    if not solved:
        print("Box placement model: no solution")
        return None, 0, pallets_data

    # 4) Free length along Y (cm) from the bounding box
    #    max_y_extent is already in cm inside the model
    max_y = model.max_y_extent.value()
    free_len = max(0, L - max_y)

    return model, free_len, pallets_data