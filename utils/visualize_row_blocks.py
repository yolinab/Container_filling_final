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
    Robust to key naming style: 'length' vs 'length_cm', etc.
    """
    if not pallets:
        return "empty"

    def _dim(pm, k1, k2):
        return pm.get(k1, pm.get(k2, "?"))

    counter = Counter(
        f"{_dim(p,'length','length_cm')}x{_dim(p,'width','width_cm')}x{_dim(p,'height','height_cm')}"
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
            color=b.get("color", colors[i % len(colors)]),
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
    seen = set()

    for b in boxes:
        legend_id = b.get("legend_id")
        legend_line = b.get("legend_line")
        if legend_id is not None and legend_line is not None:
            if legend_id not in seen:
                legend_lines.append(legend_line)
                seen.add(legend_id)
            continue

        # Fallback: original per-box legend
        line = (
            f"{b.get('id','?'):>2}: {b.get('block_type','')} | "
            f"L={b.get('l','?')} H={b.get('h','?')} | "
            f"{b.get('components','')}"
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


# ------------------------------------------------------------
# NEW: Pallet-level plotting (pallets colored by row-block)
# ------------------------------------------------------------

def build_pallet_boxes_from_row_blocks(container_rows, container_width_cm, gap_cm=5):
    """
    Expand each row-block into individual pallet cuboids.

    - All pallets within the same row-block share the same color.
    - Layout is deterministic and simple:
        * across = 3 if footprint is 77x77 else 2
        * pallets are placed left-to-right across X
        * pallets are stacked in layers along Z
        * all pallets in a row-block share the same Y start (the row start)

    This is a visualisation convenience: it is not a physics re-check.
    """

    palette = [
        "tab:blue", "tab:orange", "tab:green",
        "tab:red", "tab:purple", "tab:brown",
        "tab:pink", "tab:gray", "tab:olive", "tab:cyan"
    ]

    pallet_boxes = []

    for block_idx, r in enumerate(container_rows, start=1):
        pallets = r.get("pallets", [])
        if not pallets:
            continue

        # Row start and row dims
        y0 = int(r.get("y_start_cm", 0))
        row_len = int(r.get("length_cm", 0))
        row_h = int(r.get("height_cm", 0))
        block_type = str(r.get("block_type", ""))

        # Determine pallet footprint from first pallet meta
        p0 = pallets[0]
        Lp = int(p0.get("length", p0.get("length_cm", 0)))
        Wp = int(p0.get("width",  p0.get("width_cm",  0)))

        # Choose orientation so pallet length along Y matches row_len when possible
        if row_len == Lp:
            pallet_len_y, pallet_wid_x = Lp, Wp
        elif row_len == Wp:
            pallet_len_y, pallet_wid_x = Wp, Lp
        else:
            pallet_len_y, pallet_wid_x = Lp, Wp

        # Across heuristic (matches your business assumption)
        across = 3 if (Lp == 77 and Wp == 77) else 2

        # Z step: use tallest pallet height in the block to avoid overlaps
        heights = [int(pm.get("height", pm.get("height_cm", 0))) for pm in pallets]
        z_step = max(heights) if heights else 0

        color = palette[(block_idx - 1) % len(palette)]

        # Block-level legend line (one per block)
        comps = summarize_pallets(pallets)
        legend_line = (
            f"{block_idx:>2}: {block_type} | row L={row_len} H={row_h} | {comps}"
        )

        for i, pm in enumerate(pallets):
            layer = i // across
            pos = i % across

            x = pos * pallet_wid_x
            y = y0
            z = layer * z_step

            h_cm = int(pm.get("height", pm.get("height_cm", 0)))

            pallet_boxes.append({
                "id": i + 1,
                "x": x,
                "y": y,
                "z": z,
                "w": pallet_wid_x,
                "l": pallet_len_y,
                "h": h_cm,
                "color": color,
                # provide grouped legend info
                "legend_id": block_idx,
                "legend_line": legend_line,
            })

    return pallet_boxes


def plot_row_block_container_pallets(container_info, W, L, H, gap_cm=5):
    """Plot a single container showing individual pallets (colored by row-block)."""
    rows = container_info.get("rows", [])
    boxes = build_pallet_boxes_from_row_blocks(rows, W, gap_cm=gap_cm)
    title = f"Container {container_info.get('container_index','')} — Pallet View"
    plot_boxes_3d(W, L, H, boxes, title=title)
    return boxes


def plot_all_row_block_containers_pallets(containers, W, L, H, gap_cm=5):
    """Plot each container showing individual pallets (colored by row-block)."""
    all_boxes = []
    for c in containers:
        all_boxes.append(plot_row_block_container_pallets(c, W, L, H, gap_cm=gap_cm))
    return all_boxes