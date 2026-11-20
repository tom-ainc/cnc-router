"""Shows a design's parts for the page's golf viewer, from files the design run wrote: page_model.json beside this
script, [{name, file (.step, beside it), colour [r, g, b], group}]. golf bundles each run as one model of at most
16 MiB, so a large design is shown in `parts` runs, each with a share of the parts, and bundled together:

    golf run page_model.py --label page0 --param part=0 --param parts=3   (and part=1, part=2)
    golf bundle --out page-golf --version N0 --version N1                (the current run is included)

A design script that runs on the current golf itself does not need this: show() its parts with group= their moving
group and bundle that run. This is for parts that come from elsewhere (an older golf, another CAD tool, STEP files)."""
import json
import os

part = 0
parts = 1

entries = json.load(open("page_model.json"))
# shares of about equal size, by file size, the same in every run
load, share = [0] * parts, {}
for e in sorted(entries, key=lambda e: -os.path.getsize(os.path.basename(e["file"]))):
    k = load.index(min(load))
    share[e["name"]] = k
    load[k] += os.path.getsize(os.path.basename(e["file"]))
for e in entries:
    if share[e["name"]] != part:
        continue
    ps = import_step_file(os.path.basename(e["file"])).parts()
    p = ps[0]
    for q in ps[1:]:
        p = p + q
    show(p, e["name"], colour=tuple(e["colour"]), group=e.get("group") or None)
