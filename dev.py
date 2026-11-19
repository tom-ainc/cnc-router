"""Run router.py in plain Python (no golf runner): golf's names and a no-op show() are put in builtins.
   python dev.py [probe.py ...]  - each probe runs afterwards with the router's globals."""
import builtins, sys, time, runpy, os
import golf_py
for n in dir(golf_py):
    if not n.startswith("_"):
        setattr(builtins, n, getattr(golf_py, n))
SHOWN = []
builtins.show = lambda part, name, **k: SHOWN.append((name, k))
os.environ["ROUTER_DEV"] = "1"
t = time.time()
g = runpy.run_path("router.py", run_name="__main__")
print(f"dev run {time.time() - t:.0f} s, shown {len(SHOWN)}")
import code
for p in sys.argv[1:]:
    exec(compile(open(p).read(), p, "exec"), g)
if os.environ.get("DEV_SHELL"):
    import pickle
