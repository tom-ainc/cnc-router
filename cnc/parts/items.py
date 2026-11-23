"""Every detailed part as an item (name, part, material, kind, note, group), with its colour and mass."""
from cnc.parts import detail as D
from cnc.parts import electrical as EL
from cnc.params import M_KG, M_SPINDLE_KG
from cnc.geometry.bed import CHAIN_SPECS
from cnc.geometry.pose import REF
from cnc.parts.floor import floor_items
from cnc.design import namespace

# ---- detailed parts: built here so the masses below come from them
D.JOINTS.clear(); D.WELDS.clear()
items = D.bed_assembly(namespace()) + D.atc_assembly(namespace()) + D.gantry_assembly(namespace(), REF[0]) + D.head_assembly(namespace(), *REF) \
    + D.chains(namespace(), REF) + D.counterweight_assembly(namespace(), REF[0], REF[1]) + floor_items
items += EL.cabinet(namespace()) + EL.front_estop(namespace()) + EL.popup_pins(namespace()) + EL.ducts(namespace()) + EL.world_ducts(namespace())
items += EL.machine_side(namespace(), items)
ROPE_PTS = D.rope_path(namespace(), REF[0], REF[1])
items.append(D.item("gantry_frame.rope", D.rope_part(ROPE_PTS), "steel", "bought",
                    "5 mm 7x19 galvanised wire rope: swaged stop at the carriage anchor, swaged eye over the dead-end bolt", "x"))
for _it in items:
    if _it["name"].startswith("atc."):
        _it["name"] = "atc_rack." + _it["name"][4:]
print("detailed items", len(items))
COLOURS = {"steel": (0.45, 0.48, 0.53), "6061": (0.75, 0.77, 0.8), "MDF": (0.72, 0.62, 0.45), "UHMW": (0.92, 0.92, 0.88),
           "electrical": (0.22, 0.3, 0.42), "plastic": (0.6, 0.62, 0.6),
           "rubber": (0.12, 0.12, 0.12), "nylon": (0.18, 0.4, 0.3), "carbide": (0.85, 0.85, 0.85)}
for _it in items:
    _c = (0.25, 0.27, 0.3) if _it["kind"] == "bought" and _it["mat"] == "steel" else COLOURS[_it["mat"]]
    if _it["name"].startswith("spindle."):
        _c = (0.55, 0.15, 0.13)
    if _it["name"] == "sheet":
        _c = (0.85, 0.7, 0.45)
    _it["colour"] = _c
# ---- masses from the detail
DENS_ALL = dict(D.DENS, rubber=1.2, nylon=1.1, carbide=14.5, electrical=0.9, plastic=1.3)
CHAIN_KGM = {"x": 0.9, "y": 0.7, "z": 0.7}


def item_kg(it):
    if it["name"] == "spindle.body":
        return M_SPINDLE_KG
    if it["name"] in CHAIN_SPECS:
        return CHAIN_KGM[it["name"].split(".")[-1][0]] * CHAIN_SPECS[it["name"]]["L"] / 1000
    return it["part"].volume() * DENS_ALL[it["mat"]] * 1e-6


for _it in items:
    _it["kg"] = item_kg(_it)
kg_group = {}
for _it in items:
    kg_group[_it["group"]] = kg_group.get(_it["group"], 0.0) + _it["kg"]
kg_spindle = sum(it["kg"] for it in items if it["name"].startswith(("spindle.", "tool")))
kg_z = kg_group["xyz"] - kg_spindle
kg_y = kg_group["xy"] + M_KG                                  # with the Z motor
kg_gantry = kg_group["x"] + 3 * M_KG                          # with the X and Y motors
print(f"detail masses: Y carriage {kg_y:.1f}, Z axis {kg_z:.1f}, spindle {kg_spindle:.1f}, gantry {kg_gantry:.1f}, cw {kg_group['cw']:.1f}")
