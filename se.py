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

`report` runs last: it prints one line for each requirement, writes `systems.json`, brings the page
(`page/index.html`) up to date, and says whether any check fails.
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
    "PageView",
    "mesh",
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
        pushed = held.fork().moved(Location.translation(*(step * d for d in move)))
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
        there = moving.fork().moved(place(i / (steps - 1)))
        for name, other in fixed.items():
            require(id, text, _shared(there, other), "<=", 0, "mm^3", case=f"{name}, step {i} of {steps - 1}")


def report(baseline=None):
    """Prints the results, brings the page up to date, and says how far they go. Call it last.

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
    page = _write_page(m)
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
        if page:
            print(f"The page: {page}")
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
    if page:
        print(f"The page: {page} (serve the page/ folder, python3 -m http.server, or publish it)")
    return True



# ================================================================== the page
_COMPONENT_ORDER = ["sim.js", "sim-page.js", "sim-ui.js", "build.js", "flex.js", "confirm.js", "stackup.js", "hazards.js",
                    "cost.js", "tests.js"]


def _write_page(m, folder="page"):
    """Brings the page up to date with this run: systems.json into page/, and a default viewer_data.json when the
    script wrote none (no 3D model: the requirements, diagram and tabs). The page itself (index.html, core.js and
    golf's viewer) is copied from the systems-engineering skill; the page must be served (or published) to open."""
    import json
    import os
    if not os.path.exists(os.path.join(folder, "core.js")):
        print(f"  No page: copy it from the systems-engineering skill (mkdir -p {folder} && cp -r <skill>/page/* {folder}/), then run again.")
        return
    S = json.load(open("systems.json"))
    with open(os.path.join(folder, "systems.json"), "w") as f:
        f.write(json.dumps(S))
    vp = os.path.join(folder, "viewer_data.json")
    if not os.path.exists(vp):
        V = dict(title=m.name, components=[c for c in _COMPONENT_ORDER if os.path.exists(os.path.join(folder, c)) and c != "flex.js"])
        with open(vp, "w") as f:
            f.write(json.dumps(V))
    stale = os.path.join(folder, "data.js")
    if os.path.exists(stale):
        os.remove(stale)
    return os.path.abspath(os.path.join(folder, "index.html"))


# ================================================================== the page's data
def mesh(solid, chord=0.05, angle=10.0):
    """Triangles of a solid for the page: {"p": flat xyz, "t": flat triangle indices}. Works with any solid that has
    .mesh(chord, angle) returning .points() and .triangles() (golf's do); `angle` is in degrees."""
    m = solid.mesh(chord, angle)
    return {"p": [round(c, 2) for pt in m.points() for c in pt], "t": [i for tr in m.triangles() for i in tr]}


class PageView(dict):
    """What the page (page/index.html and core.js, copied from this skill) shows: the 3D model, how it moves, and how
    the page lays out its tiles and block diagram. A dict, so anything the components read can be added as a key.

        V = PageView("Rain tank on a stand", "2 m stand, 500 L tank", components=["build.js"])
        V.frame(translate=(0, 0, 0))
        V.axis("lift", "Lift height", (0, 800))                   # a slider, and a pose value
        V.group("lifted", ("lift", (0, 0, 1)))                    # parts in "lifted" move up with it
        V.part("tank", tank_solid, group="lifted", colour="#3b7dd8", info="PE, 500 L")
        V.tile("Height", height, "mm", req="R3", note="/ 2000")
        V.show("R3", pose=[800], parts=["tank", "stand"], dims=[[a, b, "1960 mm"]])
        V.write()                                                # page/viewer_data.json

    Parts in a group move with it; "fixed" parts sit in the model's frame, "world" ones in the scene. A pose is a dict
    of axis values, or a list in the order the axes were added."""

    def __init__(self, title, subtitle="", components=(), whole="whole system", **extra):
        super().__init__(title=title, subtitle=subtitle, components=list(components), whole=whole,
                         parts={}, viz={}, axes=[], groups={}, **extra)

    def golf(self, folder="golf"):
        """Draw the parts with golf's viewer from the bundle `golf bundle --out page/<folder>` wrote: the design script
        shows each part with group= its moving group (the groups below), and the page moves the instances by name.
        Parts given here with meshes are drawn too, beside the golf model."""
        self["golf"] = folder
        self["golf_bundle"] = True

    def golf_models(self, parts, folder="page/golf", max_mb=12.0):
        """Write the parts as golf models for the page's viewer, from the design script itself (golf 0.1.0-rc.25 or
        later): parts is [(name, part, colour (r, g, b), group)], each part placed in the world. golf's viewer loads a
        model of at most 16 MiB of text, so the parts are packed into as many models as that takes. Writes
        <folder>/models/*.golf-transfer.b64.txt and <folder>/bundle.json, and sets V["golf"]; the viewer itself is
        page/cinema/ (from this skill). Returns the number of models."""
        import base64
        import hashlib
        import json
        import os
        from golf_py import Group, export_transfer
        os.makedirs(os.path.join(folder, "models"), exist_ok=True)
        for f in os.listdir(os.path.join(folder, "models")):
            os.remove(os.path.join(folder, "models", f))
        cap = max_mb * 1024 * 1024 * 3 / 4                    # bytes of transfer per model, before base64
        models, todo = [], [list(parts)]
        while todo:
            share = todo.pop(0)
            g = Group("page")
            for name, part, colour, group in share:
                g = g.with_part(part.fork().with_name(name).with_colour(tuple(colour)))
            data = export_transfer(g)
            if len(data) > cap and len(share) > 1:             # too big for one model: split it by faces and try again
                n = max(2, -(-int(len(data) * 1.2) // int(cap)))
                load, shares = [0] * n, [[] for _ in range(n)]
                for e in sorted(share, key=lambda e: -e[1].num_faces()):
                    k = load.index(min(load)); shares[k].append(e); load[k] += e[1].num_faces()
                todo[:0] = [x for x in shares if x]
                continue
            models.append((share, data))
        bundle = {"schema": 1, "transfer_version": 5, "current": len(models), "models": {}}
        for i, (share, data) in enumerate(models, 1):
            text = base64.b64encode(data).decode()
            path = f"models/{i}.golf-transfer.b64.txt"
            with open(os.path.join(folder, path), "w") as f:
                f.write(text)
            bundle["models"][str(i)] = {"path": path, "status": "ok", "parts": [n for n, *_ in share],
                                        "sha256": hashlib.sha256(text.encode()).hexdigest()}
        with open(os.path.join(folder, "bundle.json"), "w") as f:
            json.dump(bundle, f, indent=1)
        self["golf"] = folder[len("page/"):] if folder.startswith("page/") else folder
        return len(models)

    def frame(self, translate=(0, 0, 0), rotate=(0, 0, 0)):
        """Where the model's own frame sits in the world (z up, mm): a move, then rotations about x, y, z in degrees."""
        self["frame"] = {"translate": list(translate), "rotate": list(rotate)}

    def axis(self, id, label, range, unit="mm", start=None, step=1):
        self["axes"].append(dict(id=id, label=label, range=list(range), unit=unit, step=step,
                                 start=range[0] if start is None else start))

    def group(self, name, *terms):
        """A moving group. Each term is (axis, direction, scale=1, ref=0): the group moves direction * scale *
        (pose[axis] - ref), summed over the terms. A counterweight on a 2:1 rope: ("y", (0, 1, 0), -0.5, y0)."""
        self["groups"][name] = [[t[0], list(t[1]), t[2] if len(t) > 2 else 1, t[3] if len(t) > 3 else 0] for t in terms]

    def part(self, name, solid=None, group="fixed", colour="#a0a4a8", info="", kind="made", chord=0.05, angle=10.0, **fields):
        """A part to draw. Give the solid (meshed here), or mesh= a mesh dict, or shared= a key of self["shared"] with
        loc= its 4x4 row-major placement. Names with dots group under their prefix ("frame.leg_1" is in "frame")."""
        d = dict(group=group, colour=colour, info=info, kind=kind, **fields)
        if solid is not None:
            d.update(mesh(solid, chord, angle))
        elif "mesh" in d:
            d.update(d.pop("mesh"))
        self["parts"][name] = d

    def button(self, label, pose=None, ms=1200, seq=None):
        """A button under the sliders: go to a pose, or play a sequence [(pose, ms), ...]."""
        self.setdefault("buttons", []).append(dict(label=label, seq=[[p, t] for p, t in seq]) if seq else dict(label=label, pose=pose, ms=ms))

    def sweep(self, name, *legs):
        """Travel a requirement's view can play: legs (axis, value or None for where it started, ms)."""
        self.setdefault("sweeps", {})[name] = [list(l) for l in legs]

    def view(self, name, dir, height, target, label=None):
        """A camera view: looking along -dir at target, showing height mm of the world. Without any, the page fits
        iso, side and front views to the model."""
        self.setdefault("views", {})[name] = dict(dir=list(dir), height=height, target=list(target), **({"label": label} if label else {}))

    def floor(self, x, y, step=100, major=1000):
        self["floor"] = dict(x=list(x), y=list(y), step=step, major=major)

    def tile(self, label, value, unit="", req="", note="", digits=None):
        """A headline number above the diagram; clicking it opens its requirement."""
        self.setdefault("tiles", []).append(dict(label=label, value=value, unit=unit, req=req, note=note, digits=digits))

    def diagram(self, nodes, ext=None, W=128, H=54, w=76, h=24, frame=None, size=None):
        """The block diagram's layout: nodes {id: (x, y)}, ext {outside thing: (x, y, [blocks it touches])}. Without
        one, the page puts the top-level blocks in a grid."""
        self["diagram"] = dict(nodes={k: list(v) for k, v in nodes.items()}, ext={k: [v[0], v[1], list(v[2])] for k, v in (ext or {}).items()},
                               W=W, H=H, w=w, h=h, **({"frame": list(frame)} if frame else {}), **({"size": list(size)} if size else {}))

    def show(self, req, pose=None, parts=None, view=None, dims=None, marks=None, sweep=None, **flags):
        """How selecting a requirement looks: the pose, the parts lit, a view, dimension lines [[a, b, text]],
        marks [[point, text]], a sweep to play. Flags for components: build=True opens it at its build step,
        sim=True in the simulation."""
        z = {k: v for k, v in dict(pose=pose, parts=parts, view=view, dims=dims, marks=marks, sweep=sweep).items() if v is not None}
        self["viz"][req] = {**self["viz"].get(req, {}), **z, **flags}

    def progress(self, now, next="", done=""):
        """What the agent is doing, shown in a band under the page's header: what changed since the user last
        looked (done), what it is working on (now), and what comes after (next). Update it with each publish."""
        import datetime
        self["progress"] = dict(now=now, next=next, done=done, at=datetime.datetime.now().strftime("%H:%M"))

    def ask(self, *ids):
        """The batch of requirements and assumptions to put to the user now: the few whose answers matter for the
        work about to start. The To confirm tab shows them first, under "Asked now"."""
        self["ask"] = list(ids)

    # ---- data for the companion skills' components (each component's file says how it shows it)
    def bom_line(self, item, node, qty, price, kind="bought", unit="", supplier="", part_no="", link="", date="",
                 estimated=False, basis="", parts=None):
        """A line of the bill of materials for cost.js. price is per unit; kind is bought, made, owned (salvaged or
        already owned: price 0) or stock; estimated prices give their basis (a rate per kg, per hour)."""
        b = self.setdefault("bom", {"lines": []})
        b["lines"].append(dict(item=item, node=node, qty=qty, unit=unit, price=price, kind=kind, supplier=supplier,
                               part_no=part_no, link=link, date=date, estimated=estimated, basis=basis, parts=parts or []))

    def bom_total(self):
        return sum((l["price"] or 0) * (l["qty"] or 1) for l in self.get("bom", {}).get("lines", []))

    def bom_setup(self, currency, basis="", budget=None, req=None, today=None):
        """The bill's currency and basis ("incl. GST, excl. shipping"), and the budget with its requirement."""
        b = self.setdefault("bom", {"lines": []})
        b.update(currency=currency, basis=basis, **({"budget": {"limit": budget, "req": req}} if budget is not None else {}),
                 **({"today": today} if today else {}))

    def hazard(self, id, mode, S, L, node="P", kind="hazard", D=None, energy="", who="", function="", effect="",
               cause="", detect="", mitigation="", reqs=(), parts=None, iface="", residual=""):
        """A hazard (kind="hazard": an energy that can reach someone) or a failure mode (kind="failure": FMEA) for
        hazards.js, rated severity S, likelihood L and, for failure modes, detection D on the scales set with
        hazard_scales. reqs are the requirements that check its mitigation."""
        h = self.setdefault("hazards", {"items": []})
        h["items"].append({k: v for k, v in dict(id=id, kind=kind, mode=mode, S=S, L=L, D=D, node=node, iface=iface,
                           energy=energy, who=who, function=function, effect=effect, cause=cause, detect=detect,
                           mitigation=mitigation, reqs=list(reqs), parts=parts, residual=residual).items() if v not in (None, "")})

    def hazard_scales(self, S, L, D=None, threshold=None, agreed=False):
        """Labels for each rating, lowest first (S=["negligible", ..., "fatal"]); threshold: the risk (S x L, x D for
        failure modes) at and above which a requirement must check the mitigation; agreed: the user has agreed them."""
        h = self.setdefault("hazards", {"items": []})
        h.update(scales={k: list(v) for k, v in dict(S=S, L=L, D=D).items() if v}, threshold=threshold, agreed=agreed)

    def test(self, id, title, shows=(), params=(), why="", method="", equipment=(), procedure=(), pass_="", record="",
             group="", order=None, before="", status="planned", result=""):
        """A test of the real thing for tests.js: the requirements it validates (shows) or the parameters it measures,
        how, what passes, and its place in the order. status: planned, passed or failed."""
        t = self.setdefault("tests", {"plan": [], "calibration": []})
        t["plan"].append(dict(id=id, title=title, shows=list(shows), params=list(params), why=why, method=method,
                              equipment=list(equipment), procedure=list(procedure), pass_=pass_, record=record, group=group,
                              order=len(t["plan"]) if order is None else order, before=before, status=status, result=result))
        t["plan"][-1]["pass"] = t["plan"][-1].pop("pass_")

    def calibration(self, param, measured, unit="", guess=None, uncertainty=None, method="", date="", predicted=None, changed=()):
        """A measured parameter for tests.js: the old guess, what the model predicted for the test, the measurement
        with its uncertainty, and the requirements whose standing changed [(id, before, after)]."""
        t = self.setdefault("tests", {"plan": [], "calibration": []})
        t["calibration"].append(dict(param=param, unit=unit, guess=guess, measured=measured, uncertainty=uncertainty, method=method,
                                     date=date, predicted=predicted, changed=[dict(req=c[0], before=c[1], after=c[2]) for c in changed]))

    def write(self, path="page/viewer_data.json"):
        import json
        import os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(json.dumps(self))
