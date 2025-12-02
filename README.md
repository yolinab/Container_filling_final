# Container Filling (CPMpy)

This project loads pallet data from an Excel file, builds a 3D pallet-placement model using CPMpy, and visualizes the final layout in a 3D plot.

## What the model does
The solver places all pallets inside a container while enforcing:

- **Rotation**  
  Pallets may rotate (swap length/width).

- **Inside-container**  
  Each pallet must fully fit within the container boundaries.

- **No-overlap**  
  Any two pallets must be separated in **X** or **Y** (with buffer), or stacked in **Z**.

- **No-levitation**  
  A pallet must either lie on the floor or be fully supported by another pallet below it.

- **Bounding box**  
  Tracks the maximum used height and footprint extents.

- **Objective**  
  Minimize:  
  `1000 * max_used_height + max_y_extent + max_x_extent`

## How to run
```bash
python main.py