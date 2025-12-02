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
    # ------------------------------------------------------------------
    # Objective
    # ------------------------------------------------------------------
    def _create_objective(self):
        """
        Objective: minimize
           1000 * max_used_height + max_y_extent + max_x_extent
        (cluster_score is defined but not used, as in your MiniZinc model).
        """
        obj = 1000 * self.max_used_height + self.max_y_extent + self.max_x_extent
        self.model.minimize(obj)

    # ------------------------------------------------------------------
    # Solve
    # ------------------------------------------------------------------
    def solve(self, **solver_args):
        """
        Solve the model.
        Returns True if a solution is found, False otherwise.
        """
        return self.model.solve(**solver_args)