import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

# --------------------------------------------------
# 1. SET YOUR CONTAINER SIZE (MUST MATCH MINIZINC!)
# --------------------------------------------------
W = 235  # container width  (x)
L = 1203  # container length (y)
H = 270  # container height (z)

# --------------------------------------------------
# 2. PASTE YOUR MINIZINC OUTPUT HERE
#    each line: box_id,x,y,z,len,wid,hgt
# --------------------------------------------------
solution_text = """
0 0 0 0 115 115 88
1 0 0 66 115 115 89
2 0 0 66 115 115 89
3 0 0 0 115 115 66
4 0 0 155 115 115 66
5 0 0 66 115 115 66
6 1 0 0 114 114 230
7 0 0 0 114 114 230
8 1 1 0 114 114 230
9 0 0 0 114 114 230
""".strip()

# --------------------------------------------------
# 3. PARSE THE SOLUTION
# --------------------------------------------------
boxes = []  # list of dicts: {id, x, y, z, l, w, h}

for line in solution_text.splitlines():
    parts = line.strip().split(" ")
    if len(parts) != 7:
        continue
    b_id, x, y, z, l, w, h = map(int, parts)
    boxes.append({
        "id": b_id,
        "x": x,
        "y": y,
        "z": z,
        "l": l,
        "w": w,
        "h": h
    })

# --------------------------------------------------
# 4. PLOT USING bar3d (robust)
# --------------------------------------------------
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')


ax.set_xlim(0, W)
ax.set_ylim(0, L)
ax.set_zlim(0, H)

# 👇 Make the 3D box respect real proportions
ax.set_box_aspect((W, L, H))   # or (W, L, H*something) if you want Z exaggerated



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

# container limits
ax.set_xlim(0, W)
ax.set_ylim(0, L)
ax.set_zlim(0, H)

ax.set_xlabel('X (width)')
ax.set_ylabel('Y (length)')
ax.set_zlabel('Z (height)')
ax.set_title('Box layout in container')

plt.tight_layout()
plt.show()