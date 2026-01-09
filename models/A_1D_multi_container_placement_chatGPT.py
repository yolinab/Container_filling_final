from cpmpy import *
from cpmpy.expressions.globalconstraints import Element


class RowBlock1DOrderModel:
    """
    1D Row-Block Subset + Placement Model (single container)
    using ORDER-BASED space encoding.

    - Decision is a sequence of row slots: slot[r] ∈ {0..N}
        slot[r]=i means row-block instance i is placed at row position r (back -> door).
        slot[r]=0 means empty (unused).
      Contiguity ensures all used rows form a prefix.

    - Subset selection is implicit: blocks not appearing in slot[] are "left out"
      for the next container in your outer loop.

    Hard constraints:
      * length feasibility: sum row lengths + g*(rowsUsed-1) <= L
      * payload limit: sum row weights <= Wmax
      * hard height ordering: row heights non-increasing back->door
      * door height limit: last used row height <= Hdoor

    Optional speed knobs:
      * unload_limit: N - rowsUsed <= unload_limit
      * min_loaded_value: loadedValue >= min_loaded_value

    Objective:
      maximize BIG*loadedValue + usedLen
      (lex-like: loadedValue dominates, usedLen tie-break)
    """

    def __init__(self,
                 lengths_cm, heights_cm, weights_kg, values,
                 L_cm=1203, gap_cm=5, Wmax_kg=18000, Hdoor_cm=250,
                 Rmax=None,
                 unload_limit=None,
                 min_loaded_value=None):
        # ---------- Store input ----------
        self.L = int(L_cm)
        self.g = int(gap_cm)
        self.Wmax = int(Wmax_kg)
        self.Hdoor = int(Hdoor_cm)

        self.len_in = [int(x) for x in lengths_cm]
        self.h_in   = [int(x) for x in heights_cm]
        self.w_in   = [int(x) for x in weights_kg]
        self.val_in = [int(x) for x in values]

        self.N = len(self.len_in)
        assert self.N == len(self.h_in) == len(self.w_in) == len(self.val_in)

        # Safe 0-indexed arrays so slot=0 is valid and contributes 0
        self.len0 = [0] + self.len_in
        self.h0   = [0] + self.h_in
        self.w0   = [0] + self.w_in
        self.val0 = [0] + self.val_in

        # Choose a safe Rmax if not provided
        if Rmax is None:
            min_len = min(self.len_in) if self.N > 0 else self.L
            # upper bound on number of rows that can fit (used rows form prefix)
            Rmax = (self.L + self.g) // (min_len + self.g) if (min_len + self.g) > 0 else self.N
            Rmax = max(1, min(Rmax, self.N))  # never exceed N, at least 1
        self.Rmax = int(Rmax)

        self.unload_limit = unload_limit
        self.min_loaded_value = min_loaded_value

        # ---------- Build model ----------
        self._create_variables()
        self._create_constraints()
        self._create_objective()

    # ------------------------------
    # Variables
    # ------------------------------
    def _create_variables(self):
        N = self.N
        R = self.Rmax

        # slot[r] in 0..N (0 = empty, i = choose block instance i)
        self.slot = intvar(0, N, shape=R, name="slot")

        # convenient bools
        self.used = boolvar(shape=R, name="used")      # used[r] <-> slot[r] != 0

        # how many rows used
        self.rowsUsed = intvar(0, R, name="rowsUsed")

        # gap count = max(0, rowsUsed-1)
        self.gapCount = intvar(0, R, name="gapCount")

        # aggregates
        self.usedLen = intvar(0, self.L, name="usedLen")
        self.loadedWeight = intvar(0, self.Wmax, name="loadedWeight")  # bounded
        # loadedValue upper bound: sum of all values
        self.loadedValue = intvar(0, sum(self.val_in), name="loadedValue")

        # load[i] like your old model (for pipeline extraction)
        self.load = boolvar(shape=N, name="load")

        self.model = Model()

    # ------------------------------
    # Constraints
    # ------------------------------
    def _create_constraints(self):
        m = self.model
        N = self.N
        R = self.Rmax
        g = self.g

        # (C0) used[r] <-> slot[r] != 0
        for r in range(R):
            m += (self.used[r] == (self.slot[r] != 0))

        # (C1) contiguity: once empty, always empty
        for r in range(R - 1):
            m += (self.slot[r] == 0).implies(self.slot[r + 1] == 0)

        # (C2) no duplicate nonzero slots (each block used at most once)
        for r in range(R):
            for s in range(r + 1, R):
                m += ((self.slot[r] != 0) & (self.slot[s] != 0)).implies(self.slot[r] != self.slot[s])

        # (C3) rowsUsed = sum used[r]
        m += (self.rowsUsed == sum(self.used[r] for r in range(R)))

        # (C4) gapCount = max(0, rowsUsed-1)
        # Implement robustly with reification:
        m += (self.rowsUsed == 0).implies(self.gapCount == 0)
        m += (self.rowsUsed > 0).implies(self.gapCount == self.rowsUsed - 1)

        # (C5) usedLen = sum len(slot[r]) + g*gapCount, length limit
        len_terms = [Element(self.len0, self.slot[r]) for r in range(R)]
        m += (self.usedLen == sum(len_terms) + g * self.gapCount)
        m += (self.usedLen <= self.L)

        # (C6) weight constraint
        weight_terms = [Element(self.w0, self.slot[r]) for r in range(R)]
        m += (self.loadedWeight == sum(weight_terms))
        m += (self.loadedWeight <= self.Wmax)

        # (C7) loaded value
        value_terms = [Element(self.val0, self.slot[r]) for r in range(R)]
        m += (self.loadedValue == sum(value_terms))

        # (C8) hard height ordering back -> door
        # Because h0[0]=0 and empties must be at end, this works cleanly.
        for r in range(R - 1):
            m += (Element(self.h0, self.slot[r]) >= Element(self.h0, self.slot[r + 1]))

        # (C9) door row height constraint on LAST USED row
        # Using implications on "r is last used":
        # last used row r satisfies: slot[r]!=0 and (r==R-1 or slot[r+1]==0)
        for r in range(R):
            is_used = (self.slot[r] != 0)
            is_last = is_used & ((r == R - 1) | (self.slot[r + 1] == 0) if r < R - 1 else True)
            # If r is last used row, enforce height <= Hdoor
            m += is_last.implies(Element(self.h0, self.slot[r]) <= self.Hdoor)

        # (C10) load[i] <-> i appears in some slot
        for i in range(1, N + 1):
            m += (self.load[i - 1] == any(self.slot[r] == i for r in range(R)))

        # (Optional) unload_limit: N - rowsUsed <= unload_limit
        if self.unload_limit is not None:
            m += (N - self.rowsUsed <= int(self.unload_limit))

        # (Optional) min_loaded_value
        if self.min_loaded_value is not None:
            m += (self.loadedValue >= int(self.min_loaded_value))

    # ------------------------------
    # Objective
    # ------------------------------
    def _create_objective(self):
        # Lex-like maximize loadedValue, then maximize usedLen
        BIG = 10**6
        self.model.maximize(BIG * self.loadedValue + self.usedLen)

    # ------------------------------
    # Solve
    # ------------------------------
    def solve(self, **solver_args):
        return self.model.solve(**solver_args)

    # ------------------------------
    # Helpers for pipeline
    # ------------------------------
    def loaded_indices_in_order(self):
        """Return block instance indices in back->door order (1..N), excluding 0."""
        return [int(self.slot[r].value()) for r in range(self.Rmax) if int(self.slot[r].value()) != 0]

    def unloaded_indices(self):
        """Return block indices (1..N) not loaded."""
        loaded_set = set(self.loaded_indices_in_order())
        return [i for i in range(1, self.N + 1) if i not in loaded_set]

    def compute_y_starts(self):
        """
        Deterministically reconstruct y-start positions from the slot order.
        Returns list of (block_index, y_start_cm).
        """
        order = self.loaded_indices_in_order()
        y = 0
        out = []
        for idx in order:
            out.append((idx, y))
            y += self.len0[idx] + self.g
        return out