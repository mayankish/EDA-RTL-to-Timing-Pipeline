"""
Quine-McCluskey Boolean Minimization
======================================
Finds the minimum SOP expression for a Boolean function.
This is the core algorithm inside Synopsys Design Compiler's logic optimization.
"""


class Implicant:
    """A product term (a cube in Boolean space)."""

    def __init__(self, minterms: set, value: int, mask: int):
        self.minterms = frozenset(minterms)
        self.value = value   # Fixed bit values
        self.mask  = mask    # 1 = don't-care bit (from merging)

    def __eq__(self, other):
        return self.value == other.value and self.mask == other.mask

    def __hash__(self):
        return hash((self.value, self.mask))

    def can_combine(self, other):
        """Two implicants combine iff masks equal and values differ by exactly 1 bit."""
        if self.mask != other.mask:
            return False, 0
        diff = self.value ^ other.value
        if diff and not (diff & (diff - 1)):   # power-of-2 → exactly 1 bit
            return True, diff
        return False, 0

    def to_sop_term(self, num_vars: int, var_names: list) -> str:
        literals = []
        for i in range(num_vars - 1, -1, -1):
            bit  = 1 << i
            name = var_names[num_vars - 1 - i]
            if   self.mask  & bit: continue
            elif self.value & bit: literals.append(name)
            else:                  literals.append(f"~{name}")
        return ".".join(literals) if literals else "1"


def minimize(minterms: list, dont_cares: list, num_vars: int) -> list:
    """
    Quine-McCluskey minimization.
    Returns list of Implicant objects forming a minimum SOP cover.
    """
    minterm_set = frozenset(minterms)
    all_terms   = minterm_set | frozenset(dont_cares)

    if not minterm_set:
        return []

    current: set = {Implicant({m}, m, 0) for m in all_terms}
    prime_implicants: set = set()

    while current:
        next_round: set = set()
        used: set       = set()
        impl_list = list(current)

        for i in range(len(impl_list)):
            for j in range(i + 1, len(impl_list)):
                a, b = impl_list[i], impl_list[j]
                can, diff_bit = a.can_combine(b)
                if can:
                    merged = Implicant(
                        a.minterms | b.minterms,
                        a.value & ~diff_bit,
                        a.mask  |  diff_bit,
                    )
                    next_round.add(merged)
                    used.add(a)
                    used.add(b)

        for impl in current:
            if impl not in used:
                prime_implicants.add(impl)
        current = next_round

    pis = [pi for pi in prime_implicants if pi.minterms & minterm_set]
    return _select_minimum_cover(pis, minterm_set)


def _select_minimum_cover(prime_implicants: list, minterms: frozenset) -> list:
    coverage = {m: [] for m in minterms}
    for pi in prime_implicants:
        for m in pi.minterms & minterms:
            coverage[m].append(pi)

    selected = []
    covered  = set()

    # Pass 1 — Essential PIs (only one PI covers the minterm)
    for m, pis in coverage.items():
        if len(pis) == 1:
            pi = pis[0]
            if pi not in selected:
                selected.append(pi)
                covered |= pi.minterms & minterms

    # Pass 2 — Greedy cover for remaining minterms
    remaining = set(minterms) - covered
    while remaining:
        best = max(prime_implicants, key=lambda pi: len(pi.minterms & remaining))
        new_cov = best.minterms & remaining
        if not new_cov:
            break
        selected.append(best)
        covered  |= new_cov
        remaining -= new_cov

    return selected
