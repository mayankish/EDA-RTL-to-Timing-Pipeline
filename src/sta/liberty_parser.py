"""Liberty File Parser - brace-counting implementation."""
import re
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class PinTiming:
    related_pin: str
    cell_rise: float = 0.0
    cell_fall: float = 0.0

    @property
    def delay(self):
        return max(self.cell_rise, self.cell_fall)


@dataclass
class CellPin:
    direction: str
    is_clock: bool = False
    timings: List[PinTiming] = field(default_factory=list)


@dataclass
class LibCell:
    name: str
    area: float
    pins: Dict[str, CellPin] = field(default_factory=dict)
    FALLBACKS = {"INV":15.0,"NAND2":18.0,"NOR2":20.0,"AND2":25.0,"OR2":28.0,"XOR2":40.0,"DFF":30.0}

    def delay_to(self, out_pin, from_pin):
        if out_pin in self.pins:
            for t in self.pins[out_pin].timings:
                if t.related_pin == from_pin:
                    return t.delay
            if self.pins[out_pin].timings:
                return self.pins[out_pin].timings[0].delay
        return self.FALLBACKS.get(self.name, 20.0)

    def max_delay(self):
        best = 0.0
        for pin in self.pins.values():
            for t in pin.timings:
                best = max(best, t.delay)
        return best if best > 0 else self.FALLBACKS.get(self.name, 20.0)


def _find_blocks(text, keyword, named=True):
    """Brace-counting block extractor. Handles nested braces correctly."""
    pat = re.compile(rf"{keyword}\s*\((\w+)\)\s*\{{") if named \
          else re.compile(rf"{keyword}\s*\(\s*\)\s*\{{")
    results = []
    for m in pat.finditer(text):
        start = m.end() - 1
        depth, end = 0, start
        for i in range(start, len(text)):
            if text[i] == '{': depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0: end = i; break
        body = text[start+1:end]
        results.append((m.group(1), body) if named else body)
    return results


def _gf(text, key):
    m = re.search(rf"{key}\s*[:(]\s*([0-9.]+)", text)
    return float(m.group(1)) if m else 0.0


def _gs(text, key):
    m = re.search(rf'{key}\s*:\s*"?([^";\n{{}}]+)"?', text)
    return m.group(1).strip().strip('"') if m else ""


def parse_lib(filepath):
    """Parse .lib file, return dict of cell_name -> LibCell."""
    with open(filepath) as f:
        text = f.read()
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)

    cells = {}
    for cell_name, cell_body in _find_blocks(text, "cell"):
        cell = LibCell(name=cell_name, area=_gf(cell_body, "area"))
        for pin_name, pin_body in _find_blocks(cell_body, "pin"):
            is_clock = bool(re.search(r"clock\s*:\s*true", pin_body))
            pin = CellPin(direction=_gs(pin_body, "direction"), is_clock=is_clock)
            for tb in _find_blocks(pin_body, "timing", named=False):
                related = _gs(tb, "related_pin").strip('"')
                rise = _gf(tb, "cell_rise") or _gf(tb, "rise_constraint")
                fall = _gf(tb, "cell_fall") or _gf(tb, "fall_constraint")
                if related:
                    pin.timings.append(PinTiming(related_pin=related,
                                                 cell_rise=rise, cell_fall=fall))
            cell.pins[pin_name] = pin
        cells[cell_name] = cell
    return cells


def parse_lib_verbose(filepath):
    """Parse and print a summary."""
    cells = parse_lib(filepath)
    print(f"  Liberty: loaded {len(cells)} cells from {filepath}")
    for n, c in cells.items():
        print(f"    {n:<10}  area={c.area:.1f}  max_delay={c.max_delay():.1f}ps")
    return cells
