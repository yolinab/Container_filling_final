# pipeline.py

from models.A_box_placement_model import BoxPlacementModel
from models.B_reccomend_fill_model import ReccomendFillModel
from utils.parse_xlsx import parse_pallet_excel


def run_box_placement(excel_path, W, L, H, BUF, solver="ortools", time_limit=60):
    """
    Run Model A (BoxPlacementModel) on pallets defined in the Excel file.
    Returns (model, free_len) if solved, else (None, 0).
    """
    lengths, widths, heights, pallets_data = parse_pallet_excel(excel_path)

    model = BoxPlacementModel(lengths, widths, heights, W, L, H, BUF)

    # ! Run on 8 CPU threads !
    # solved = model.solve(solver=solver, time_limit=time_limit, num_search_workers=8)
    solved = model.solve(solver=solver, time_limit=time_limit)

    if not solved:
        print("Box placement model: no solution")
        return None, 0

    # Simple definition: remaining free length along Y
    max_y = model.max_y_extent.value()
    free_len = max(0, L - max_y)

    return model, free_len


def run_reccomend_fill(pallets_data, BUF, free_len, solver="ortools", time_limit=60):
    """
    Run Model B (ReccomendFillModel) given free_len and pallet types.

    pallets_data is the per-type list from parse_pallet_excel():
      [
        { "pallet_size": ..., "length": ..., "width": ..., "height": ..., "pallet_type": ..., "count": ...},
        ...
      ]
    """
    if free_len <= 0:
        print("No free length available, skipping extra selection.")
        return None

    lengths = [p["length"] for p in pallets_data]
    widths  = [p["width"]  for p in pallets_data]
    heights = [p["height"] for p in pallets_data]

    # For max_add, simplest choice: allow up to some cap per type
    # (you can replace this by a real limit later)
    max_add = [10] * len(pallets_data)

    modelB = ReccomendFillModel(lengths, widths, heights, BUF, free_len, max_add)
    solved = modelB.solve(solver=solver, time_limit=time_limit)

    if not solved:
        print("Extra selection model: no solution")
        return None

    add_list = modelB.get_solution_add()
    return {
        "model": modelB,
        "add": add_list,
        "total_volume": modelB.total_added_volume.value()
    }


def run_full_pipeline(excel_path, W, L, H, BUF, solver="ortools", time_limit=60):
    """
    Full pipeline: A (placement) -> compute free_len -> B (extra selection).
    """
    # 1) Run placement
    lengths, widths, heights, pallets_data = parse_pallet_excel(excel_path)
    modelA = BoxPlacementModel(lengths, widths, heights, W, L, H, BUF)
    solvedA = modelA.solve(solver=solver, time_limit=time_limit)

    if not solvedA:
        print("Box placement model: no solution, aborting pipeline.")
        return

    max_y = modelA.max_y_extent.value()
    free_len = max(0, L - max_y)
    print(f"Free length for extra pallets: {free_len}")

    # 2) Run extra selection on the same pallet types
    lengths_types = [p["length"] for p in pallets_data]
    widths_types  = [p["width"]  for p in pallets_data]
    heights_types = [p["height"] for p in pallets_data]

    max_add = [10] * len(pallets_data)  # placeholder cap

    modelB = ReccomendFillModel(lengths_types, widths_types, heights_types, BUF, free_len, max_add)
    solvedB = modelB.solve(solver=solver, time_limit=time_limit)

    if not solvedB:
        print("Extra selection model: no solution")
        return

    add_list = modelB.get_solution_add()
    print("Recommended extra pallets per type:", add_list)
    print("Total added volume:", modelB.total_added_volume.value())

    # You can return both models for inspection/plotting
    return modelA, modelB, add_list