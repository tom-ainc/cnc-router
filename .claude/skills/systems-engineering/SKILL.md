---
name: systems-engineering
description: Has the agent write what a thing must do, what it meets and a check for each requirement into the design's own script before it designs, changes or analyses anything, then work until the checks pass. Use at the start of any engineering task, whatever the tools or the field, and before reporting its result.
---

# Working as a systems engineer

Write down what the thing must do and how each requirement is checked before you design or change
it. Put that in the same script as the design, so that every run tests it. Then work until the run
says `DONE`.

## Steps

1. Read the request and every file, and the guidance of the tools you will use, such as golf's own
   skills. Change nothing yet.
2. Copy the three `.py` files from this folder into the task's folder:
   `cp .claude/skills/systems-engineering/*.py .`
3. In the design's script (a golf script, or a plain Python file where there is no CAD), write the
   models at the top and a `require` line for each requirement at the bottom, as below.
4. Run it before the design is right. It prints `NOT DONE` and the failing requirements. For a
   design that exists, this first run is on the design unchanged.
5. Change the design and run again. **Repeat until the last line says `DONE`.** One run is never
   enough: expect five or more. Do not write your report while the last line says `NOT DONE`, unless
   five different changes have failed to move the same requirement; then say so.
6. Report each requirement with its measured value, limit and margin, then the assumptions not
   confirmed and what the user still has to test. Give the path of `systems.html`.

A question that one measurement or lookup answers needs none of this: answer it with the tools, as
their own guidance says, and state anything assumed.

## The script

```python
from se import *

product("Rain tank on a stand", task="new_design")       # or change_review, optimization, problem_solving
part("TNK", "Tank", material="Steel")
outside("floor", "four feet on a level floor")           # each thing outside that it meets
outside("hose", "G1/2 outlet", keeps="thread and height")
flow(["rain, L/min"], ["water at the outlet, L/min"])    # what goes in, what comes out
assume("The hose needs the outlet 300 mm up", why="no height was given")

RADIUS, HEIGHT, WALL, STAND = 200.0, 450.0, 1.2, 320.0
tank = Part.cylinder(RADIUS, HEIGHT)                     # the design, built with the tool
show(tank, "tank")

require("R1", "The tank shall hold at least 50 L", tank.volume(), ">=", 50, "L", measured_in="mm^3")
require("R2", "The outlet shall be at least 300 mm up", STAND, ">=", 300, "mm")
require("R3", "The empty tank shall weigh no more than 12 kg",
        mass_kg(2 * 3.1416 * RADIUS * HEIGHT * WALL, "Steel"), "<=", 12, "kg")
cannot_check("R4", "The tank shall be galvanised", why="a finish, not geometry")
report()
```

- `require(id, text, value, op, limit, unit)`: `value` is measured from the design; `op` is `<=`,
  `>=` or `==`. `measured_in=` gives the value's unit when it is not the limit's. Call it once for
  each case with `case="open"`, `case="closed"`.
- `require_true(id, text, passed, note)` is for a fact with no number, computed from the design.
- `cannot_check(id, text, why)` is for what the model cannot show. Never use it for something that
  can be measured or computed.
- `report()` goes last. It writes `systems.html`, the page for the user.

Checks that take one line, for solids made with golf:

| Call                                                            | Checks                                                                 |
| --------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `require_one_solid("R5", part)`                                 | A part built from pieces is joined into one solid                      |
| `require_no_overlap("R6", {"motor": motor, "cover": cover})`    | No two of the named parts share volume: name every part                |
| `require_held("R7", holder, held, free=("+x",))`                | `held` fits in `holder` and cannot leave except by the `free` ways     |
| `require_clear_travel("R8", moving, {"rail": rail}, place=...)` | A moving part clears each fixed part at eleven places along its travel |

`place=lambda t: Location.translation(t * 80, 0, 0)` moves the part from where it is now (`t` = 0)
to the end of its travel (`t` = 1).

## Rules

- **A number for everything that can be measured.** "Shall clear" is a minimum distance. "Shall not
  overlap" is a maximum of zero shared volume. "Shall hold" is something a check can show.
- **Measure, do not judge by eye.** Sizes, volumes, distances and overlaps come from the tool, never
  from a number typed again.
- **Behaviour is computed.** Where no tool gives a deflection, a stress, a temperature or a run
  time, use a simple formula, and pass `evidence={"tool": "the formula", "leaves_out": "..."}`. Say
  "cannot be determined" only when no stated assumption would give a number.
- **Model what the product meets.** Give each outside thing a simple solid in its real place, and
  check against it: it fits, it clears, it cannot fall out.
- **Check every case.** For a part that moves, check positions across the whole travel, not only the
  ends. The worst case decides.
- **A change is modelled before it is proposed.** Apply it in the model, check every pair of parts
  for overlap, and run every check. Propose only what passes.
- **Never change a check or a limit to make a design pass.**

## By kind of task

- **Something new:** the first run fails. Build, run, change, until `DONE`. Use `require_one_solid`
  on each part, and `require_held` for anything the product holds, with the held thing modelled as a
  solid in its place.
- **A change to something that exists:** do not reason about where things are. Build or import the
  design and run `require_no_overlap` on all its parts. Then model the changed part in place of the
  old one and run again: each failing pair is what the change breaks. A part that connects to
  something not in the files stays where it is. Model each fix and run again; propose the smallest
  one that gives `DONE`.
- **Making something better:** the thing to improve is one measured value; every limit is a
  `require`, computed by a formula where no tool gives it. Change one variable at a time, running
  each time, and stop when the next step would fail a limit.
- **Something does not work:** the fault is a requirement that is not met. Write the check that
  fails on the unchanged design as the user reports; for a part that moves, that is
  `require_clear_travel` against every fixed part. The failing case names the cause: fix that, and
  nothing that passes. The fix is done at `DONE`, with every part still on its seat.

## With golf

- Overlap of two parts is `(a & b).volume()`; distance is `a.distance_to(b).distance()`, which is 0
  for parts that overlap, so check the overlap too. `golf contacts` lists every pair that touches or
  overlaps.
- Size is `part.bounding_box().size()`; volume is `part.volume()` in mm^3; mass is
  `mass_kg(part.volume(), "Steel")`, since golf has no materials.
