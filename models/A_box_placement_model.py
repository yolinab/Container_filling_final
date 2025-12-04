from cpmpy import *
from cpmpy import any as cpm_any


class BoxPlacementModel:

    def __init__(self, lengths, widths, heights, W, L, H, BUF):
        # Input data
        self.lengths = list(lengths)
        self.widths  = list(widths)
        self.heights = list(heights)
        self.W = int(W)
        self.L = int(L)
        self.H = int(H)
        self.BUF = int(BUF)

        self.num_boxes = len(self.lengths)
        assert self.num_boxes == len(self.widths) == len(self.heights)

        # Create model, vars, constraints, objective
        self._create_variables()
        self._create_constraints()
        self._create_objective()

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------
    def _create_variables(self):
        n = self.num_boxes

        # Decision Variables: positions
        self.x = intvar(0, self.W, shape=n, name="x")  # x-position
        self.y = intvar(0, self.L, shape=n, name="y")  # y-position
        self.z = intvar(0, self.H, shape=n, name="z")  # z-position

        # Rotation: 0 = normal, 1 = swapped
        self.rot = boolvar(shape=n, name="rot")

        # Effective dimensions after rotation
        max_len_or_wid = max(max(self.lengths), max(self.widths))
        self.eff_len = intvar(0, max_len_or_wid, shape=n, name="eff_len")
        self.eff_wid = intvar(0, max_len_or_wid, shape=n, name="eff_wid")

        # Extents / bounding box over all boxes
        self.max_used_height = intvar(0, self.H, name="max_used_height")
        self.max_x_extent    = intvar(0, self.W, name="max_x_extent")
        self.max_y_extent    = intvar(0, self.L, name="max_y_extent")

        # Optional clustering metric (not used in objective now)
        self.cluster_score = sum(self.x[i] + self.y[i] for i in range(n))

        # The model object
        self.model = Model()

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    def _create_constraints(self):
        self.model = Model()
        self._add_rotation_constraints()
        self._add_inside_container_constraints()
        self._add_no_overlap_constraints()
        self._add_no_levitation_constraints()
        self._add_bounding_box_constraints()
        self._add_symmetry_breaking_constraints()
        self._add_row_uniformity_constraints()
        self._add_stack_same_footprint_constraints()
        self._add_height_ordering_constraints()
        # self._add_height_ordering_constraints()

    def _add_rotation_constraints(self):
        """Rotation: if rot[p]=0 -> (eff_len=len, eff_wid=wid),
                     if rot[p]=1 -> (eff_len=wid, eff_wid=len)"""
        for p in range(self.num_boxes):
            Lp = self.lengths[p]
            Wp = self.widths[p]

            # rot[p] == 0
            self.model += (~self.rot[p]).implies(self.eff_len[p] == Lp)
            self.model += (~self.rot[p]).implies(self.eff_wid[p] == Wp)

            # rot[p] == 1
            self.model += ( self.rot[p]).implies(self.eff_len[p] == Wp)
            self.model += ( self.rot[p]).implies(self.eff_wid[p] == Lp)

    def _add_inside_container_constraints(self):
        """Each box must lie fully inside the container."""
        for p in range(self.num_boxes):
            Hp = self.heights[p]
            self.model += self.x[p] + self.eff_wid[p] <= self.W
            self.model += self.y[p] + self.eff_len[p] <= self.L
            self.model += self.z[p] + Hp              <= self.H

    def _add_no_overlap_constraints(self):
        """
        No overlap with buffer on x,y.
        Allow stacking in z (no buffer in z), via disjunction:
          - strictly apart in x OR
          - strictly apart in y OR
          - non-overlapping in z (stacked).
        """
        n = self.num_boxes
        B = self.BUF

        for p in range(n):
            for q in range(p + 1, n):
                Hp = self.heights[p]
                Hq = self.heights[q]

                # Disjunction: at least one must hold
                sep_x = self.x[p] + self.eff_wid[p] + B <= self.x[q]
                sep_x_rev = self.x[q] + self.eff_wid[q] + B <= self.x[p]

                sep_y = self.y[p] + self.eff_len[p] + B <= self.y[q]
                sep_y_rev = self.y[q] + self.eff_len[q] + B <= self.y[p]

                sep_z = self.z[p] + Hp <= self.z[q]
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
          For each box p:
            - either it sits on the floor (z[p] == 0), OR
            - it is supported by some other box q (q != p) such that
                z[p] = z[q] + h[q]
                and the footprint of p is within footprint of q.
        """
        n = self.num_boxes

        for p in range(n):
            # p sits on the floor:
            on_floor = (self.z[p] == 0)

            # OR p is supported by some q != p
            support_exprs = []
            for q in range(n):
                if q == p:
                    continue

                Hq = self.heights[q]

                # is_supported_by(p,q)
                support_pq = (
                    (self.z[p] == self.z[q] + Hq) &
                    (self.x[p] >= self.x[q]) &
                    (self.x[p] + self.eff_wid[p] <= self.x[q] + self.eff_wid[q]) &
                    (self.y[p] >= self.y[q]) &
                    (self.y[p] + self.eff_len[p] <= self.y[q] + self.eff_len[q])
                )
                support_exprs.append(support_pq)

            supported_by_some_q = cpm_any(support_exprs) if support_exprs else False

            self.model += on_floor | supported_by_some_q

    def _add_bounding_box_constraints(self):
        """
        Bounding rectangle of all stacked boxes together:
          max_x_extent = max_p (x[p] + eff_wid[p])
          max_y_extent = max_p (y[p] + eff_len[p])
          max_used_height = max_p (z[p] + hgt[p])
        """
        n = self.num_boxes

        self.model += (
            self.max_x_extent ==
            max([self.x[p] + self.eff_wid[p] for p in range(n)])
        )

        self.model += (
            self.max_y_extent ==
            max([self.y[p] + self.eff_len[p] for p in range(n)])
        )

        self.model += (
            self.max_used_height ==
            max([self.z[p] + self.heights[p] for p in range(n)])
        )

    def _add_symmetry_breaking_constraints(self):
        """
        Symmetry-breaking: for boxes with identical dimensions,
        impose an ordering on (x,y) to avoid exploring permutations
        of identical solutions.
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

                # Enforce: box p is "not after" box q in (x,y) lexicographically
                # x[p] < x[q] OR (x[p] == x[q] AND y[p] <= y[q])
                self.model += (
                    (self.x[p] < self.x[q]) |
                    ((self.x[p] == self.x[q]) & (self.y[p] <= self.y[q]))
                )
    
    def _add_row_uniformity_constraints(self):
        """
        Rows are defined left-to-right:
          - same row => same y and same z (same level, same front-back position)
        Each row must contain pallets with the same (length x width).
        """
        n = self.num_boxes
        for p in range(n):
            for q in range(p + 1, n):
                # p and q are in the same row if they are on the same level and
                # have the same y-position (front-back coordinate)
                same_row = (self.z[p] == self.z[q]) & (self.y[p] == self.y[q])

                # If in the same row, their effective length/width must match
                self.model += same_row.implies(
                    (self.eff_len[p] == self.eff_len[q]) &
                    (self.eff_wid[p] == self.eff_wid[q])
                )

    def _add_stack_same_footprint_constraints(self):
        """
        If a pallet p is stacked on a pallet q (same support condition
        as in _add_no_levitation_constraints), then p and q must have
        the same effective (length x width).
        """
        n = self.num_boxes

        for p in range(n):
            for q in range(n):
                if p == q:
                    continue

                Hq = self.heights[q]

                stacked_on_q = (
                    (self.z[p] == self.z[q] + Hq) &
                    (self.x[p] >= self.x[q]) &
                    (self.x[p] + self.eff_wid[p] <= self.x[q] + self.eff_wid[q]) &
                    (self.y[p] >= self.y[q]) &
                    (self.y[p] + self.eff_len[p] <= self.y[q] + self.eff_len[q])
                )

                # If p is stacked on q, they must have identical footprint size
                self.model += stacked_on_q.implies(
                    (self.eff_len[p] == self.eff_len[q]) &
                    (self.eff_wid[p] == self.eff_wid[q])
                )

    def _add_height_ordering_constraints(self):
        """
        Heuristic ordering:
        - Among pallets on the floor (z == 0),
          taller pallets should not be placed in front of shorter ones.
        - Formally: if heights[p] > heights[q] and both are on the floor,
          then y[p] >= y[q] (p is at least as far back as q).
        """
        n = self.num_boxes
        for p in range(n):
            for q in range(n):
                if p == q:
                    continue

                # Heights are constants, so check this in Python:
                if self.heights[p] > self.heights[q]:
                    # If both on floor, enforce y[p] >= y[q]
                    self.model += (
                        ((self.z[p] == 0) & (self.z[q] == 0))
                    ).implies(self.y[p] >= self.y[q])

    def _add_height_ordering_constraints(self):
        """
        Heuristic ordering:
        For floor pallets with the same footprint (eff_len, eff_wid),
        taller ones must be placed at least as far back (y) as shorter ones.
        """
        n = self.num_boxes
        for p in range(n):
            for q in range(n):
                if p == q:
                    continue

                if self.heights[p] <= self.heights[q]:
                    continue

                # condition: both on floor and same footprint
                same_footprint_floor = (
                    (self.z[p] == 0) &
                    (self.z[q] == 0) &
                    (self.eff_len[p] == self.eff_len[q]) &
                    (self.eff_wid[p] == self.eff_wid[q])
                )

                self.model += same_footprint_floor.implies(self.y[p] >= self.y[q])
    # ------------------------------------------------------------------
    # Objective
    # ------------------------------------------------------------------
    # def _create_objective(self):
        # """
        # Objective: minimize
        #    1000 * max_used_height + max_y_extent + max_x_extent
        # (cluster_score is defined but not used, as in your MiniZinc model).
        # """
        # obj = 1000 * self.max_used_height + self.max_y_extent + self.max_x_extent
        # self.model.minimize(obj)
        
    # def _create_objective(self):
    #     """
    #     Objective: primarily minimise used length (max_y_extent),
    #         secondarily avoid unnecessary stack height.
    # """
    #     # Big weight on used length, small on height
    #     obj = 1000 * self.max_y_extent + self.max_used_height
    #     self.model.minimize(obj)

    
    def _create_objective(self):
        n = self.num_boxes

        # main: compact bounding box
        main_term = 1000 * self.max_used_height + self.max_y_extent + self.max_x_extent

        # secondary: penalise distance from origin, weighted by height or area
        spread_term = sum(
            (self.x[p] + self.y[p]) * self.heights[p]   # or * (self.lengths[p]*self.widths[p])
            for p in range(n)
        )

        # small weight so it only breaks ties, doesn’t ruin compactness
        self.model.minimize(main_term * 1000 + spread_term)

    # ------------------------------------------------------------------
    # Solve
    # ------------------------------------------------------------------
    def solve(self, **solver_args):
        """
        Solve the model.
        Returns True if a solution is found, False otherwise.
        """
        return self.model.solve(**solver_args)