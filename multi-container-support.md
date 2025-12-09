# Steps to Achieve Multi-Container Support

## 1. Optimising the Current Placement Model  
### → Reduce Search Space Without Oversimplifying Physical Reality

The existing 3D model uses continuous coordinates, pairwise no-overlap disjunctions, and full freedom in height/width placement.  
This is **far more freedom** than real-world container stacking requires, and it directly leads to solver time exploding.

The goal is to keep pallets **as individual atomic units**, but to **reduce the continuous search space** by switching to a coarse, discrete grid while still enforcing realistic stacking rules.
---

## 1.2 What We *Are* Doing

### ✔ **A discrete 3D grid model using indices instead of coordinates**

Each pallet receives **three discrete indices**:

- `slot[p]` — position along container length (discretised length)
- `col[p]` — which width column it occupies (container width split into 2–4 columns depending on pallet widths)
- `layer[p]` — stacking layer (0,1,… up to max floors allowed, usually 2–3)

This preserves:
- correct individual pallet placement  
- side-by-side layout  
- stacking by footprint  
- realistic container geometry  

While drastically reducing search complexity.

---

## 1.3 Real-World Rules We *Do* Keep

### ✔ Same-footprint stacking
If pallet p is directly above pallet q:
- they must match in width × length footprint  
- q must fully support p  
This matches warehouse practice.

### ✔ Only 2–3 vertical layers are realistic  
Not a hard rule from Niels, but observed in all shipments.  
We enforce layers = {0,1,2} (configurable).

### ✔ Width-based discrete columns  
Instead of continuous 0–235 cm width:
- determine **unique widths present in this order**
- compute 2–4 possible width columns
- place pallets into these discrete columns

This preserves correct adjacency but removes continuous free placement.

### ✔ Length discretised into slots  
Length 1203 cm is split into slots:
- either fixed slot size (e.g., 10–20 cm)
- or dynamically generated from pallet lengths in the order

---

## 1.4 Preprocessing (what actually happens)

We keep pallets **as individuals**, but we preprocess dimensional data:

### ✔ Combine identical pallet dimension types  
If multiple pallets share the same dimensions (e.g., 115×115×100), they share a type entry, but each pallet is still modelled separately.

### ✔ Compute feasible discrete grid units  
From the pallet types present in the order, we compute:
- valid slot sizes for length  
- columns compatible with pallet widths  
- number of vertical layers possible  

### ✔ No merging into rows or pairs  
Stacking constraints remain part of the model.

---

## 1.5 Why the Model Got Slower Recently

The slowdown came from:
- more constraints (e.g., height ordering, support, symmetry, footprint matching)
- more pallets in examples
- full continuous coordinate domain
- z-console becomes tightly constrained by real-world stacking rules → solver has harder time with disjunctions

Switching to discrete `(slot, col, layer)` variables will reduce runtime **by 10×–100×**.

---

# 2. Multi-Container Planning

Goal:
> Decide optimally how to distribute all pallets across as many containers as needed.

### ✔ New binary variable
For each pallet:
- load[p] ∈ {0, 1}

Meaning:
- `1` → pallet is placed in this container  
- `0` → pallet stays for the next iteration  

Procedure:
1. Solve for container 1 (best subset)
2. Remove placed pallets
3. Solve for container 2
4. Repeat

### ✔ Why this works
Each iteration becomes:
- “maximise volume density” or “minimise bounding box waste”
- subject to stacking and discrete placement constraints

This is the most realistic and scalable approach.

---

# 3. Summary of the Final Agreed Model Direction

### ✔ Pallets remain atomic units  
No grouping. No row abstraction.

### ✔ Replace real coordinates with discrete indices:
- `slot[p]` (length)
- `col[p]` (width)
- `layer[p]` (height)

### ✔ Stacking constraints stay:
- full support
- same-footprint stacking

### ✔ Preprocessing:
- dedupe pallet types only
- build discrete grid based on pallet dimensions appearing in the order

### ✔ Multi-container logic:
- `load[p]` binary variable
- run solver iteratively until all pallets allocated

### ✔ Expected effect:
- 30× smaller search space
- predictable solver time
- scalability to 2–5 containers per order
- correct physical packing preserved

---

