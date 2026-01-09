# visualize_boxes.py
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D


# -------------------------------------------------------------------
# High-level function for main.py
# -------------------------------------------------------------------

def plot_modelA(modelA, W, L, H, pallets_data=None):
    """
    Plot just the solution of Model A, with optional pallet metadata.
    """
    boxes = build_boxes_from_modelA(modelA)
    plot_boxes_3d(W, L, H, boxes)
    return boxes

# -------------------------------------------------------------------
# Helper to expand pallets_data into per-box metadata
# -------------------------------------------------------------------

def _expand_meta_from_pallets_data(pallets_data, num_boxes):
    """
    Expand pallets_data (per pallet type with 'count') into a per-pallet
    metadata list aligned with box indices 0..num_boxes-1.

    Assumes the BoxPlacementModel was created by expanding lengths/widths/heights
    in the same order and repetition as here.
    """
    meta = []
    for row in pallets_data:
        for _ in range(row["count"]):
            meta.append({
                "pallet_type": row.get("pallet_type", ""),
                "pallet_size": row.get("pallet_size", ""),
                "length": row.get("length", None),
                "width": row.get("width", None),
                "height": row.get("height", None),
            })
    # Optional safety check:
    if len(meta) != num_boxes:
        print(f"[WARN] meta count {len(meta)} != num_boxes {num_boxes}")
    return meta

# -------------------------------------------------------------------
# Helpers: build boxes from Model A
# -------------------------------------------------------------------

def build_boxes_from_modelA(modelA):
    """
    Turn a discretised BoxPlacementModel solution into a list of box dicts.

    Assumes the model exposes:
      - num_boxes
      - ix[p], iy[p], z[p]      : decision variables (slot indices and height in cm)
      - STEP_X, STEP_Y          : discretisation steps in cm
      - widths[p], lengths[p]   : pallet footprint in cm (input data)
      - heights[p]              : pallet height in cm (input data)
    """
    boxes = []

    step_x = modelA.STEP_X
    step_y = modelA.STEP_Y

    for p in range(modelA.num_boxes):
        ix = modelA.ix[p].value()
        iy = modelA.iy[p].value()
        z  = modelA.z[p].value()

        # Safety: if something is None, you know immediately
        if ix is None or iy is None or z is None:
            raise ValueError(f"Unassigned variable for pallet {p} – was the model solved?")

        x_cm = int(ix * step_x)
        y_cm = int(iy * step_y)

        w_cm = int(modelA.widths[p])
        l_cm = int(modelA.lengths[p])
        h_cm = int(modelA.heights[p])

        boxes.append({
            "id": p + 1,
            "x": x_cm,
            "y": y_cm,
            "z": z,
            "w": w_cm,
            "l": l_cm,
            "h": h_cm,
        })

    return boxes

# -------------------------------------------------------------------
# Main 3D plotting function
# -------------------------------------------------------------------

def plot_boxes_3d(W, L, H, boxes):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    ax.set_xlim(0, W)
    ax.set_ylim(0, L)
    ax.set_zlim(0, H)
    ax.set_box_aspect((W, L, H))

    colors = ['tab:blue', 'tab:orange', 'tab:green',
              'tab:red', 'tab:purple', 'tab:brown',
              'tab:pink', 'tab:gray', 'tab:olive', 'tab:cyan']

    for i, b in enumerate(boxes):
        ax.bar3d(
            b["x"], b["y"], b["z"],
            b["w"], b["l"], b["h"],
            alpha=0.5,
            color=colors[i % len(colors)],
            edgecolor="k",
            linewidth=0.5,
            shade=True
        )

        cx = b["x"] + b["w"] / 2
        cy = b["y"] + b["l"] / 2
        cz = b["z"] + b["h"] / 2
        ax.text(cx, cy, cz, str(b["id"]), color="k", fontsize=8)

    ax.set_xlabel('X (width)')
    ax.set_ylabel('Y (length)')
    ax.set_zlabel('Z (height)')

    # ---------- legend text (id → dims (+ type)) ----------
    legend_lines = []
    for b in boxes:
        # If pallet_size string is present (e.g. "1.15x1.15x1.01"), use it.
        if b.get("pallet_size"):
            size_label = b["pallet_size"]
        else:
            size_label = f"{b['l']}x{b['w']}x{b['h']}"

        line = f"{b['id']:>2}: {size_label}"
        if b.get("pallet_type"):
            line += f"  ({b['pallet_type']})"
        legend_lines.append(line)

    legend_text = "\n".join(legend_lines)

    # put legend in figure margin (bottom-left; tweak coords if needed)
    fig.text(
        0.02, 0.02,
        legend_text,
        fontsize=8,
        family="monospace",
        va="bottom",
        ha="left"
    )
    # ------------------------------------------------------

    plt.tight_layout()
    plt.show()

# # -------------------------------------------------------------------
# # Helpers: build boxes from Model A and from B's output
# # -------------------------------------------------------------------

# def build_boxes_from_modelA(modelA):
#     """
#     Turn a BoxPlacementModel (Model A) solution into a list of box dicts.
#     """
#     boxes = []
#     for p in range(modelA.num_boxes):
#         boxes.append({
#             "id": p + 1,
#             "x": modelA.x[p].value(),
#             "y": modelA.y[p].value(),
#             "z": modelA.z[p].value(),
#             "w": modelA.eff_wid[p].value(),
#             "l": modelA.eff_len[p].value(),
#             "h": modelA.heights[p],
#         })
#     return boxes


# def build_extra_boxes_from_B(modelA, add_list, pallets_data, BUF, W, L, H):
#     """
#     Build a simple 3D layout for extra pallets recommended by Model B.

#     We only have counts per type (add_list), so we:
#       - place extras in a strip along Y
#       - at x = 0, z = 0
#       - starting at modelA.max_y_extent
#       - stop if we run out of container length L
#     """
#     boxes_extra = []
#     next_id = modelA.num_boxes + 1

#     start_y = modelA.max_y_extent.value()
#     current_y = start_y

#     for t, count in enumerate(add_list):
#         if count <= 0:
#             continue

#         p = pallets_data[t]
#         l = int(p["length"])
#         w = int(p["width"])
#         h = int(p["height"])

#         for _ in range(count):
#             if current_y + l > L:
#                 break  # don't overflow container

#             boxes_extra.append({
#                 "id": next_id,
#                 "x": 0,
#                 "y": current_y,
#                 "z": 0,
#                 "w": w,
#                 "l": l,
#                 "h": h,
#             })
#             next_id += 1
#             current_y += l + BUF

#     return boxes_extra


# def plot_modelA_with_extras(modelA, add_list, pallets_data, BUF, W, L, H):
#     """
#     Plot Model A + extra pallets (from Model B's 'add_list') in one figure.
#     """
#     boxes_main = build_boxes_from_modelA(modelA)
#     boxes_extra = build_extra_boxes_from_B(modelA, add_list, pallets_data, BUF, W, L, H)
#     boxes_all = boxes_main + boxes_extra
#     plot_boxes_3d(W, L, H, boxes_all)
#     return boxes_all    

# utils/visualize_boxes.py

def build_boxes_from_modelAA(modelA, loaded_meta=None):
    boxes = []
    for p in range(modelA.num_boxes):
        if hasattr(modelA, "load"):
            if modelA.load[p].value() == 0:
                continue

        # discretised coordinates -> cm
        x_cm = modelA.ix[p].value() * modelA.STEP_X
        y_cm = modelA.iy[p].value() * modelA.STEP_Y

        b = {
            "id": p + 1,
            "x": x_cm,
            "y": y_cm,
            "z": modelA.z[p].value(),
            "w": modelA.widths[p],
            "l": modelA.lengths[p],
            "h": modelA.heights[p],
        }

        if loaded_meta is not None:
            # loaded_meta is in the same order as "loaded pallets", not p.
            # easiest is: store meta in model order before solving (recommended).
            pass

        boxes.append(b)
    return boxes


def plot_modelAA(modelA, W, L, H, pallets_data=None, loaded_meta=None):
    boxes = build_boxes_from_modelAA(modelA, loaded_meta=loaded_meta)
    plot_boxes_3d(W, L, H, boxes)
    return boxes