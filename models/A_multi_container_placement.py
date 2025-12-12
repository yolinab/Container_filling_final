from cpmpy import *
from cpmpy import any as cpm_any


class MultiContainerPlacementModel:
    """
    Subset + placement model (single container).

    Changes vs your current version:
    - Adds load[p] ∈ {0,1}
    - All geometric constraints are conditional:
        * load[p] -> inside container
        * (load[p] & load[q]) -> no-overlap disjunction
        * load[p] -> (on_floor OR supported_by_some_loaded_q)
    - Bounding box extents ignore unloaded pallets.
    - Objective:
        1) maximize loaded volume
        2) minimize bounding box (height, length, width)
    - Optional speed knobs:
        * unload_limit: restrict how many pallets may be left out
        * identical pallets: enforce load ordering to kill subset symmetries
    """

    def __init__(self, lengths, widths, heights, W, L, H, BUF,
                 step_x=10, step_y=10,
                 unload_limit=None,
                 min_loaded_volume=None):
        # ---- Input data (sizes in cm) ----
        self.lengths = list(lengths)  # along container length (Y)
        self.widths  = list(widths)   # along container width  (X)
        self.heights = list(heights)  # height (Z)

        self.W = int(W)
        self.L = int(L)
        self.H = int(H)
        self.BUF = int(BUF)

        self.num_boxes = len(self.lengths)
        assert self.num_boxes == len(self.widths) == len(self.heights)

        # ---- Discretisation steps (in cm) ----
        self.STEP_X = int(step_x)
        self.STEP_Y = int(step_y)

        self.NX = self.W // self.STEP_X
        self.NY = self.L // self.STEP_Y

        # optional parameters
        self.unload_limit = unload_limit          # e.g. 4
        self.min_loaded_volume = min_loaded_volume # e.g. greedy lower bound (cm^3)

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

        # load decision
        self.load = boolvar(shape=n, name="load")

        # discretised x/y slots
        self.ix = intvar(0, self.NX, shape=n, name="ix")
        self.iy = intvar(0, self.NY, shape=n, name="iy")

        # z in cm
        self.z = intvar(0, self.H, shape=n, name="z")

        # Bounding extents (cm) over LOADED pallets only
        self.max_used_height = intvar(0, self.H, name="max_used_height")
        self.max_x_extent    = intvar(0, self.W, name="max_x_extent")
        self.max_y_extent    = intvar(0, self.L, name="max_y_extent")

        # helper ends (so unloaded pallets contribute 0)
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
        self._add_bounding_box_constraints()
        self._add_symmetry_breaking_constraints()

    def _add_optional_limits(self):
        n = self.num_boxes

        # restrict how many pallets can be left out (huge speed knob)
        if self.unload_limit is not None:
            self.model += (sum(~self.load[p] for p in range(n)) <= int(self.unload_limit))

        # force a minimum loaded volume (another big speed knob)
        if self.min_loaded_volume is not None:
            vol = [self.lengths[p] * self.widths[p] * self.heights[p] for p in range(n)]
            loaded_vol = sum(self.load[p] * vol[p] for p in range(n))
            self.model += (loaded_vol >= int(self.min_loaded_volume))

    def _add_inside_container_constraints(self):
        """
        inside constraints apply only if the pallet is loaded
        """
        for p in range(self.num_boxes):
            Lp, Wp, Hp = self.lengths[p], self.widths[p], self.heights[p]
            xp = self._x_cm(p)
            yp = self._y_cm(p)

            self.model += self.load[p].implies(xp + Wp <= self.W)
            self.model += self.load[p].implies(yp + Lp <= self.L)
            self.model += self.load[p].implies(self.z[p] + Hp <= self.H)

            # optional: if not loaded, pin it somewhere to reduce noise (safe)
            # (doesn't change feasibility, helps search a bit)
            self.model += (~self.load[p]).implies(self.z[p] == 0)

    def _add_no_overlap_constraints(self):
        """
        no-overlap disjunction applies only if BOTH pallets are loaded
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

                both_loaded = self.load[p] & self.load[q]
                self.model += both_loaded.implies(
                    sep_x | sep_x_rev | sep_y | sep_y_rev | sep_z | sep_z_rev
                )

    def _add_no_levitation_constraints(self):
        """
        Support applies only if loaded.
        Supporter must also be loaded.
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
                    self.load[q] &                          # supporter must be loaded
                    (self.z[p] == self.z[q] + Hq) &
                    (xp >= xq) &
                    (xp + Wp <= xq + Wq) &
                    (yp >= yq) &
                    (yp + Lp <= yq + Lq)
                )
                support_terms.append(support_pq)

            supported_by_some_loaded_q = cpm_any(support_terms) if support_terms else False

            # If pallet is loaded, it must be supported (floor or on someone)
            self.model += self.load[p].implies(on_floor | supported_by_some_loaded_q)

    def _add_bounding_box_constraints(self):
        """
        Define x_end/y_end/z_end such that unloaded pallets contribute 0.

          x_end[p] = load[p] * (x_cm[p] + width[p])
          max_x_extent = max(x_end)

        Same for y,z.
        """
        n = self.num_boxes

        for p in range(n):
            self.model += self.x_end[p] == self.load[p] * (self._x_cm(p) + self.widths[p])
            self.model += self.y_end[p] == self.load[p] * (self._y_cm(p) + self.lengths[p])
            self.model += self.z_end[p] == self.load[p] * (self.z[p] + self.heights[p])

        self.model += (self.max_x_extent == max(self.x_end))
        self.model += (self.max_y_extent == max(self.y_end))
        self.model += (self.max_used_height == max(self.z_end))

    def _add_symmetry_breaking_constraints(self):
        """
        Two symmetry breakers:

        (1) identical pallets: enforce load ordering
            if dims equal and p<q: load[p] >= load[q]

        (2) if both loaded and identical dims: lex order on (ix,iy)
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

                # kill subset symmetry
                self.model += (self.load[p] >= self.load[q])

                # kill placement symmetry if both loaded
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
        Lex objective implemented via weights:

        Primary: maximize loaded volume
        Secondary: minimize bounding extents (height, then length, then width)
        Tertiary: weak clustering toward origin (optional)
        """
        n = self.num_boxes
        vol = [self.lengths[p] * self.widths[p] * self.heights[p] for p in range(n)]
        loaded_vol = sum(self.load[p] * vol[p] for p in range(n))

        # compactness term (smaller is better)
        compact = (1000 * self.max_used_height + 10 * self.max_y_extent + 1 * self.max_x_extent)

        # tiny spread term (only breaks ties)
        spread = sum((self.ix[p] + self.iy[p]) * self.heights[p] * self.load[p] for p in range(n))

        # Weighting: choose BIG so volume dominates everything
        BIG = 10**9
        self.model.minimize((-BIG * loaded_vol) + (compact * 1000) + spread)

        # expose for pipeline convenience
        self.loaded_vol_expr = loaded_vol

    # ------------------------------
    # Solve
    # ------------------------------
    def solve(self, **solver_args):
        return self.model.solve(**solver_args)