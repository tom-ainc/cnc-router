"""R55, R41-R43: cable chains."""
import math
from cnc.parts import detail as D
from cnc.parts import electrical as EL
from cnc.params import CABLE_D_MAX, CHAIN, CHAIN_R
from cnc.geometry.bed import CHAIN_SPECS
from cnc.system.requirements import require

CABLES = EL.chain_fill(None)          # from the cable schedule in electrical.py
# cable chains: the loop stays in its zone and both runs stay positive over the whole travel
for _nm, _sp in CHAIN_SPECS.items():
    for _md in (_sp["m_min"], (_sp["m_min"] + _sp["m_max"]) / 2, _sp["m_max"]):      # along the chain's run direction
        _m = _sp["sg"] * _md
        _a, _b = D.chain_state(_sp, _m)
        _run_b = _b - _md
        _hi = _sp["zone"][1] - (_b + _sp["R"] + _sp["h"] / 2)
        _lo = min(_sp["f"], _md) - 0.4 * _sp["pitch"] - _sp["zone"][0]
        require("R55", "Each cable chain shall keep both runs and its loop inside its zone over the whole travel (least margin)",
                min(_a, _run_b, _hi, _lo), ">=", 0, "mm", case=f"{_nm.split('.')[-1]}, moving end at {_m:.0f}")
# cable chains
require("R41", "Cable chains shall bend no tighter than 7.5 x the largest continuous-flex cable", CHAIN_R / CABLE_D_MAX, ">=", 7.5, "",
        evidence={"tool": "chainflex rule: R >= 7.5 d", "leaves_out": "the cable maker's own figure"})
for ax, cables in CABLES.items():
    fill = sum(math.pi / 4 * d * d for d in cables) / (CHAIN[ax]["inner"][0] * CHAIN[ax]["inner"][1])
    require("R42", "Each cable chain shall be no more than 60 % full", fill * 100, "<=", 60, "", case=f"{ax} chain",
            evidence={"tool": "cable areas / inner section", "leaves_out": "separators"})
    require("R43", "Each cable chain's inner height shall take its largest cable", CHAIN[ax]["inner"][0] - max(cables), ">=", 0, "mm",
            case=f"{ax} chain")
