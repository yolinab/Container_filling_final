# visualize_boxes.py
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401


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
        # bar3d: x, y, z, dx, dy, dz
        ax.bar3d(
            b["x"], b["y"], b["z"],
            b["w"], b["l"], b["h"],
            alpha=0.5,
            color=colors[i % len(colors)],
            edgecolor="k",
            linewidth=0.5,
            shade=True
        )

        # label roughly at center
        cx = b["x"] + b["w"] / 2
        cy = b["y"] + b["l"] / 2
        cz = b["z"] + b["h"] / 2
        ax.text(cx, cy, cz, str(b["id"]), color="k")

    ax.set_xlabel('X (width)')
    ax.set_ylabel('Y (length)')
    ax.set_zlabel('Z (height)')

    plt.tight_layout()
    plt.show()

# -------------------------------------------------------------------
# Helpers: build boxes from Model A and from B's output
# -------------------------------------------------------------------

def build_boxes_from_modelA(modelA):
    """
    Turn a BoxPlacementModel (Model A) solution into a list of box dicts.
    """
    boxes = []
    for p in range(modelA.num_boxes):
        boxes.append({
            "id": p + 1,
            "x": modelA.x[p].value(),
            "y": modelA.y[p].value(),
            "z": modelA.z[p].value(),
            "w": modelA.eff_wid[p].value(),
            "l": modelA.eff_len[p].value(),
            "h": modelA.heights[p],
        })
    return boxes


def build_extra_boxes_from_B(modelA, add_list, pallets_data, BUF, W, L, H):
    """
    Build a simple 3D layout for extra pallets recommended by Model B.

    We only have counts per type (add_list), so we:
      - place extras in a strip along Y
      - at x = 0, z = 0
      - starting at modelA.max_y_extent
      - stop if we run out of container length L
    """
    boxes_extra = []
    next_id = modelA.num_boxes + 1

    start_y = modelA.max_y_extent.value()
    current_y = start_y

    for t, count in enumerate(add_list):
        if count <= 0:
            continue

        p = pallets_data[t]
        l = int(p["length"])
        w = int(p["width"])
        h = int(p["height"])

        for _ in range(count):
            if current_y + l > L:
                break  # don't overflow container

            boxes_extra.append({
                "id": next_id,
                "x": 0,
                "y": current_y,
                "z": 0,
                "w": w,
                "l": l,
                "h": h,
            })
            next_id += 1
            current_y += l + BUF

    return boxes_extra


# -------------------------------------------------------------------
# High-level functions for main.py
# -------------------------------------------------------------------

def plot_modelA(modelA, W, L, H):
    """
    Plot just the solution of Model A.
    """
    boxes = build_boxes_from_modelA(modelA)
    plot_boxes_3d(W, L, H, boxes)
    return boxes


def plot_modelA_with_extras(modelA, add_list, pallets_data, BUF, W, L, H):
    """
    Plot Model A + extra pallets (from Model B's 'add_list') in one figure.
    """
    boxes_main = build_boxes_from_modelA(modelA)
    boxes_extra = build_extra_boxes_from_B(modelA, add_list, pallets_data, BUF, W, L, H)
    boxes_all = boxes_main + boxes_extra
    plot_boxes_3d(W, L, H, boxes_all)
    return boxes_all    