"""
MAIN PIPELINE — 1D ROW-BLOCK CONTAINER PACKING
=============================================

Assumes the following already exist and are imported:
- parse_pallet_excel_v3  (or v2) returning meta_per_pallet with weight_kg
- build_row_blocks_from_pallets
- RowBlock1DOrderModel (1D order-based model)

NOTE: Your current RowBlock1DOrderModel does NOT accept group_ids.
To avoid selecting both rotation variants of the same physical block, this script
selects ONE variant per physical block_id before solving (currently: shortest length).
If you later add group_ids support in the model, remove the `select_one_variant_per_block()` step
and pass group_ids into the model.
"""

from typing import List, Dict, Any

from utils.parse_xlsx import parse_pallet_excel_v3
from utils.oneDbuildblocks import build_row_blocks_from_pallets
from models.A_1D_multi_container_placement_chatGPT import RowBlock1DOrderModel

from utils.visualize_row_blocks import plot_all_row_block_containers_pallets



def select_one_variant_per_block(blocks):
    """Keep exactly one variant per physical block_id (currently the shortest length)."""
    best = {}
    for b in blocks:
        bid = b.block_id
        if bid not in best:
            best[bid] = b
        else:
            # choose shorter length variant to increase chance of fitting
            if b.length_cm < best[bid].length_cm:
                best[bid] = b
    # preserve stable ordering by block_id
    return [best[k] for k in sorted(best.keys())]


def main(
    excel_path: str,
    sheet_name=0,
    L_cm: int = 1203,
    gap_cm: int = 5,
    Wmax_kg: int = 18000,
    Hdoor_cm: int = 250,
    solver: str = "ortools",
    time_limit: int = 10,
):
    # ------------------------------------------------------------
    # 1) Parse Excel
    # ------------------------------------------------------------
    print("\n=== STEP 1: Parsing Excel ===")

    lengths, widths, heights, pallets_data, meta_per_pallet = parse_pallet_excel_v3(
        excel_path,
        sheet_name=sheet_name,
        return_per_pallet_meta=True,
    )

    print(f"Parsed {len(meta_per_pallet)} physical pallets")
    print(f"Distinct pallet rows: {len(pallets_data)}")

    # ------------------------------------------------------------
    # 2) Build row-block instances (and validate multiples)
    # ------------------------------------------------------------
    print("\n=== STEP 2: Building Row-Blocks ===")

    blocks, recommendations, warnings = build_row_blocks_from_pallets(
        meta_per_pallet,
        Hdoor_cm=Hdoor_cm,
        require_multiples=True,   # HARD requirement
    )



    print("DEBUG pallet heights unique:", sorted(set(pm["height"] for pm in meta_per_pallet))[:20])
    print("DEBUG block heights unique:", sorted(set(b.height_cm for b in blocks))[:20])



    if warnings:
        print("\nWARNINGS during block construction:")
        for w in warnings:
            print(" -", w)

    if recommendations:
        print("\nORDER NOT VALID FOR FULL ROW-BLOCK MODEL")
        print("You need to add pallets to reach valid multiples:\n")
        for k, v in recommendations.items():
            print(f"  {k}: add {v} pallets")
        print("\nStopping before optimization.")
        return

    print(f"Constructed {len(blocks)} row-block VARIANTS")
    physical_blocks = len(set(b.block_id for b in blocks))
    print(f"Corresponding to {physical_blocks} physical row-blocks")

    # IMPORTANT: current model cannot enforce mutual exclusion across rotation variants.
    # So we keep only one variant per physical block_id.
    blocks = select_one_variant_per_block(blocks)
    print(f"After choosing ONE variant per block_id: {len(blocks)} blocks")

    # ------------------------------------------------------------
    # 3) Multi-container loop
    # ------------------------------------------------------------
    print("\n=== STEP 3: Solving Containers ===")

    remaining_blocks = blocks[:]  # copy
    containers: List[Dict[str, Any]] = []
    container_idx = 1

    while remaining_blocks:
        print(f"\n--- Solving container {container_idx} ---")

        # ---- Flatten remaining blocks into model arrays ----
        lens = [b.length_cm for b in remaining_blocks]
        hs   = [b.height_cm for b in remaining_blocks]
        ws   = [b.weight_kg for b in remaining_blocks]
        vals = [b.value for b in remaining_blocks]

        # ---- Build model ----
        model = RowBlock1DOrderModel(
            lengths_cm=lens,
            heights_cm=hs,
            weights_kg=ws,
            values=vals,
            L_cm=L_cm,
            gap_cm=gap_cm,
            Wmax_kg=Wmax_kg,
            Hdoor_cm=Hdoor_cm,
        )

        solved = model.solve(
            solver=solver,
            time_limit=time_limit,
        )

        if not solved:
            raise RuntimeError(f"No feasible solution for container {container_idx}")

        # ----------------------------------------------------
        # 4) Extract solution
        # ----------------------------------------------------
        chosen_variant_indices = model.loaded_indices_in_order()
        chosen_blocks = [remaining_blocks[i - 1] for i in chosen_variant_indices]

        # Physical block IDs used
        used_block_ids = {b.block_id for b in chosen_blocks}

        if len(chosen_blocks) == 0:
            print("\n!! EMPTY CONTAINER SOLUTION RETURNED !!")
            print(f"Remaining blocks: {len(remaining_blocks)}")

            door_ok = [b for b in remaining_blocks if b.height_cm <= Hdoor_cm]
            print(f"Door-OK blocks (height <= {Hdoor_cm}): {len(door_ok)}")

            heights_unique = sorted({b.height_cm for b in remaining_blocks})
            print(f"Remaining heights (unique): {heights_unique[:30]}{'...' if len(heights_unique) > 30 else ''}")

            raise RuntimeError(
                "Solver returned empty selection. Likely no feasible non-empty packing exists "
                "under current constraints (often because no remaining door-allowed blocks)."
            )

        # Reconstruct y-coordinates (back -> door)
        y_cursor = 0
        rows = []
        for b in chosen_blocks:
            rows.append({
                "block_id": b.block_id,
                "block_type": b.block_type_key,
                "length_cm": b.length_cm,
                "height_cm": b.height_cm,
                "weight_kg": b.weight_kg,
                "pallet_count": b.value,
                "y_start_cm": y_cursor,
                "pallets": b.pallets,
            })
            y_cursor += b.length_cm + gap_cm

        used_len = model.usedLen.value()
        leftover = L_cm - used_len

        container_info = {
            "container_index": container_idx,
            "rows": rows,
            "used_length_cm": used_len,
            "leftover_cm": leftover,
            "loaded_value": model.loadedValue.value(),
            "loaded_weight": model.loadedWeight.value(),
        }
        containers.append(container_info)

        # ----------------------------------------------------
        # 5) Print container summary
        # ----------------------------------------------------
        print(f"Loaded blocks: {len(rows)}")
        print(f"Used length: {used_len} / {L_cm} cm")
        print(f"Leftover length: {leftover} cm")
        print(f"Loaded pallets: {model.loadedValue.value()}")
        print(f"Loaded weight: {model.loadedWeight.value()} kg")

        print("\nRow layout (back → door):")
        for r in rows:
            print(
                f"  y={r['y_start_cm']:>4} cm | "
                f"{r['block_type']:>12} | "
                f"L={r['length_cm']:>3} | "
                f"H={r['height_cm']:>3} | "
                f"pallets={r['pallet_count']}"
            )

        # ----------------------------------------------------
        # 6) Remove used physical blocks
        # ----------------------------------------------------
        remaining_blocks = [b for b in remaining_blocks if b.block_id not in used_block_ids]
        container_idx += 1

    # ------------------------------------------------------------
    # 7) Final output
    # ------------------------------------------------------------
    print("\n=== ALL CONTAINERS SOLVED ===")
    print(f"Total containers used: {len(containers)}")

    # ------------------------------------------------------------
    # 8) Visualization of all containers
    # ------------------------------------------------------------
    # containers = main("sample_instances/input_large.xlsx")
    plot_all_row_block_containers_pallets(containers, W=235, L=1203, H=270)

    return containers


if __name__ == "__main__":
    main("sample_instances/input_large.xlsx")
