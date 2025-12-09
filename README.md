# Container Filling (CPMpy)

This project loads pallet data from an Excel file, builds a 3D pallet-placement model using CPMpy, and visualizes the final layout in a 3D plot.

```
Excel File
    ↓
parse_xlsx.py (parse_pallet_excel)
    ↓ Returns: lengths[], widths[], heights[], pallet_types[]
    ↓
Pipeline (utils/pipeline.py)
    ├─ run_box_placement() → Stage A (BoxPlacementModel)
    │                     Returns: model, free_len, pallet_metadata
    │
    └─ run_reccomend_fill() → Stage B (ReccomendFillModel)
                            Returns: add_list, total_volume
    ↓
Visualization (utils/visualize_boxes.py)
    ↓ Renders 3D plot
```

## Codebase Overview
This is a constraint programming solution for optimizing the placement of pallets/boxes into a container, with a two-stage pipeline approach.

### Stage A (Primary): 3D Box Placement Model (BoxPlacementModel)
- Takes a list of individual pallets with dimensions (length, width, height) and packs them into a fixed container
- Uses constraint programming (CPMpy) to solve a complex 3D bin packing problem
- Handles realistic constraints: rotation, stacking with support, no overlap, buffer spacing, bounding box optimization
- Output: Optimal 3D coordinates for each pallet + container utilization metrics

### Stage B (Secondary): Extra Pallet Recommendation Model (ReccomendFillModel)

- Takes the free remaining space from Stage A and recommends additional pallets that could fit
- Currently simplified: only considers 1D capacity along container length (Y-axis)
- Limitation: Does NOT actually place these extras in 3D—it's a volume maximization heuristic, not a full packing model
- Output: Counts of how many extra pallets of each type could theoretically fit

### Key Workflow

1. Input: Excel file with pallet type definitions (dimensions, counts)
2. Parse: Convert Excel data into flattened lists (one entry per physical pallet)
3. Stage A: Place all pallets optimally in 3D container → get used space
4. Stage B: Recommend extras based on remaining free length
5. Visualize: Plot 3D arrangement (Stage A placement + Stage B extras as placeholder)

## Optimization Constraints (Stage A)

1. Geometry: Pallets stay inside container boundaries; rotation allowed (0°/90° along XY plane)
2. Stacking: Pallets can be stacked, but only on pallets with matching footprint (same length×width)
3. Support: No levitation—each pallet either sits on floor OR fully supported by pallet below
4. Spacing: Buffer zone between pallets (no overlap) in X/Y; free stacking in Z (height)
5. Uniformity: Pallets in the same row must have identical footprints
6. Symmetry: Identical pallets ordered lexicographically to reduce search space

- Objective: Minimize (1000 × max height) + max X-extent + max Y-extent
→ Prioritizes compact vertical stacking, then horizontal compactness