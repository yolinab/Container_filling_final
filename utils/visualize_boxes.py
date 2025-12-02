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