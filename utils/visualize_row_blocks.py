import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from collections import Counter


# ------------------------------------------------------------
# Helpers: summarize pallet composition inside a row-block
# ------------------------------------------------------------

def summarize_pallets(pallets, max_items=3):
    """
    Create a compact summary string of pallet composition.
    Groups by (length x width x height).
    """
    if not pallets:
        return "empty"

    counter = Counter(
        f"{p['length']}x{p['width']}x{p['height']}"
        for p in pallets
    )

    parts = []
    for k, v in counter.most_common(max_items):
        parts.append(f"{k}×{v}")

    if len(counter) > max_items:
        parts.append("...")

    return ", ".join(parts)


# ------------------------------------------------------------
# Build 3D boxes from container rows
# ------------------------------------------------------------

def build_boxes_from_row_blocks(container_rows, container_width_cm):
    """
    Convert row-blocks into 3D boxes compatible with plot_boxes_3d().
    """
    boxes = []

    for i, r in enumerate(container_rows):
        boxes.append({
            "id": i + 1,
            "x": 0,  # full width blocks start at x=0
            "y": r["y_start_cm"],
            "z": 0,
            "w": container_width_cm,
            "l": r["length_cm"],
            "h": r["height_cm"],
            "block_type": r["block_type"],
            "components": summarize_pallets(r["pallets"]),
        })

    return boxes


# ------------------------------------------------------------
# Main 3D plotting function (refactored from your original)
# ------------------------------------------------------------

def plot_boxes_3d(W, L, H, boxes, title=None):
    fig = plt.figure(figsize=(12, 7))
    ax = fig.add_subplot(111, projection="3d")

    ax.set_xlim(0, W)
    ax.set_ylim(0, L)
    ax.set_zlim(0, H)
    ax.set_box_aspect((W, L, H))

    colors = [
        "tab:blue", "tab:orange", "tab:green",
        "tab:red", "tab:purple", "tab:brown",
        "tab:pink", "tab:gray", "tab:olive", "tab:cyan"
    ]

    for i, b in enumerate(boxes):
        ax.bar3d(
            b["x"], b["y"], b["z"],
            b["w"], b["l"], b["h"],
            alpha=0.55,
            color=colors[i % len(colors)],
            edgecolor="k",
            linewidth=0.6,
            shade=True,
        )

        cx = b["x"] + b["w"] / 2
        cy = b["y"] + b["l"] / 2
        cz = b["z"] + b["h"] / 2

        ax.text(cx, cy, cz, str(b["id"]), color="k", fontsize=9, ha="center")

    ax.set_xlabel("X — container width (cm)")
    ax.set_ylabel("Y — container length (cm)")
    ax.set_zlabel("Z — height (cm)")

    if title:
        ax.set_title(title, fontsize=14, pad=12)

    # ---------------- Legend text ----------------
    legend_lines = []
    for b in boxes:
        line = (
            f"{b['id']:>2}: {b['block_type']} | "
            f"L={b['l']} H={b['h']} | "
            f"{b['components']}"
        )
        legend_lines.append(line)

    fig.text(
        0.02,
        0.02,
        "\n".join(legend_lines),
        fontsize=9,
        family="monospace",
        va="bottom",
        ha="left",
    )
    # ------------------------------------------------

    plt.tight_layout()
    plt.show()


# ------------------------------------------------------------
# Public API — what you actually call
# ------------------------------------------------------------

def plot_row_block_container(container_info, W, L, H):
    """
    Plot a single container solution (one figure).
    """
    boxes = build_boxes_from_row_blocks(container_info["rows"], W)
    title = f"Container {container_info['container_index']} — Row-Block Layout"
    plot_boxes_3d(W, L, H, boxes, title=title)


def plot_all_row_block_containers(containers, W, L, H):
    """
    Plot all containers, one figure per container.
    """
    for c in containers:
        plot_row_block_container(c, W, L, H)