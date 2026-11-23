"""The interface list: datums and the dimensions each pair of parts must agree on (local frame, mm)."""
import math
from se import flow, meets
from cnc.params import (
    BLK_H, CHAIN_R, COL_D, COL_W, M_CW, PL, SHEAVE_D, SPOIL_T, SP_OFF, SP_W, SUP_SPACER, X_BED, X_PINION_PCD, YS_X,
    YS_Z, Y_RAIL, Y_RB, Y_RISER, Y_RT, ZC0, ZS_X, Z_RISER)
from cnc.geometry.bed import CROSS, SUBSTRATE_T, XCH, n_cross
from cnc.geometry.moving import ROPE_X, SHEAVE_Z
from cnc.geometry.world import N_LEGS

# ---- interface list: datums and the dimensions each pair of parts must agree on (local machine frame, mm)
meets("BED", "SP", "Datums: A = spoilboard face (z 0), B = sheet's bottom edge on the pop-up pins (y 0), C = sheet's left edge (x 0)",
      keeps="all positions below are from A, B, C")
meets("GAN", "BED", f"X rails HGR25 on the bed's front face (z {-SPOIL_T:g}), centres at y {Y_RB:g} and {Y_RT:g} "
      f"({Y_RT - Y_RB:g} apart), {X_BED[1] - X_BED[0]:.0f} long; 2 x HGH25CA per rail at +-45 from the column centre",
      keeps="rail faces coplanar and rails parallel within 0.05 mm over the length")
meets("GAN", "BED", f"Helical racks m1.5 beside each rail (centre y {Y_RB - 62.5:g} and {Y_RT + 62.5:g}); 20T pinion "
      f"(PCD {X_PINION_PCD:g}) on each foot, 3:1 belt (15T:45T HTD 5M) from the X motor; racks on 3 mm shims, teeth facing away from the rails",
      keeps=f"pinion centre {X_PINION_PCD / 2:.2f} from the rack's pitch line (1.5 below its tooth tips); a sprung, pivoting housing takes up backlash")
meets("GAN", "BED", f"X cable chain {XCH['inner'][0]:g} x {XCH['inner'][1]:g} inside, R{CHAIN_R:g}, lying against the bed's back face just under its top edge; "
      "an arm from the top foot reaches over the bed's top edge to its moving end; the fixed run heads left from the fixed end, so the cables leave it straight into the trunking to the right", keeps="chain clear of the bed and the floor frame")
meets("YC", "GAN", f"Y cable chain 25 x 38, R{CHAIN_R:g}, on the column's front face, looping towards the operator; fixed end above the middle, "
      "running down, so the cables from the X chain go straight in; bracket from the Y plate above the carriage's centre")
meets("ZA", "YC", f"Z cable chain 25 x 38, R{CHAIN_R:g}, beside the Y plate's upper edge (the Y chain's side), looping outwards; carries the spindle, fan and air lines to the Z plate")
meets("YC", "GAN", f"Y rails HGR25 on {Y_RISER:g} mm risers on the column's +x face, at z {ZC0 + 40:g} and {ZC0 + COL_D - 40:g} "
      f"({COL_D - 80:g} apart), y {Y_RAIL[0]:g} to {Y_RAIL[1]:g}; Y plate inner face {Y_RISER + BLK_H:g} off the column face",
      keeps="riser tops machined coplanar, rails parallel within 0.03 mm")
meets("YC", "GAN", f"Y screw 25 x 20 lead: axis {YS_X:g} off the column face at z {YS_Z:g}; BK20 at the top, BF20 at the bottom on "
      f"{SUP_SPACER:g} mm spacers; nut flange 68 bolted to a bracket on the Y plate", keeps="screw axis parallel to the Y rails within 0.05 mm")
meets("YC", "GAN", f"Y belt HTD 5M 15 wide over the column's top cap: 30T on the Y motor, 20T on the screw, centres "
      f"{math.hypot((COL_W + 50) + YS_X, (ZC0 + COL_D - 60) - YS_Z):.0f} apart; 24 V brake on the screw's bottom end")
meets("GAN", "YC", f"Counterweight rope, 5 mm 7x19, in the gap {ROPE_X:g} off the column face at z {SHEAVE_Z:g}: anchor on the Y plate, "
      f"over a {SHEAVE_D:g} sheave through a slot in the column wall, 2:1 to a {M_CW:.0f} kg block", keeps="rope plane clear of the Y blocks and BK20")
meets("ZA", "YC", f"Z rails HGR25 on {Z_RISER:g} mm aluminium risers on the Y plate's outer face, at y +-70 (140 apart); "
      f"Z screw 20 x 10 lead {ZS_X:g} off the plate, BK15 at the far end, BF15 near; nut on the Z plate", keeps="rails parallel within 0.03 mm")
meets("ZA", "YC", f"Z belt past the Y plate's end: 40T on the Z motor (behind the plate), 20T on the screw, centres {Y_RISER + BLK_H + PL + ZS_X - (Y_RISER + BLK_H - 50):.0f} apart")
meets("SP", "ZA", f"Spindle axis {SP_W / 2 + 10:g} off the Z plate's outer face ({SP_OFF:g} off the column face); two clamp blocks on the body",
      keeps="spindle axis normal to datum A within 0.05 mm over 100 mm (tram)")
meets("SP", "ELEC", "3-ph 0-230 V 0-800 Hz from the Delta VFD (full flux to 484 Hz); STO to the E-stop chain", kind="electrical")
meets("GAN", "ELEC", "Four 34E1K-120 motors, each on its own driver and 60 V 350 W supply; cables through drag chains", kind="electrical")
meets("BED", "BASE", f"bed's bottom rail beam welded along the floor frame's front rail; {N_LEGS} rear posts (SHS 60x60x4) to the top rail beam's back face",
      keeps=f"rear posts at {(X_BED[1] - X_BED[0] - 80) / (N_LEGS - 1):.0f} mm pitch")
meets("BED", "BED", f"spoilboard MDF {SPOIL_T:g} screwed to a {SUBSTRATE_T:g} mm MDF substrate glued to {n_cross} RHS 50x50x3 cross members at "
      f"{(X_BED[1] - X_BED[0] - CROSS['b']) / (n_cross - 1):.0f} mm pitch between the rail beams", keeps="spoilboard face is datum A; surfaced in place by the machine")
flow(["mains, A", "air, bar", "G-code"], ["cut parts", "chips to the dust hood"])
meets("ATC", "BED", "tool rack's two stands bolted up through the substrate at the bed's right end (2 x M6 each, from behind)")
meets("ATC", "SP", "ISO30 holder flange groove in a 41 mm fork slot; the spindle slides a holder in along +x at the fork's height",
      keeps="cutter tip above the spoilboard and clear of a 25 mm sheet while sliding (R54)")
meets("ELEC", "BASE", "cabinet stand welded to stubs continuing the floor frame's rails past the bed's right end")
meets("ELEC", "BED", "X chain's fixed end on the tray; trunking on the tray's rear shelf to the stand; X home flags on the substrate; "
      "pop-up pin cylinders and their hose", kind="electrical")
meets("ELEC", "YC", "Z motor, Z home sensor; spindle cables and hoses pass from the Z chain to the Y chain over the carriage's upper edge",
      kind="electrical")
meets("ELEC", "SP", "tool release (8 mm) and taper blow (6 mm) air through the Z, Y and X chains from the valve manifold", kind="fluid")
