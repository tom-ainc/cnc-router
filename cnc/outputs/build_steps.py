"""The build steps as the page plays them back and the procedure lists them, with their fasteners and welds."""
from cnc import assembly as A
from cnc.parts import detail as D
from cnc.parts import fasteners as FA
from cnc.checks.build import ASM_STEPS, ASM_UNITS, JOINT_RESULTS

# ---- the build, for the page to play back
STEPS = []
for _st in ASM_STEPS:
    _parts = list(_st["adds"]) + (list(ASM_UNITS[_st["moves"]]["parts"]) if _st["moves"] else [])
    def _legs_json(p):
        L_ = A._legs(p)
        return None if L_ is None else [[list(l[0]), l[1], l[2] if len(l) > 2 else "local"] for l in L_]
    _legs_of = {}
    for _n in _st["adds"]:
        _p = _st["path"]
        for _pat, _q in _st["paths"].items():
            if A.fnmatch.fnmatchcase(_n, _pat):
                _p = _q
        _legs_of[_n] = _legs_json(_p)
    STEPS.append(dict(id=_st["id"], phase=_st["phase"], title=_st["title"], text=_st["text"], tools=_st["tools"], fixture=_st["fixture"],
                     why=_st["why"], adds=_st["adds"], unit=_st["unit"], moves=_st["moves"], path=_legs_json(_st["path"]), legs_of=_legs_of,
                     pose=list(_st["pose"]) if _st["pose"] else None, lift=_st.get("lift")))
for _st in STEPS:
    _js = [J for J in JOINT_RESULTS if J["step"] == _st["id"] and J["f"]["type"] != "STUD"]
    _sum = {}
    for J in _js:
        k = (FA.label(J["f"]), FA.tool(J["f"]), FA.torque(J["f"], J["into"]))
        _sum[k] = _sum.get(k, 0) + len(J["pts"])
    _st["fasteners"] = [dict(n=n, label=k[0], tool=k[1], torque=k[2]) for k, n in _sum.items() if not k[0].startswith("M16 x 34 levelling")]
    _st["welds"] = [dict(a=W["a"], b=W["b"], how=W["how"]) for W in D.WELDS if W["step"] == _st["id"]]
