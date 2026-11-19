# Copyright (C) 2026 Admix Pty. Ltd. - All Rights Reserved.
# Unauthorized copying of this file, via any medium is strictly prohibited.
# Proprietary and confidential.

"""The system models of the systems-engineering skill: the product tree, requirements, assumptions,
interfaces, blocks and check results of one task, written as `systems.json` and `systems.html`.

A script imports this file, and `systems_page.py`, from its own folder. Both use only the standard
library, so the script runs with `python3` or as a golf script. Every quantity carries its unit as
text; `convert` changes between the units in `UNITS`.
"""

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1

SOURCES = ("stated", "implied", "assumed")
METHODS = ("measure", "calculate", "simulate", "inspect", "outside")
LIMITS = ("max", "min", "equal", None)
TASKS = ("new_design", "change_review", "optimization", "problem_solving", "other")
MODELS = ("nodes", "requirements", "assumptions", "interfaces", "blocks")
# What the evidence of a simulated result must say.
SIMULATION_EVIDENCE = ("tool", "leaves_out")

# Densities in g/cm^3, for mass from a part's volume.
DENSITY = {
    "Al6060": 2.70,
    "Al6061": 2.70,
    "Al7075": 2.81,
    "Steel": 7.85,
    "Stainless304": 8.00,
    "Ti6Al4V": 4.43,
    "Brass": 8.50,
    "ABS": 1.04,
    "PLA": 1.24,
    "PETG": 1.27,
    "Nylon66": 1.14,
}

# Each unit's kind of quantity and its size in that kind's first unit. Temperatures are not here:
# their scales differ by an offset, so a temperature is checked in the requirement's own unit.
UNITS = {
    kind_unit: (kind, size)
    for kind, units in {
        "length": {"mm": 1, "um": 1e-3, "cm": 10, "m": 1000, "in": 25.4, "ft": 304.8},
        "area": {"mm^2": 1, "cm^2": 100, "m^2": 1e6, "in^2": 645.16},
        "volume": {"mm^3": 1, "cm^3": 1e3, "mL": 1e3, "L": 1e6, "m^3": 1e9, "in^3": 16387.064},
        "mass": {"kg": 1, "mg": 1e-6, "g": 1e-3, "t": 1000, "lb": 0.45359237, "oz": 0.028349523125},
        "force": {"N": 1, "kN": 1e3, "kgf": 9.80665, "lbf": 4.4482216152605},
        "pressure": {"MPa": 1, "Pa": 1e-6, "kPa": 1e-3, "GPa": 1e3, "bar": 0.1, "psi": 0.006894757293168},
        "torque": {"N*m": 1, "N*mm": 1e-3, "lbf*in": 0.1129848290276, "lbf*ft": 1.3558179483314},
        "time": {"s": 1, "ms": 1e-3, "min": 60, "h": 3600},
        "angle": {"deg": 1, "rad": 180 / math.pi},
        "frequency": {"Hz": 1, "kHz": 1e3, "rpm": 1 / 60},
        "speed": {"m/s": 1, "mm/s": 1e-3, "km/h": 1 / 3.6},
        "power": {"W": 1, "mW": 1e-3, "kW": 1e3},
        "energy": {"J": 1, "kJ": 1e3, "W*h": 3600},
    }.items()
    for kind_unit, size in units.items()
}


def convert(value, unit, to):
    """`value` in `unit`, in the unit `to`. Raises where the two are not the same text and not two
    units of one kind in `UNITS`."""
    if unit == to:
        return value
    if unit not in UNITS or to not in UNITS or UNITS[unit][0] != UNITS[to][0]:
        raise ValueError(f"cannot convert {unit!r} to {to!r}: give the value in {to!r}")
    return value * UNITS[unit][1] / UNITS[to][1]


def mass_kg(volume_mm3, material):
    """The mass of `volume_mm3` of a material in `DENSITY`."""
    return volume_mm3 * DENSITY[material] * 1e-6


@dataclass
class Node:
    """One item of the product tree. A leaf is a part; `shows` are the names it has in golf's
    `show`, or in whatever else draws it."""

    id: str
    name: str
    parent: str | None = None
    shows: list = field(default_factory=list)
    quantity: int = 1
    material: str | None = None
    mass_kg: float | None = None
    cost: float | None = None
    bought: bool = False
    extra: dict = field(default_factory=dict)


@dataclass
class Requirement:
    """`applies_to`: the ids of the nodes or interfaces it is about. `source`: who it came from.
    `method`: how it is verified; `outside` is one that the model cannot verify. `limit` with `kind`
    makes it a number that `check` compares, in `unit`."""

    id: str
    text: str
    applies_to: list
    source: str = "stated"
    method: str = "measure"
    kind: str | None = None
    limit: float | None = None
    unit: str = ""
    tolerance: float = 0.0
    extra: dict = field(default_factory=dict)


@dataclass
class Assumption:
    """A value or fact the user did not give. `affects` lists the ids that depend on it."""

    id: str
    text: str
    reason: str
    affects: list = field(default_factory=list)
    confirmed: bool = False
    extra: dict = field(default_factory=dict)


@dataclass
class Interface:
    """Where two nodes meet, or a node and something outside the product (`b="external:wall"`).
    `keeps` says what a change must not alter."""

    id: str
    a: str
    b: str
    kind: str
    text: str
    keeps: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class Port:
    name: str
    quantity: str
    unit: str = ""


@dataclass
class Block:
    """What a node does, as inputs and outputs. `relation` says how the outputs follow from the
    inputs, in words or as a formula; empty for a block that is not modelled inside."""

    node: str
    inputs: list = field(default_factory=list)
    outputs: list = field(default_factory=list)
    relation: str = ""
    runs: bool = False
    extra: dict = field(default_factory=dict)


@dataclass
class Result:
    """One check of a requirement, in one case. `measured` is in the requirement's unit."""

    case: str
    status: str
    measured: float | None = None
    margin: float | None = None
    note: str = ""
    evidence: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)


class Model:
    """The models of one task. Add items, call `check` for each requirement the script can verify,
    then `write`."""

    def __init__(self, name, task="other", **task_details):
        if task not in TASKS:
            raise ValueError(f"task is one of {TASKS}, not {task!r}")
        self.name = name
        self.task = {"kind": task, **task_details}
        self.nodes = {}
        self.requirements = {}
        self.assumptions = {}
        self.interfaces = {}
        self.blocks = {}
        self.results = {}
        self.skipped = {}
        self.simulations = []
        self._functions = {}
        self._tests = {}

    def _add(self, items, item, key=None):
        key = key or item.id
        if key in items:
            raise ValueError(f"{key!r} is defined twice")
        items[key] = item
        return item

    def node(self, id, name, parent=None, **fields):
        return self._add(self.nodes, Node(id, name, parent, **fields))

    def requirement(self, id, text, applies_to, **fields):
        """`applies_to` is the id of a node or an interface, or a list of them."""
        ids = [applies_to] if isinstance(applies_to, str) else list(applies_to)
        r = Requirement(id, text, ids, **fields)
        if r.source not in SOURCES or r.method not in METHODS or r.kind not in LIMITS:
            raise ValueError(f"{id}: source, method or kind is not one this file knows")
        if (r.kind is None) != (r.limit is None):
            raise ValueError(f"{id}: give kind and limit together")
        return self._add(self.requirements, r)

    def assumption(self, id, text, reason, **fields):
        return self._add(self.assumptions, Assumption(id, text, reason, **fields))

    def interface(self, id, a, b, kind, text, **fields):
        return self._add(self.interfaces, Interface(id, a, b, kind, text, **fields))

    def block(self, node, inputs=(), outputs=(), relation="", function=None, **fields):
        """`function`, where given, takes the inputs by name and returns the outputs as a dict by
        name; `simulate` calls it."""
        ports = [[Port(*p) if not isinstance(p, Port) else p for p in side] for side in (inputs, outputs)]
        block = Block(node, *ports, relation, runs=function is not None, **fields)
        self._add(self.blocks, block, key=node)
        if function is not None:
            self._functions[node] = function
        return block

    def skip(self, model, reason):
        """Records why one of `MODELS` has nothing in it for this task."""
        if model not in MODELS:
            raise ValueError(f"model is one of {MODELS}, not {model!r}")
        self.skipped[model] = reason

    def simulate(self, node, **inputs):
        """Runs a block's function on values for its inputs, records the run, and returns its
        outputs by name. A block's function may call `simulate` for the blocks of the nodes below
        it."""
        block = self.blocks[node]
        if node not in self._functions:
            raise ValueError(f"the block of {node} has no function")
        expected = {p.name for p in block.inputs}
        if set(inputs) != expected:
            raise ValueError(f"the block of {node} takes {sorted(expected)}, not {sorted(inputs)}")
        outputs = self._functions[node](**inputs)
        absent = [p.name for p in block.outputs if p.name not in outputs]
        if absent:
            raise ValueError(f"the function of {node} did not return {absent}")
        self.simulations.append({"block": node, "inputs": inputs, "outputs": dict(outputs)})
        return outputs

    def check(self, id, measured=None, unit=None, *, passed=None, case="", note="", evidence=None, extra=None):
        """Records one result of a requirement and returns it; it never raises for a failure.

        With a limit, give `measured` and its `unit`, which is converted to the requirement's; a
        unit that cannot be is an error. Without a limit, give `passed` and a `note` of what was
        compared. Check a requirement that
        holds in several positions, loads or modes once for each, with a `case` name: the worst case
        gives the requirement's status. `evidence` says where the value came from: `tool`, `inputs`,
        `files`, `accuracy`, `leaves_out`, and any other key. A `simulate` requirement needs `tool`
        and `leaves_out`."""
        r = self.requirements[id]
        cases = self.results.setdefault(id, {})
        if case in cases:
            raise ValueError(f"{id} is checked twice: give each check its own case=")
        evidence = dict(evidence or {})
        if r.method == "simulate" and any(not evidence.get(k) for k in SIMULATION_EVIDENCE):
            raise ValueError(f"{id} is simulated: its evidence needs {SIMULATION_EVIDENCE}")
        margin = None
        if r.kind is not None:
            if measured is None or unit is None:
                raise ValueError(f"{id} has a limit in {r.unit!r}: give the measured value and its unit")
            measured = convert(measured, unit, r.unit)
            margin = {
                "max": r.limit - measured,
                "min": measured - r.limit,
                "equal": r.tolerance - abs(measured - r.limit),
            }[r.kind]
            passed = margin >= 0
        elif passed is None or not note:
            raise ValueError(f"{id} has no limit: give passed=True or False, and a note of what was compared")
        status = "pass" if passed else "fail"
        cases[case] = Result(case, status, measured, margin, note, evidence, dict(extra or {}))
        return cases[case]

    def test(self, id, unit=None, evidence=None):
        """Makes the function below it a test of a requirement. Write it with the requirement, before
        the design.

        `run` calls the function with the design and checks what it returns: a number in `unit` (the
        requirement's own where not given), True or False for a requirement with no limit, or a dict
        of either by case name. A test that raises, as it does while the design is not there yet, or
        returns nothing, is recorded as failed with the reason. `evidence` is as for `check`."""
        if id not in self.requirements:
            raise ValueError(f"nothing has the id {id!r}: define the requirement before its test")

        def register(function):
            self._tests.setdefault(id, []).append((function, unit, evidence))
            return function

        return register

    def run(self, design=None, path="systems.json", baseline=None):
        """Runs every test on `design`, whatever the tests expect (a dict of parts and values is
        usual; an empty one before there is a design), then writes the files as `write` does."""
        for id, tests in self._tests.items():
            r = self.requirements[id]
            for function, unit, evidence in tests:
                name = function.__name__
                only = "" if len(tests) == 1 else name
                try:
                    value = function(design)
                except Exception as error:
                    self._failed(id, only, f"test could not run: {type(error).__name__}: {error}")
                    continue
                for case, one in (value if isinstance(value, dict) else {only: value}).items():
                    if one is None:
                        self._failed(id, case, "test returned no value")
                    elif r.kind is None:
                        note = (function.__doc__ or name).strip()
                        self.check(id, passed=bool(one), case=case, note=note, evidence=evidence)
                    else:
                        self.check(id, one, r.unit if unit is None else unit, case=case, evidence=evidence)
        self.write(path, baseline)

    def _failed(self, id, case, note):
        """Records a test that gave no value as a failed case."""
        self.results.setdefault(id, {})[case] = Result(case, "fail", note=note)

    def children(self, id):
        return [n for n in self.nodes.values() if n.parent == id]

    def total(self, id, attribute):
        """The sum of `attribute` (`mass_kg` or `cost`) over the parts under a node, each times its
        quantity and those of the nodes above it, and the ids of the parts that have no value."""
        node, children = self.nodes[id], self.children(id)
        if not children:
            value = getattr(node, attribute)
            return (0.0, [id]) if value is None else (value * node.quantity, [])
        total, missing = 0.0, []
        for child in children:
            value, absent = self.total(child.id, attribute)
            total += value
            missing += absent
        return total * node.quantity, missing

    def problems(self):
        """References to ids that are not defined, and models left empty without a reason."""
        found = []

        def known(owner, id, items):
            if id not in items and not id.startswith("external:"):
                found.append(f"{owner}: nothing has the id {id!r}")

        for n in self.nodes.values():
            if n.parent is not None:
                known(n.id, n.parent, self.nodes)
        for r in self.requirements.values():
            for id in r.applies_to:
                known(r.id, id, self.nodes | self.interfaces)
        for i in self.interfaces.values():
            known(i.id, i.a, self.nodes)
            known(i.id, i.b, self.nodes)
        for b in self.blocks.values():
            known(f"block {b.node}", b.node, self.nodes)
        everything = self.nodes | self.requirements | self.assumptions | self.interfaces
        for a in self.assumptions.values():
            for id in a.affects:
                known(a.id, id, everything)
        for model in MODELS:
            if not getattr(self, model) and model not in self.skipped:
                found.append(f"{model}: empty; add items or skip({model!r}, reason)")
        for r in self.requirements.values():
            if r.method != "outside" and r.id not in self._tests and r.id not in self.results:
                found.append(f"{r.id}: no test; write one with @m.test({r.id!r}) before the design")
        return found

    def result(self, id):
        """A requirement's result: its worst case, with every case under `cases`. With no check,
        an `outside` one is `cannot_verify` and any other `not_verified`."""
        r = self.requirements[id]
        cases = list(self.results.get(id, {}).values())
        if not cases:
            status = "cannot_verify" if r.method == "outside" else "not_verified"
            return {"requirement": id, **asdict(Result("", status)), "cases": []}
        worst = min(cases, key=lambda c: (c.status == "pass", math.inf if c.margin is None else c.margin))
        return {"requirement": id, **asdict(worst), "cases": [asdict(c) for c in cases]}

    def to_dict(self, baseline=None):
        """Everything as JSON values. With `baseline`, an earlier `to_dict`, each result that the
        baseline also has gets `before` (its status, value and margin then) and `regressed`: it
        passed then and fails now."""

        def rows(items):
            return [asdict(i) for i in items.values()]

        totals = {}
        for node in self.nodes.values():
            if self.children(node.id):
                mass, no_mass = self.total(node.id, "mass_kg")
                cost, no_cost = self.total(node.id, "cost")
                totals[node.id] = {"mass_kg": mass, "no_mass": no_mass, "cost": cost, "no_cost": no_cost}
        results = [self.result(id) for id in self.requirements]
        before = {r["requirement"]: r for r in (baseline or {}).get("results", [])}
        for result in results:
            if result["requirement"] in before:
                old = before[result["requirement"]]
                result["before"] = {k: old[k] for k in ("status", "measured", "margin")}
                result["regressed"] = old["status"] == "pass" and result["status"] == "fail"
        return {
            "schema": SCHEMA_VERSION,
            "name": self.name,
            "written": time.strftime("%Y-%m-%d %H:%M:%S"),
            "task": self.task,
            "nodes": rows(self.nodes),
            "requirements": rows(self.requirements),
            "assumptions": rows(self.assumptions),
            "interfaces": rows(self.interfaces),
            "blocks": rows(self.blocks),
            "skipped": self.skipped,
            "totals": totals,
            "results": results,
            "simulations": self.simulations,
            "problems": self.problems(),
        }

    def summary(self, data=None):
        """The results of a `to_dict` as lines of text, then the assumptions the user has not
        confirmed."""
        data = data or self.to_dict()
        lines = []
        for result in data["results"]:
            r = self.requirements[result["requirement"]]
            numbers = ""
            if result["measured"] is not None:
                numbers = f"  {result['measured']:g} {r.unit} (limit {r.limit:g}, margin {result['margin']:g})"
            elif result["status"] == "fail" and result["note"]:
                numbers = f"  ({result['note']})"
            if len(result["cases"]) > 1:
                numbers += f"  worst of {len(result['cases'])} cases: {result['case']}"
            tool = f"  [{result['evidence']['tool']}]" if result["evidence"].get("tool") else ""
            if result.get("before", {}).get("margin") is not None:
                tool += f"  margin before: {result['before']['margin']:g}"
            if result.get("regressed"):
                tool += "  PASSED BEFORE"
            lines.append(f"{result['status']:13} {r.id:8} {r.text}{numbers}{tool}")
        for a in self.assumptions.values():
            if not a.confirmed:
                lines.append(f"{'assumed':13} {a.id:8} {a.text}")
        return "\n".join(lines + data["problems"])

    def write(self, path="systems.json", baseline=None):
        """Writes the models and results to `path`, the page for the user beside it as `.html`, and
        prints the summary.

        `baseline` names a file of the results to compare with. Where it is not there yet, this run
        is written to it; later runs give each result its value in that file. Remove the file to
        start again."""
        from systems_page import page

        earlier = None
        if baseline is not None and Path(baseline).exists():
            earlier = json.loads(Path(baseline).read_text())
        data = json.loads(json.dumps(self.to_dict(earlier), default=str))
        Path(path).write_text(json.dumps(data, indent=2))
        Path(path).with_suffix(".html").write_text(page(data))
        print(self.summary(data))
        if baseline is not None and earlier is None:
            Path(baseline).write_text(json.dumps(data, indent=2))
            print(f"baseline written to {baseline}")
        elif earlier is not None:
            print(f"compared with {baseline}, written {earlier.get('written', 'at an unknown time')}")
