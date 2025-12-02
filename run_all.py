# #!/usr/bin/env python3

# from excel_to_dzn import build_dzn_from_excel
# from run_container_packing import run_container_packing

# def main():
#     print("▶ Generating MiniZinc data from Excel...")
#     build_dzn_from_excel()

#     print("▶ Running MiniZinc + plotting layout...")
#     run_container_packing()

# if __name__ == "__main__":
#     main()

# run_all.py

from excel_to_dzn import build_dzn_from_excel
from run_container_packing import run_container_packing, find_free_floor_segments, L
from extra_recommender import run_extra_recommender

def main():
    # 1) Excel → base .dzn
    build_dzn_from_excel()

    # 2) First MiniZinc run: current layout
    boxes, stats = run_container_packing(
        data_path="instance_from_excel.dzn",
        title="Current stacking",
        do_plot=True
    )

    
    # ------------------------------------------------------------
    # Compute free floor length from output of first packing
    # ------------------------------------------------------------
    print("▶ Computing free floor segments...")
    segments = find_free_floor_segments(boxes, L)
    print(f"Free segments: {segments}")

    free_len = sum(end - start for (start, end) in segments)
    print(f"Total free floor length available: {free_len} cm")

    # ------------------------------------------------------------
    # Step 3: Run MINIZINC “extra pallet selector”
    # ------------------------------------------------------------
    print("▶ Selecting recommended extra pallets using MiniZinc...")
    dzn_with_extras = run_extra_recommender(
        free_len=free_len
    )

    if dzn_with_extras is None:
        print("No extra pallets found.")
        return

    print(f"Created new extended DZN: {dzn_with_extras}")

    # ------------------------------------------------------------
    # Step 4: Second MiniZinc run WITH recommended pallets
    # ------------------------------------------------------------
    print("▶ Running extended container packing...")
    run_container_packing(
        data_path=str(dzn_with_extras),
        title="Stacking with recommended extra pallets",
        do_plot=True
    )

if __name__ == "__main__":
    main()