import subprocess
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
MODEL_PATH = "/Users/yolina/Desktop/Container-filling_v1/Base_model_min_vol.mzn"      # your MiniZinc model file
DATA_PATH  = "/Users/yolina/Desktop/Container-filling_v1/instance_from_excel.dzn"   # the dzn with pallet/container data

# container dims must match the dzn
W = 235   # width  (x)
L = 1203  # length (y)
H = 270   # height (z)
BUF = 5   # buffer between pallets

# --------------------------------------------------
# 1. RUN MINIZINC AND CAPTURE SOLUTION
# --------------------------------------------------
def run_minizinc(model_path, data_path):
    """
    Runs MiniZinc model+data and returns stdout as text.
    Requires `minizinc` CLI on PATH.
    """
    result = subprocess.run(
        [
            "minizinc",
            "--solver", "chuffed",
            model_path,
            data_path
        ],
        capture_output=True,
        text=True,
        check=True
    )
    
    return result.stdout

# --------------------------------------------------
# 2. PARSE SOLUTION TEXT (CSV LINES)
#    format: p,x,y,z,eff_len,eff_wid,hgt
# --------------------------------------------------
def parse_solution(solution_text):
    boxes = []
    for line in solution_text.splitlines():
        line = line.strip()
        if not line or line.startswith("%"):
            continue
        parts = line.split(",")
        if len(parts) != 7:
            continue
        b_id, x, y, z, eff_len, eff_wid, hgt = map(int, parts)
        boxes.append({
            "id": b_id,
            "x": x,
            "y": y,
            "z": z,
            "l": eff_len,  # length  (Y direction)
            "w": eff_wid,  # width   (X direction)
            "h": hgt       # height  (Z direction)
        })
    return boxes


# --------------------------------------------------
# 3. CALCULATE USED UP VOLUME FROM CHOSEN PALLET ARRANGEMENT - AND DRWAW BOUNDING BOX
# --------------------------------------------------

def compute_volumes(boxes, W, L, H):
    # min and max extents of the actual pallets
    min_x = min(b["x"] for b in boxes)
    min_y = min(b["y"] for b in boxes)
    min_z = min(b["z"] for b in boxes)

    max_x = max(b["x"] + b["w"] for b in boxes)
    max_y = max(b["y"] + b["l"] for b in boxes)
    max_z = max(b["z"] + b["h"] for b in boxes)

    used_box_width  = max_x - min_x
    used_box_length = max_y - min_y
    used_box_height = max_z - min_z

    used_stack_volume = used_box_width * used_box_length * used_box_height
    container_volume  = W * L * H

    pallet_volume = sum(b["l"] * b["w"] * b["h"] for b in boxes)
    unused_container_volume = container_volume - used_stack_volume

    return {
        "min_x": min_x,
        "min_y": min_y,
        "min_z": min_z,
        "max_x": max_x,
        "max_y": max_y,
        "max_z": max_z,
        "used_stack_volume": used_stack_volume,
        "pallet_volume": pallet_volume,
        "container_volume": container_volume,
        "unused_container_volume": unused_container_volume,
        "packing_density": pallet_volume / used_stack_volume if used_stack_volume > 0 else 0
    }

def draw_box(ax, x0, y0, z0, x1, y1, z1, color="k", linestyle="-", linewidth=1.0, alpha=1.0):
    """
    Draws a wireframe box from (x0,y0,z0) to (x1,y1,z1).
    """
    # 8 corners
    xs = [x0, x1]
    ys = [y0, y1]
    zs = [z0, z1]

    # bottom rectangle
    ax.plot([xs[0], xs[1]], [ys[0], ys[0]], [zs[0], zs[0]], color=color, linestyle=linestyle, linewidth=linewidth, alpha=alpha)
    ax.plot([xs[1], xs[1]], [ys[0], ys[1]], [zs[0], zs[0]], color=color, linestyle=linestyle, linewidth=linewidth, alpha=alpha)
    ax.plot([xs[1], xs[0]], [ys[1], ys[1]], [zs[0], zs[0]], color=color, linestyle=linestyle, linewidth=linewidth, alpha=alpha)
    ax.plot([xs[0], xs[0]], [ys[1], ys[0]], [zs[0], zs[0]], color=color, linestyle=linestyle, linewidth=linewidth, alpha=alpha)

    # top rectangle
    ax.plot([xs[0], xs[1]], [ys[0], ys[0]], [zs[1], zs[1]], color=color, linestyle=linestyle, linewidth=linewidth, alpha=alpha)
    ax.plot([xs[1], xs[1]], [ys[0], ys[1]], [zs[1], zs[1]], color=color, linestyle=linestyle, linewidth=linewidth, alpha=alpha)
    ax.plot([xs[1], xs[0]], [ys[1], ys[1]], [zs[1], zs[1]], color=color, linestyle=linestyle, linewidth=linewidth, alpha=alpha)
    ax.plot([xs[0], xs[0]], [ys[1], ys[0]], [zs[1], zs[1]], color=color, linestyle=linestyle, linewidth=linewidth, alpha=alpha)

    # vertical edges
    ax.plot([xs[0], xs[0]], [ys[0], ys[0]], [zs[0], zs[1]], color=color, linestyle=linestyle, linewidth=linewidth, alpha=alpha)
    ax.plot([xs[1], xs[1]], [ys[0], ys[0]], [zs[0], zs[1]], color=color, linestyle=linestyle, linewidth=linewidth, alpha=alpha)
    ax.plot([xs[1], xs[1]], [ys[1], ys[1]], [zs[0], zs[1]], color=color, linestyle=linestyle, linewidth=linewidth, alpha=alpha)
    ax.plot([xs[0], xs[0]], [ys[1], ys[1]], [zs[0], zs[1]], color=color, linestyle=linestyle, linewidth=linewidth, alpha=alpha)

# --------------------------------------------------
# 4. CALCULATE FREE FLOOR SEGMENTS
# --------------------------------------------------

def find_free_floor_segments(boxes, L):
    """
    Return free floor segments along Y: list of (y_start, y_end),
    based only on pallets with z == 0.
    """
    floor_boxes = [b for b in boxes if b["z"] == 0]
    if not floor_boxes:
        return [(0, L)]

    min_y = min(b["y"] for b in floor_boxes)
    max_y = max(b["y"] + b["l"] for b in floor_boxes)

    segments = []
    if min_y > 0:
        segments.append((0, min_y))
    if max_y < L:
        segments.append((max_y, L))

    return segments


# --------------------------------------------------
# 5. VISUALISE IN 3D
# --------------------------------------------------
def plot_layout(boxes, W, L, H, stats, title="Container layout"):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")

    # container limits
    ax.set_xlim(0, W)
    ax.set_ylim(0, L)
    ax.set_zlim(0, H)
    ax.set_box_aspect((W, L, H))

    colors = ['tab:blue', 'tab:orange', 'tab:green',
              'tab:red', 'tab:purple', 'tab:brown',
              'tab:pink', 'tab:gray', 'tab:olive', 'tab:cyan']

    # draw pallets
    for i, b in enumerate(boxes):
        ax.bar3d(
            b["x"], b["y"], b["z"],
            b["w"],  # X
            b["l"],  # Y
            b["h"],  # Z
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

        # --- NEW: draw container boundary (full container)
    draw_box(ax, 0, 0, 0, W, L, H,
             color="black", linestyle="--", linewidth=1.0, alpha=0.6)

    # --- NEW: draw used bounding box (tight hull around pallets)
    min_x = stats["min_x"]
    min_y = stats["min_y"]
    min_z = stats["min_z"]
    max_x = stats["max_x"]
    max_y = stats["max_y"]
    max_z = stats["max_z"]

    draw_box(ax, min_x, min_y, min_z,
             max_x, max_y, max_z,
             color="red", linestyle="-", linewidth=2.0, alpha=0.9)

    ax.set_xlabel("X (width)")
    ax.set_ylabel("Y (length)")
    ax.set_zlabel("Z (height)")

    ax.set_title(f"{title}\nUsed vs container volume")

    plt.tight_layout()
    plt.show()

# --------------------------------------------------
# 6. MAIN WORKFLOW
# --------------------------------------------------

def run_container_packing(data_path=DATA_PATH, title="Container layout", do_plot=True):
    sol_text = run_minizinc(MODEL_PATH, data_path)
    boxes = parse_solution(sol_text)
    volumes = compute_volumes(boxes, W, L, H)
    plot_layout(boxes, W, L, H, volumes)
    if do_plot:
        plot_layout(boxes, W, L, H, volumes, title=title)

    return boxes, volumes


if __name__ == "__main__":
    run_container_packing()