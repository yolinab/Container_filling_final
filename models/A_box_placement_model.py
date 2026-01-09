from cpmpy import *
from cpmpy import any as cpm_any


class BoxPlacementModel:
    """
    Subset + placement model (single container), discretized in X/Y.

    Key rules enforced:
    - load[p] ∈ {0,1} decides whether pallet p is used in this container
    - All geometry constraints are conditional on load
    - No-levitation support: loaded pallets must be on floor or supported by a loaded pallet
    - Same-footprint stacking ONLY (Lp==Lq and Wp==Wq if p sits on q)
    - Row uniformity:
        Rows are along the X axis (short side),
        so "same row" means same (ix, z).
        If two loaded pallets share (ix, z), they must have identical (L,W).
    """

    def __init__(self, lengths, widths, heights, W, L, H, BUF,
                 step_x=10, step_y=10,
                 unload_limit=None,
                 min_loaded_volume=None):

        self.lengths = list(lengths)  # along container length (Y)
        self.widths  = list(widths)   # along container width  (X)
        self.heights = list(heights)  # height (Z)

        self.W = int(W)
        self.L = int(L)
        self.H = int(H)
        self.BUF = int(BUF)

        self.num_boxes = len(self.lengths)
        assert self.num_boxes == len(self.widths) == len(self.heights)

        self.STEP_X = int(step_x)
        self.STEP_Y = int(step_y)

        self.NX = self.W // self.STEP_X
        self.NY = self.L // self.STEP_Y

        self.unload_limit = unload_limit
        self.min_loaded_volume = min_loaded_volume

        self._create_variables()
        self._create_constraints()
        self._create_objective()

    # ------------------------------
    # Convenience: physical coords
    # ------------------------------
    def _x_cm(self, p):
        return self.ix[p] * self.STEP_X

    def _y_cm(self, p):
        return self.iy[p] * self.STEP_Y

    # ------------------------------
    # Variables
    # ------------------------------
    def _create_variables(self):
        n = self.num_boxes

        self.load = boolvar(shape=n, name="load")

        self.ix = intvar(0, self.NX, shape=n, name="ix")
        self.iy = intvar(0, self.NY, shape=n, name="iy")

        self.z = intvar(0, self.H, shape=n, name="z")

        self.max_used_height = intvar(0, self.H, name="max_used_height")
        self.max_x_extent    = intvar(0, self.W, name="max_x_extent")
        self.max_y_extent    = intvar(0, self.L, name="max_y_extent")

        self.x_end = intvar(0, self.W, shape=n, name="x_end")
        self.y_end = intvar(0, self.L, shape=n, name="y_end")
        self.z_end = intvar(0, self.H, shape=n, name="z_end")

        self.model = Model()

    # ------------------------------
    # Constraints
    # ------------------------------
    def _create_constraints(self):
        self.model = Model()

        self._add_optional_limits()
        self._add_inside_container_constraints()
        self._add_no_overlap_constraints()
        self._add_no_levitation_constraints()
        self._add_row_uniformity_constraints()      # <-- fixed axis here
        self._add_bounding_box_constraints()
        self._add_symmetry_breaking_constraints()

    def _add_optional_limits(self):
        n = self.num_boxes

        if self.unload_limit is not None:
            self.model += (sum(~self.load[p] for p in range(n)) <= int(self.unload_limit))

        if self.min_loaded_volume is not None:
            vol = [self.lengths[p] * self.widths[p] * self.heights[p] for p in range(n)]
            loaded_vol = sum(self.load[p] * vol[p] for p in range(n))
            self.model += (loaded_vol >= int(self.min_loaded_volume))

    def _add_inside_container_constraints(self):
        for p in range(self.num_boxes):
            Lp, Wp, Hp = self.lengths[p], self.widths[p], self.heights[p]
            xp = self._x_cm(p)
            yp = self._y_cm(p)

            self.model += self.load[p].implies(xp + Wp <= self.W)
            self.model += self.load[p].implies(yp + Lp <= self.L)
            self.model += self.load[p].implies(self.z[p] + Hp <= self.H)

            # If not loaded, pin z to 0 (helps search; harmless)
            self.model += (~self.load[p]).implies(self.z[p] == 0)

    def _add_no_overlap_constraints(self):
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

                both_loaded = self.load[p] & self.load[q]
                self.model += both_loaded.implies(
                    sep_x | sep_x_rev | sep_y | sep_y_rev | sep_z | sep_z_rev
                )

    def _add_no_levitation_constraints(self):
        """
        Support applies only if loaded.
        Supporter must also be loaded.
        AND we enforce same-footprint stacking only.
        """
        n = self.num_boxes

        for p in range(n):
            on_floor = (self.z[p] == 0)
            Lp, Wp = self.lengths[p], self.widths[p]
            xp = self._x_cm(p)
            yp = self._y_cm(p)

            support_terms = []
            for q in range(n):
                if q == p:
                    continue

                Lq, Wq, Hq = self.lengths[q], self.widths[q], self.heights[q]
                xq = self._x_cm(q)
                yq = self._y_cm(q)

                support_pq = (
                    self.load[q] &
                    (self.z[p] == self.z[q] + Hq) &

                    # footprint containment
                    (xp >= xq) &
                    (xp + Wp <= xq + Wq) &
                    (yp >= yq) &
                    (yp + Lp <= yq + Lq) &

                    # SAME FOOTPRINT ONLY
                    (Lp == Lq) &
                    (Wp == Wq)
                )
                support_terms.append(support_pq)

            supported_by_some_loaded_q = cpm_any(support_terms) if support_terms else False
            self.model += self.load[p].implies(on_floor | supported_by_some_loaded_q)

    def _add_row_uniformity_constraints(self):
        """
        Rows are along the X axis (short side).
        So "same row" = same (ix, z).

        Rule:
        If two loaded pallets share the same (ix, z), they must have identical (L,W).
        """
        n = self.num_boxes
        for p in range(n):
            for q in range(p + 1, n):
                both_loaded = self.load[p] & self.load[q]
                same_row = (self.ix[p] == self.ix[q]) & (self.z[p] == self.z[q])

                self.model += (both_loaded & same_row).implies(
                    (self.lengths[p] == self.lengths[q]) &
                    (self.widths[p]  == self.widths[q])
                )

    def _add_bounding_box_constraints(self):
        n = self.num_boxes

        for p in range(n):
            self.model += self.x_end[p] == self.load[p] * (self._x_cm(p) + self.widths[p])
            self.model += self.y_end[p] == self.load[p] * (self._y_cm(p) + self.lengths[p])
            self.model += self.z_end[p] == self.load[p] * (self.z[p] + self.heights[p])

        self.model += (self.max_x_extent == max(self.x_end))
        self.model += (self.max_y_extent == max(self.y_end))
        self.model += (self.max_used_height == max(self.z_end))

    def _add_symmetry_breaking_constraints(self):
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

                # subset symmetry
                self.model += (self.load[p] >= self.load[q])

                # placement symmetry when both loaded
                both = self.load[p] & self.load[q]
                self.model += both.implies(
                    (self.ix[p] < self.ix[q]) |
                    ((self.ix[p] == self.ix[q]) & (self.iy[p] <= self.iy[q]))
                )

    # ------------------------------
    # Objective
    # ------------------------------
    def _create_objective(self):
        """
        Objective priorities (single container):
        1) maximize loaded volume
        2) maximize loaded count (tie-break)
        3) minimize footprint used: max_y then max_x
        4) maximize used height (encourage stacking once footprint is tight)
        5) pull-to-origin tie-break
        """
        n = self.num_boxes
        vol = [self.lengths[p] * self.widths[p] * self.heights[p] for p in range(n)]
        loaded_vol = sum(self.load[p] * vol[p] for p in range(n))
        loaded_cnt = sum(self.load[p] for p in range(n))

        footprint = 1000 * self.max_y_extent + 10 * self.max_x_extent
        used_height = self.max_used_height  # we will MAXIMIZE this after footprint is minimized

        pull = sum(self.load[p] * (100 * self.iy[p] + 10 * self.ix[p]) for p in range(n))

        # Safe weights (big enough to be lexicographic-ish)
        VMAX = sum(vol)
        FOOT_MAX = 1000 * self.L + 10 * self.W
        PULL_MAX = n * (100 * self.NY + 10 * self.NX)

        BIG1 = (FOOT_MAX + self.H + PULL_MAX + 1) * 10
        BIG2 = (FOOT_MAX + self.H + PULL_MAX + 1)

        self.model.minimize(
            (-BIG1 * loaded_vol) +            # 1) max volume
            (-BIG2 * loaded_cnt) +            # 2) max count
            (footprint * 100) +               # 3) min footprint
            (-used_height * 1) +              # 4) max height usage (encourage stacking)
            (pull * 1)                        # 5) tie-break: reduce holes
        )

        self.loaded_vol_expr = loaded_vol
        self.loaded_cnt_expr = loaded_cnt


    # ------------------------------
    # Solve
    # ------------------------------
    def solve(self, **solver_args):
        return self.model.solve(**solver_args)