from cpmpy import *

# Choose how many extra pallets of each type to add, given
# a scalar free floor length (aggregated) and buffer.


class ReccomendFillModel:
    """
    Inputs (per pallet type t):
        lengths[t]  = len[t]  (Y dimension)
        widths[t]   = wid[t]  (X dimension)
        heights[t]  = hgt[t]  (Z dimension)
        max_add[t]  = upper bound on extra pallets of type t

    Global inputs:
        BUF         = buffer between pallets along Y
        free_len    = total free floor length along Y

    Decision:
        add[t]      = number of extra pallets of type t to add

    Objective:
        maximize total_added_volume =
            sum_t add[t] * len[t] * wid[t] * hgt[t]
    """

    def __init__(self, lengths, widths, heights, BUF, free_len, max_add):
        # ---- Input data ----
        self.lengths = [int(x) for x in lengths]
        self.widths  = [int(x) for x in widths]
        self.heights = [int(x) for x in heights]
        self.max_add = [int(x) for x in max_add]

        self.BUF      = int(BUF)
        self.free_len = int(free_len)

        self.T = len(self.lengths)
        assert self.T == len(self.widths) == len(self.heights) == len(self.max_add)

        # Model will be built here
        self.model = Model()

        self._create_variables()
        self._create_constraints()
        self._create_objective()

    # ------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------
    def _create_variables(self):
        """
        add[t] in [0, max(max_add)]
        We still constrain add[t] <= max_add[t] per type in constraints.
        """
        ub = max(self.max_add) if self.max_add else 0
        self.add = intvar(0, ub, shape=self.T, name="add")

    # ------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------
    def _create_constraints(self):
        self._add_bounds_constraints()
        self._add_capacity_constraint()

    def _add_bounds_constraints(self):
        """0 <= add[t] <= max_add[t] for each type t."""
        for t in range(self.T):
            self.model += (self.add[t] >= 0)
            self.model += (self.add[t] <= self.max_add[t])

    def _add_capacity_constraint(self):
        """
        Sum over types:
            add[t] * (len[t] + BUF) <= free_len
        """
        total_len_used = sum(
            self.add[t] * (self.lengths[t] + self.BUF)
            for t in range(self.T)
        )
        self.model += (total_len_used <= self.free_len)

    # ------------------------------------------------------------
    # Objective
    # ------------------------------------------------------------
    def _create_objective(self):
        """
        total_added_volume =
            sum_t add[t] * len[t] * wid[t] * hgt[t]

        We maximize this.
        """
        self.total_added_volume = sum(
            self.add[t] * self.lengths[t] * self.widths[t] * self.heights[t]
            for t in range(self.T)
        )

        self.model.maximize(self.total_added_volume)

    # ------------------------------------------------------------
    # Solve helper
    # ------------------------------------------------------------
    def solve(self, **solver_args):
        """
        Solve the model.
        Returns True if a solution is found, False otherwise.
        """
        return self.model.solve(**solver_args)

    def get_solution_add(self):
        """
        Return the chosen add[t] as a Python list (if solved).
        """
        return [self.add[t].value() for t in range(self.T)]