"""
Input Parser — Boolean Function Specification
==============================================
Parses a .txt file describing a Boolean function (minterms, don't-cares,
variable names) into a FunctionSpec dataclass.

Supported syntax:
  VARS:       A B C D
  MINTERMS:   0 1 3 5 7 8 10 14 15
  DONT_CARES: 2 6
  OUTPUT:     F          (optional, default = "Z")

Lines starting with '#' are comments.
"""

import re
from dataclasses import dataclass
from typing import List


@dataclass
class FunctionSpec:
    """Parsed Boolean function specification."""
    var_names:   List[str]
    num_vars:    int
    minterms:    List[int]
    dont_cares:  List[int]
    output_name: str

    def validate(self):
        max_minterm = 2 ** self.num_vars - 1
        all_terms   = set(self.minterms) | set(self.dont_cares)
        for t in all_terms:
            if t < 0 or t > max_minterm:
                raise ValueError(
                    f"Term {t} out of range for {self.num_vars} variables "
                    f"(valid: 0–{max_minterm})"
                )
        overlap = set(self.minterms) & set(self.dont_cares)
        if overlap:
            raise ValueError(f"Terms in both MINTERMS and DONT_CARES: {overlap}")
        return self


def parse_file(filepath: str) -> FunctionSpec:
    """Parse a .txt function specification file."""
    fields = {"vars": None, "minterms": [], "dont_cares": [], "output": "Z"}

    with open(filepath) as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip().upper()
            value = value.strip()

            if   key == "VARS":
                fields["vars"] = value.split()
            elif key == "MINTERMS":
                fields["minterms"] = _parse_int_list(value)
            elif key in ("DONT_CARES", "DONTCARES", "DC"):
                fields["dont_cares"] = _parse_int_list(value)
            elif key == "OUTPUT":
                fields["output"] = value.strip()

    if fields["vars"] is None:
        raise ValueError("VARS line is required in the input file.")

    spec = FunctionSpec(
        var_names   = fields["vars"],
        num_vars    = len(fields["vars"]),
        minterms    = fields["minterms"],
        dont_cares  = fields["dont_cares"],
        output_name = fields["output"],
    )
    return spec.validate()


def _parse_int_list(s: str) -> List[int]:
    tokens = re.split(r"[\s,]+", s.strip())
    return [int(t) for t in tokens if t]
