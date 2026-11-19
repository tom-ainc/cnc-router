# Copyright (C) 2026 Admix Pty. Ltd. - All Rights Reserved.
# Unauthorized copying of this file, via any medium is strictly prohibited.
# Proprietary and confidential.

"""Short calls for writing the system models and tests inside the design's own script.

    from se import *
    product("Rain tank on a stand", task="new_design")
    outside("hose", "G1/2 outlet", keeps="thread and height")
    assume("The hose needs the outlet 300 mm up", why="no height was given")
    ...build the design...
    require("R1", "The tank shall hold at least 50 L", volume_mm3, ">=", 50, "L", measured_in="mm^3")
    report()

`report` runs last: it prints one line for each requirement, writes `systems.html`, and says
whether the work is done.
"""

from systems import DENSITY, Model, convert, mass_kg  # noqa: F401

__all__ = [
    "assume",
    "cannot_check",
    "confirm",
    "fragile",
    "model",
    "validate",
    "flow",
    "mass_kg",
    "meets",
    "outside",
    "part",
    "product",
    "report",
    "require",
    "require_clear_travel",
    "require_held",
    "require_no_overlap",
    "require_one_solid",
    "require_true",
]

_model = None
_count = {"I": 0, "A": 0}
_KINDS = {"<": "max", "<=": "max", ">": "min", ">=": "min", "==": "equal"}


def _m():
    if _model is None:
        raise RuntimeError("call product(name, task=...) first")
    return _model


def _next(letter):
    _count[letter] += 1
    return f"{letter}{_count[letter]}"


def product(name, task="other", **details):
    """Starts the models: the whole product is the part `P`. `task` is new_design, change_review,
    optimization, problem_solving or other; other details (symptom=, objective=, change=) go by name."""
    global _model
    _model = Model(name, task=task, **details)
    _count.update(I=0, A=0)
    _model.node("P", name)
    return _model


def part(id, name, of="P", **fields):
    """A part of the product: `material=`, `mass_kg=`, `quantity=`, `shows=[names in show()]`."""
    return _m().node(id, name, parent=of, **fields)


def outside(name, how, keeps="", of="P", kind="mechanical"):
    """Something outside the product that it touches, joins, moves past or feeds."""
    return _m().interface(_next("I"), of, f"external:{name}", kind, how, keeps=keeps)


def meets(a, b, how, keeps="", kind="mechanical"):
    """Where two parts of the product meet."""
    return _m().interface(_next("I"), a, b, kind, how, keeps=keeps)


def flow(inputs, outputs, of="P", how=""):
    """What goes into a part and what comes out, as names: flow(["load, N"], ["reaction, N"])."""
    ports = [
        [tuple(part.strip() for part in item.split(",", 1)) + ("",) * (2 - len(item.split(",", 1))) for item in side]
        for side in (inputs, outputs)
    ]
    return _m().block(
        of, inputs=[(p[0], p[0], p[1]) for p in ports[0]], outputs=[(p[0], p[0], p[1]) for p in ports[1]], relation=how
    )


def assume(text, why, affects=()):
    """A value or fact the user did not give."""
    return _m().assumption(_next("A"), text, why, affects=list(affects))


def require(
    id,
    text,
    value,
    op,
    limit,
    unit="",
    measured_in=None,
    case="",
    of="P",
    source="stated",
    tolerance=0.0,
    evidence=None,
    depends=(),
):
    """A requirement with a number, and its measured value: require("R1", "...", mass, "<=", 60, "g").

    `source` says who set it: "stated" (the user, a drawing, a standard), "implied" (follows from what the thing is
    for), or "assumed" (a limit the agent chose). Only stated ones count as right until the user confirms them.
    `depends` lists the assumptions and models (see `model`) its check rests on.

    `value` comes from the design; None means it is not built yet, which fails. Call it again with
    `case=` for each position, load or mode. `evidence={"tool": ..., "leaves_out": ...}` says how a
    computed value was got."""
    m = _m()
    if id not in m.requirements:
        method = "simulate" if evidence else "measure"
        m.requirement(
            id, text, of, kind=_KINDS[op], limit=limit, unit=unit, source=source, tolerance=tolerance, method=method,
            depends=list(depends),
        )
    else:
        r = m.requirements[id]
        r.depends += [d for d in depends if d not in r.depends]
    if value is None:
        m._failed(id, case, "no value yet: the design does not give one")
    else:
        m.check(id, value, measured_in or unit, case=case, evidence=evidence)


def require_true(id, text, passed, note, of="P", source="stated"):
    """A requirement with no number: `passed` is computed from the design, `note` says what was compared."""
    m = _m()
    if id not in m.requirements:
        m.requirement(id, text, of, method="inspect", source=source)
    m.check(id, passed=bool(passed), note=note)


def cannot_check(id, text, why, of="P", source="stated"):
    """A requirement the model cannot show, such as a load test or a finish."""
    m = _m()
    m.requirement(id, text, of, method="outside", source=source, extra={"why": why})


def confirm(*ids):
    """The user has confirmed these requirements (as right) or assumptions (as true)."""
    m = _m()
    for id in ids:
        item = m.requirements.get(id) or m.assumptions.get(id)
        if item is None:
            raise ValueError(f"nothing has the id {id!r}")
        item.confirmed = True


def model(id, text, checked_by=()):
    """A model checks rest on (`depends=[id]`): checked only when its own tests against known answers
    (`checked_by`, requirement ids) all pass. model("sim", "time-domain simulation", checked_by=["R80", "R81"])."""
    return _m().model(id, text, checked_by)


def fragile(id, why):
    """The check passes, but would fail if `why` (from a sensitivity sweep: "friction is doubled")."""
    r = _m().requirements[id]
    if why not in r.fragile:
        r.fragile.append(why)


def validate(id, measured, unit="", how="", date="", case=""):
    """A test or measurement of the real thing: validate("R3", 302, "mm", "dial gauge over the Z stroke", "2026-12-01").
    Only this makes a requirement VALIDATED; one that fails makes it FAILS IN TEST, whatever the model says."""
    return _m().validation(id, measured, unit, how, date, case)


def _shared(a, b):
    """The volume two solids share, in mm^3."""
    return float((a & b).volume())


def require_one_solid(id, solid, text="The part shall be one solid"):
    """A part made of pieces must be joined into one: checks its number of solids."""
    require(id, text, solid.num_solids(), "==", 1)


def require_no_overlap(id, solids, text="No two parts shall overlap", allow=()):
    """Checks every pair of the named solids: `require_no_overlap("R2", {"motor": motor, "cover": cover})`.
    `allow` lists pairs that are meant to share volume, as ("a", "b")."""
    names = list(solids)
    allowed = {frozenset(pair) for pair in allow}
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if frozenset((a, b)) not in allowed:
                require(id, text, _shared(solids[a], solids[b]), "<=", 0, "mm^3", case=f"{a} and {b}")


def require_held(id, holder, held, free=(), step=20.0, text="The held thing shall fit and shall not come out"):
    """Checks that `held` (a solid in its place) fits in `holder` and cannot leave it.

    In place the two must not overlap. Pushed `step` mm along +x, -x, +y, -y, +z and -z, the held
    solid must run into the holder. `free` names the directions it may leave by, such as ("+x",)."""
    from golf_py import Location

    require(id, text, _shared(holder, held), "<=", 0, "mm^3", case="in place")
    for name, move in (
        ("+x", (1, 0, 0)),
        ("-x", (-1, 0, 0)),
        ("+y", (0, 1, 0)),
        ("-y", (0, -1, 0)),
        ("+z", (0, 0, 1)),
        ("-z", (0, 0, -1)),
    ):
        if name in free:
            continue
        pushed = held.moved(Location.translation(*(step * d for d in move)))
        m = _m()
        stop_id = id + "-stops"
        if stop_id not in m.requirements:
            m.requirement(
                stop_id,
                f"{text}: pushed {step:g} mm it shall meet the holder",
                "P",
                kind="min",
                limit=1,
                unit="mm^3",
                source="implied",
            )
        m.check(stop_id, _shared(holder, pushed), "mm^3", case=f"pushed {name}")


def require_clear_travel(
    id, moving, fixed, place, steps=11, text="The moving part shall not overlap anything over its travel"
):
    """Checks a moving solid against each fixed one at `steps` places along its travel.

    `fixed` is {"name": solid}; `place(t)` gives the Location of the moving solid for t from 0 to 1,
    measured from where `moving` is now: `place=lambda t: Location.translation(t * 80, 0, 0)`."""
    for i in range(steps):
        there = moving.moved(place(i / (steps - 1)))
        for name, other in fixed.items():
            require(id, text, _shared(there, other), "<=", 0, "mm^3", case=f"{name}, step {i} of {steps - 1}")


def report(baseline=None):
    """Prints the results, writes the page, and says how far they go. Call it last.

    The last line is never "done": a check that passes says the model predicts a pass. It counts the passes by how
    far they can be trusted (draft: the requirement is not confirmed; provisional: it rests on something not
    confirmed or checked, or fails under a plausible change of a guess; credible: none of those; validated: a test of
    the real thing agrees), and lists what would raise them. Returns True when no check fails."""
    from systems import STANDING_TEXT
    m = _m()
    for model_ in ("assumptions", "interfaces", "blocks"):
        if not getattr(m, model_) and model_ not in m.skipped:
            m.skip(model_, "none written")
    m.write(baseline=baseline)
    results = [m.result(id) for id in m.requirements]
    by = {}
    for r in results:
        by.setdefault(r["standing"], []).append(r["requirement"])
    failing = by.get("fail", []) + by.get("test_fail", []) + by.get("not_verified", [])
    if not results:
        print("FAILING: no requirements are written.")
        return False
    if failing:
        print(f"FAILING: {', '.join(failing)}. Change the design and run again.")
        return False
    passing = sum(len(by.get(k, [])) for k in ("draft", "provisional", "credible"))
    parts = ", ".join(f"{len(by[k])} {k}" for k in ("draft", "provisional", "credible") if by.get(k))
    print(f"NO FAILING CHECKS: {passing} pass ({parts}), {len(by.get('validated', []))} validated, "
          f"{len(by.get('not_checked', []))} for a person to check.")
    confirm_r = by.get("draft", [])
    confirm_a = [a.id for a in m.assumptions.values() if not a.confirmed]
    if confirm_r:
        print(f"  Confirm these requirements with the user: {' '.join(confirm_r)}")
    if confirm_a:
        print(f"  Confirm these assumptions: {' '.join(confirm_a)}")
    weak = [id for id in by.get("provisional", []) + by.get("draft", []) if m.requirements[id].fragile]
    if weak:
        print(f"  Fragile (fail under a plausible change of a guess): {' '.join(weak)}")
    print("  Nothing is done until it is tested on the real thing: record tests with validate().")
    return True
