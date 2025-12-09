from cpmpy import *
from cpmpy import any as cpm_any


class BoxPlacementModel:
    """
    Simplified 3D pallet placement model.

    - X (width) and Y (length) are discretised into coarse slots.
      We don't work in raw cm any more for positions, only for sizes.
    - No rotations: we use (lengths[p], widths[p]) as given.
    - Constraints kept:
        * inside container
        * no overlap
        * no levitation (support)
        * bounding box + compactness objective
    - Constraints dropped (for speed / simplicity):
        * row_uniformity
        * stack_same_footprint
        * height_ordering
        * rotations
    """

    def __init__(self, lengths, widths, heights, W, L, H, BUF,
                 step_x=10, step_y=10):
        # ---- Input data (sizes always in cm) ----
        self.lengths = list(lengths)  # along container length (Y)
        self.widths  = list(widths)   # along container width  (X)
        self.heights = list(heights)  # height (Z)

        self.W = int(W)   # container width
        self.L = int(L)   # container length
        self.H = int(H)   # container height
        self.BUF = int(BUF)

        self.num_boxes = len(self.lengths)
        assert self.num_boxes == len(self.widths) == len(self.heights)

        # ---- Discretisation steps (in cm) ----
        # Positions can only start at multiples of these.
        self.STEP_X = int(step_x)
        self.STEP_Y = int(step_y)

        # Number of slots along each axis
        self.NX = self.W // self.STEP_X  # index 0..NX
        self.NY = self.L // self.STEP_Y  # index 0..NY

        # Create model, vars, constraints, objective
        self._create_variables()
        self._create_constraints()
        self._create_objective()

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------
    def _create_variables(self):
        n = self.num_boxes

        # Discretised positions: slot indices, not cm
        # Physical coordinate is:
        #   x_cm = ix[p] * STEP_X
        #   y_cm = iy[p] * STEP_Y
        self.ix = intvar(0, self.NX, shape=n, name="ix")  # width slots
        self.iy = intvar(0, self.NY, shape=n, name="iy")  # length slots

        # z still in cm (you *could* also discretise, but not needed yet)
        self.z = intvar(0, self.H, shape=n, name="z")

        # Extents / bounding box over all boxes (in cm)
        self.max_used_height = intvar(0, self.H, name="max_used_height")
        self.max_x_extent    = intvar(0, self.W, name="max_x_extent")
        self.max_y_extent    = intvar(0, self.L, name="max_y_extent")

        # Model object
        self.model = Model()

    # Convenience: physical coordinates in cm (expressions)
    def _x_cm(self, p):
        return self.ix[p] * self.STEP_X

    def _y_cm(self, p):
        return self.iy[p] * self.STEP_Y

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    def _create_constraints(self):
        self.model = Model()
        self._add_inside_container_constraints()
        self._add_no_overlap_constraints()
        self._add_no_levitation_constraints()
        self._add_bounding_box_constraints()
        self._add_symmetry_breaking_constraints()  # still cheap & helpful

    def _add_inside_container_constraints(self):
        """
        Each box must lie fully inside the container.
        Using discretised positions:
          x_cm = ix * STEP_X
          y_cm = iy * STEP_Y
        """
        for p in range(self.num_boxes):
            Lp = self.lengths[p]
            Wp = self.widths[p]
            Hp = self.heights[p]

            self.model += self._x_cm(p) + Wp <= self.W
            self.model += self._y_cm(p) + Lp <= self.L
            self.model += self.z[p] + Hp    <= self.H

    def _add_no_overlap_constraints(self):
        """
        No overlap, with buffer B on X/Y, stacking allowed in Z.

        For any two pallets p, q:
          at least one of these holds:
            - p is strictly to the "right" of q in X
            - q is strictly to the right of p in X
            - p is strictly "in front of" q in Y
            - q is strictly in front of p in Y
            - p is entirely below q in Z
            - q is entirely below p in Z
        """
        n = self.num_boxes
        B = self.BUF

        for p in range(n):
            for q in range(p + 1, n):
                Lp, Wp, Hp = self.lengths[p], self.widths[p], self.heights[p]
                Lq, Wq, Hq = self.lengths[q], self.widths[q], self.heights[q]

                xp = self._x_cm(p)
                xq = self._x_cm(q)
                yp = self._y_cm(p)
                yq = self._y_cm(q)

                sep_x     = xp + Wp + B <= xq
                sep_x_rev = xq + Wq + B <= xp

                sep_y     = yp + Lp + B <= yq
                sep_y_rev = yq + Lq + B <= yp

                sep_z     = self.z[p] + Hp <= self.z[q]
                sep_z_rev = self.z[q] + Hq <= self.z[p]

                self.model += (
                    sep_x |
                    sep_x_rev |
                    sep_y |
                    sep_y_rev |
                    sep_z |
                    sep_z_rev
                )

    def _add_no_levitation_constraints(self):
        """
        No levitation:

        For each pallet p:
          - either z[p] == 0 (sits on the floor), OR
          - there exists q != p such that:
              z[p] = z[q] + h[q]
              and footprint of p is fully inside footprint of q
                (in X and Y, using discretised x_cm, y_cm).
        """
        n = self.num_boxes

        for p in range(n):
            on_floor = (self.z[p] == 0)

            support_exprs = []
            Lp, Wp = self.lengths[p], self.widths[p]

            for q in range(n):
                if q == p:
                    continue

                Lq, Wq, Hq = self.lengths[q], self.widths[q], self.heights[q]

                xp = self._x_cm(p)
                xq = self._x_cm(q)
                yp = self._y_cm(p)
                yq = self._y_cm(q)

                support_pq = (
                    (self.z[p] == self.z[q] + Hq) &
                    (xp >= xq) &
                    (xp + Wp <= xq + Wq) &
                    (yp >= yq) &
                    (yp + Lp <= yq + Lq)
                )
                support_exprs.append(support_pq)

            supported_by_some_q = cpm_any(support_exprs) if support_exprs else False
            self.model += on_floor | supported_by_some_q

    def _add_bounding_box_constraints(self):
        """
        Bounding box in cm:

          max_x_extent    = max_p (x_cm[p] + width[p])
          max_y_extent    = max_p (y_cm[p] + length[p])
          max_used_height = max_p (z[p] + height[p])
        """
        n = self.num_boxes

        self.model += (
            self.max_x_extent ==
            max([self._x_cm(p) + self.widths[p] for p in range(n)])
        )

        self.model += (
            self.max_y_extent ==
            max([self._y_cm(p) + self.lengths[p] for p in range(n)])
        )

        self.model += (
            self.max_used_height ==
            max([self.z[p] + self.heights[p] for p in range(n)])
        )

    def _add_symmetry_breaking_constraints(self):
        """
        Symmetry-breaking: for pallets with identical (L,W,H),
        impose a lexicographic order on (ix, iy) to avoid exploring
        permutations of identical solutions.
        """
        n = self.num_boxes
        for p in range(n):
            for q in range(p + 1, n):
                same_dims = (
                    self.lengths[p] == self.lengths[q] and
                    self.widths[p]  == self.widths[q]  and
                    self.heights[p] == self.heights[q]
                )
                if not same_dims:
                    continue

                # Enforce: (ix[p], iy[p]) <=_lex (ix[q], iy[q])
                self.model += (
                    (self.ix[p] < self.ix[q]) |
                    ((self.ix[p] == self.ix[q]) & (self.iy[p] <= self.iy[q]))
                )

    # ------------------------------------------------------------------
    # Objective
    # ------------------------------------------------------------------
    def _create_objective(self):
        """
        Objective: compact packing.

        Primary: minimise used height, then used length, then used width.
        Secondary: small bias toward clustering near origin (optional).
        """
        n = self.num_boxes

        main_term = (
            1000 * self.max_used_height +
            10   * self.max_y_extent +
            1    * self.max_x_extent
        )

        # weak clustering term (uses indices, not cm)
        spread_term = sum(
            (self.ix[p] + self.iy[p]) * self.heights[p]
            for p in range(n)
        )

        self.model.minimize(main_term * 1000 + spread_term)

    # ------------------------------------------------------------------
    # Solve
    # ------------------------------------------------------------------
    def solve(self, **solver_args):
        """
        Solve the model.
        Returns True if a solution is found.
        """
        return self.model.solve(**solver_args)