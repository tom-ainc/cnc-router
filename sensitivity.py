"""Sensitivity of the simulation's results to its guessed parameters: each at half and double, every job to its end.

Run after router.py (it writes sim_params.json): python3 sensitivity.py. Writes sensitivity.json, and a copy into page/.
Each variation runs every job and reports the worst case of each requirement the simulation checks (R69-R79)."""
import json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from cnc import simulation as SIM

HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(HERE, "sim_params.json")))
path = os.path.join(HERE, ".sweep_params.json")
json.dump(P, open(path, "w"))
n_var = int(subprocess.run(["node", "-e", f"console.log(require({SIM.SIM_JS!r}).VARIATIONS.length)"], capture_output=True, text=True).stdout)
jobs = [list(range(i, 2 * n_var, 2 * (os.cpu_count() or 2))) for i in range(2 * (os.cpu_count() or 2))]
jobs = [j for j in jobs if j]
t0 = time.time()


def node(args):
    out = subprocess.run(["node", SIM.SIM_JS, path] + args, capture_output=True, text=True, timeout=7200)
    if out.returncode:
        raise RuntimeError(out.stderr[-2000:])
    return json.loads(out.stdout)


with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as ex:
    base_f = ex.submit(node, ["base"])
    parts = list(ex.map(lambda w: node(["sweep", ",".join(map(str, w))]), jobs))
os.unlink(path)
rows = sorted([r for p in parts for r in p], key=lambda r: r["i"])
out = {"digest": SIM.digest(P), "base": base_f.result(), "rows": rows, "seconds": round(time.time() - t0)}
for f in (os.path.join(HERE, "sensitivity.json"), os.path.join(HERE, "page", "sensitivity.json")):
    json.dump(out, open(f, "w"), indent=1)
flips = [(r["name"], r["f"], k) for r in rows for k, c in r["checks"].items() if not c["ok"]]
print(f"{len(rows)} variations in {out['seconds']} s; failing: " + ("; ".join(f"{n} x{f}: {k}" for n, f, k in flips) or "none"))
