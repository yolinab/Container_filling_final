# pipeline.py

from models.A_box_placement_model import BoxPlacementModel
from utils.parse_xlsx import parse_pallet_excel_v2


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


# utils/pipeline.py

from models.A_box_placement_model import BoxPlacementModel
from utils.parse_xlsx import parse_pallet_excel

def run_single_container_subset(
    lengths, widths, heights,
    W, L, H, BUF,
    solver="ortools",
    time_limit=30,
    step_x=10, step_y=10,
    unload_limit=None,
    min_loaded_volume=None,
):
    """
    Solve ONE container using the subset+placement model.
    Returns: (model, loaded_indices, unloaded_indices)
    """
    model = BoxPlacementModel(
        lengths, widths, heights,
        W, L, H, BUF,
        step_x=step_x, step_y=step_y,
        unload_limit=unload_limit,
        min_loaded_volume=min_loaded_volume,
    )

    solved = model.solve(solver=solver, time_limit=time_limit)
    if not solved:
        return None, [], list(range(len(lengths)))

    loaded = [p for p in range(model.num_boxes) if model.load[p].value() == 1]
    unloaded = [p for p in range(model.num_boxes) if model.load[p].value() == 0]
    return model, loaded, unloaded


def run_multi_container_placement(
    excel_path,
    W, L, H, BUF,
    solver="ortools",
    time_limit_per_container=30,
    step_x=10, step_y=10,
    unload_limit=4,
):
    """
    Multi-container allocation via repeated subset solves.

    Returns:
      containers: list of dicts:
        {
          "model": solved_model,
          "pallets_data": pallets_data_for_loaded_pallets,
          "loaded_meta": list[dict] one per loaded pallet (meta),
          "loaded_indices": indices in the current remaining list,
        }
    """
    # IMPORTANT: we need per-pallet meta (one entry per physical pallet)
    # If your parse_pallet_excel doesn't return that yet, see note below.
    lengths, widths, heights, pallets_data, meta_per_pallet = parse_pallet_excel_v2(excel_path, return_per_pallet_meta=True)

    remaining_lengths = list(lengths)
    remaining_widths  = list(widths)
    remaining_heights = list(heights)
    remaining_meta    = list(meta_per_pallet)

    containers = []
    k = 1

    while len(remaining_lengths) > 0:
        # (Optional) lower bound for speed: force "almost all" pallets in
        # using unload_limit. Start strict; relax if infeasible.
        model, loaded_idx, unloaded_idx = run_single_container_subset(
            remaining_lengths, remaining_widths, remaining_heights,
            W, L, H, BUF,
            solver=solver,
            time_limit=time_limit_per_container,
            step_x=step_x, step_y=step_y,
            unload_limit=unload_limit,
            min_loaded_volume=None,
        )

        if model is None or len(loaded_idx) == 0:
            # Relax unload_limit and try once more before giving up
            if unload_limit is not None and unload_limit < len(remaining_lengths):
                unload_limit = min(len(remaining_lengths), unload_limit * 2)
                continue
            raise RuntimeError(f"No feasible loading found for remaining pallets (container {k}).")

        loaded_meta = [remaining_meta[i] for i in loaded_idx]

        # OPTIONAL: pallets_data_for_loaded could be aggregated by type for legend
        containers.append({
            "model": model,
            "loaded_meta": loaded_meta,
            "pallets_data": pallets_data,  # original type-level list (still useful)
            "loaded_indices": loaded_idx,
        })

        # Remove loaded pallets from remaining
        keep = unloaded_idx
        remaining_lengths = [remaining_lengths[i] for i in keep]
        remaining_widths  = [remaining_widths[i] for i in keep]
        remaining_heights = [remaining_heights[i] for i in keep]
        remaining_meta    = [remaining_meta[i] for i in keep]

        k += 1

    return containers