"""The build: every step from stock on the floor to the first cut, as data the router script checks and the page plays back.

A step adds parts (picked by name pattern: exact names, or fnmatch globs such as "bed.cross_*") to the machine where they
finally sit, or to a bench-built unit (`unit=`) that a later step installs as one piece (`moves=`).  Each step says how
its parts arrive (`path`: a direction and a distance in the machine's local frame), what pose the axes are in, how heavy
things are handled (`handle`), and which tools and temporary supports it needs.

Local machine frame: x along the sheet, y up the bed, z out of the bed towards the operator (see router.py).
"""
import fnmatch
import math

PEOPLE = 2                 # the crew (stated by the user)
KG_PERSON = 25.0           # most any one person lifts, pushes or holds (stated by the user)
MOTORS = ("gantry_drives.x_motor_bottom", "gantry_drives.x_motor_top", "gantry_drives.y_motor", "y_carriage.z_motor")

# where each bench-built unit is shown while it waits (local frame offset from where it finally sits): in front of the bed
STAGE = {"backplate": (0.0, -900.0, 0.0),"column": (0.0, 0.0, 1500.0), "x_drive_bottom": (0.0, 0.0, 900.0), "x_drive_top": (0.0, 0.0, 900.0),
         "y_screw": (0.0, 0.0, 900.0), "carriage": (0.0, 0.0, 1300.0), "cw_top": (0.0, -500.0, 900.0), "cw_bottom": (0.0, -500.0, 900.0)}


def S(id, phase, title, text, parts=(), unit=None, moves=None, path=None, handle=None, pose=None, tools=(), fixture=None, why=None, paths=None):
    """One step. path = (direction, distance mm[, "world"]) or a list of such legs: the parts arrive moving along it, in the
    machine's local frame unless "world". paths = {pattern: path} for parts that arrive another way (None: laid in, flexible)."""
    return dict(id=id, phase=phase, title=title, text=text, parts=list(parts), unit=unit, moves=moves, path=path,
                handle=handle or {}, pose=pose, tools=list(tools), fixture=fixture, why=why, paths=paths or {})


def procedure(g):
    """The whole build, in order."""
    X_ASM = g["X_ASM"]                       # the gantry's station while it is built: column midway between two floor legs
    Y_MID = (g["Y_WORK"][0] + g["Y_WORK"][1]) / 2
    TIP_HI = g["ZN_MAX"] - g["TIP_TO_NOSE"]
    pose0 = (X_ASM, Y_MID, TIP_HI)
    UP = (0.0, 0.0, 1.0)                     # out of the bed, towards the operator (and up through the bed from behind)
    TO_BED = (0.0, 0.0, -1.0)                # onto the bed's face, from the operator's side
    DOWN_W = (0.0, 0.0, -1.0)                # straight down, in the world
    DOWN_BED = (0.0, -1.0, 0.0)              # down the bed slope
    TOWARDS_COL = (-1.0, 0.0, 0.0)           # along -x, onto the column's rail face
    steps = []
    a = steps.append
    # ---------------------------------------------------------------- floor frame
    ph = "Floor frame (welded where the machine stands)"
    a(S("F01", ph, "Weld nuts and levelling feet on the floor rails",
        "Weld an M16 nut under each rail at the five leg stations. "
        "Screw a levelling foot into each and set all ten to 30 mm under the rail. Stand the front and rear rails on their feet "
        "where the machine will live, front rail along the chalk line, 2 m clear in front for loading sheets.",
        parts=["floor_frame.front_rail", "floor_frame.rear_rail", "floor_frame.foot_nut_*", "feet.*"], path=(DOWN_W, 300.0, "world"),
        handle={"people": 2, "method": "carry"}, tools=["MIG welder", "tape", "chalk line", "24 mm spanner"]))
    a(S("F02", ph, "Cross members and outriggers",
        "Clamp the five cross members between the rails at the leg stations and tack them. Check the diagonals agree within "
        "2 mm, then tack the five outriggers to the front rail's front face. Weld out all joints, alternating ends.",
        parts=["floor_frame.cross_*", "floor_frame.outrigger_*"], path=(DOWN_W, 300.0, "world"),
        tools=["MIG welder", "framing square", "tape", "4 F-clamps"]))
    a(S("F03", ph, "Level the floor frame",
        "Level the frame on its feet to 0.5 mm/m along both rails and across, with a machinist's level on the rails. "
        "Lock the foot nuts.", tools=["machinist's level 0.05 mm/m", "24 mm spanner"]))
    a(S("F04", ph, "Rear posts",
        "Cut a plywood template to the posts' angle from the drawing. Tack each post to the rear rail on its station with the "
        "template under it and brace its top to the front rail with a timber batten. Leave them tacked only: their tops are "
        "welded to the bed in B06.",
        parts=["floor_frame.rear_post_*"], path=(DOWN_W, 300.0, "world"), tools=["MIG welder", "angle template", "5 timber braces"],
        fixture="timber braces from each post top to the front rail, until B06"))
    a(S("F05", ph, "Cabinet stand",
        "Weld the two stubs onto the front and rear rails' right ends (butt, ground flush), the cross member between their "
        "ends, the two uprights on the rear stub (plumb, 520 apart) and the two weld nuts; screw in the stand's two feet "
        "and level them with the frame.",
        parts=["cabinet_stand.*"], path=(DOWN_W, 300.0, "world"), tools=["MIG welder", "level", "square", "24 mm spanner"]))
    # ---------------------------------------------------------------- bed
    ph = "Bed (welded in place on the floor frame)"
    a(S("B01", ph, "Bottom rail beam",
        "Weld the end caps on the beam on trestles. Lift it onto the front rail with its back face 10 deg back from vertical "
        "(digital angle gauge), hold it with two timber props and G-clamps, and tack it to the front rail at each station.",
        parts=["bed.rail_beam_bottom", "bed.beam_cap_bottom_*"], path=(DOWN_W, 400.0, "world"),
        handle={"people": 2, "method": "carry"}, tools=["MIG welder", "digital angle gauge", "2 trestles", "4 G-clamps"],
        fixture="2 timber props under the beam's front face, until B03"))
    a(S("B02", ph, "Top rail beam",
        "Weld its end caps on trestles. Two people lift it onto the rear post tops, one at each end, standing on "
        "platform steps. Clamp it to the posts. Set the rail centres 1398 mm apart up the slope at both ends and in the middle, "
        "the beams parallel within 1 mm and the face 10 deg back; tack it to each post.",
        parts=["bed.rail_beam_top", "bed.beam_cap_top_*"], path=(DOWN_W, 400.0, "world"),
        handle={"people": 2, "method": "carry"}, tools=["MIG welder", "2 platform steps", "tape", "digital angle gauge", "5 G-clamps"]))
    a(S("B03", ph, "Cross members",
        "Fit the twelve cross members between the beams, set back so the substrate sits on them flush with the beams' "
        "faces less 10 mm. Tack each, check the beams stay 1398 apart, then weld out from the middle outwards, alternating ends "
        "and sides, in short runs so the beams do not bow. Remove the props.",
        parts=["bed.cross_*"], path=(TO_BED, 300.0), tools=["MIG welder", "tape", "string line"]))
    a(S("B04", ph, "Rail lands, rack lands, X chain tray",
        "Clamp each land flat bar to its beam on the layout lines (rail centres 1398 apart, racks 60 mm outboard). "
        "Stitch weld 30 mm every 150 mm, alternating sides and working from the middle out. Weld the X chain tray, with its "
        "rear shelf for the trunking, on the top beam's top face.",
        parts=["bed.rail_land_*", "bed.rack_land_*", "bed.x_chain_tray"], path=(TO_BED, 200.0), paths={"bed.x_chain_tray": (DOWN_BED, 200.0)},
        tools=["MIG welder", "8 toolmaker's clamps"]))
    a(S("B05", ph, "Flatten the lands, drill and tap",
        "With a 1 m precision straightedge and feeler gauges, grind and file the rail lands until each is straight within "
        "0.05 mm per metre and the pair are coplanar within 0.05 mm (a straightedge across both, at 300 mm steps, with a "
        "level on it). Drill and tap the M6 holes with a drill guide from the rail and rack hole patterns.",
        tools=["1 m straightedge (DIN 874/1)", "feeler gauges", "flap disc", "mill file", "drill guide", "M6 taps, 5.0 drill"],
        why="Lands can't be machined in place; the rails are then shimmed (X01)"))
    a(S("B06", ph, "Weld the bed to the floor frame",
        "Weld the bottom beam to the front rail along both sides of the contact line, and the rear posts' tops to the top beam's "
        "back. Remove the braces. Re-check the bed's lean (10 deg) and the floor frame's level.",
        tools=["MIG welder", "digital angle gauge"]))
    a(S("B07", ph, "Clean and paint",
        "Wire-brush the welds, prime and paint the frame. Mask the lands and their tapped holes.",
        tools=["wire brush", "primer", "masking tape"]))
    a(S("B08", ph, "Substrate boards",
        "Lay the three 25 mm MDF boards on the cross members, each end on the middle of a cross member, PVA glue on the "
        "members, and screw through into each member.",
        parts=["bed.substrate.*"], path=(TO_BED, 300.0), handle={"people": 2, "method": "carry"},
        tools=["cordless drill", "PVA glue"]))
    # ---------------------------------------------------------------- X axis
    ph = "X axis"
    a(S("X01", ph, "X rails",
        "Bolt the bottom rail on its land, screws snug. Straighten it against the straightedge (or a taut 0.3 mm wire) "
        "within 0.02 mm per metre, tightening from one end. Fit the top rail, then set it parallel to the bottom one with a "
        "dial indicator on a block run along both: 0.02 mm over the length. Shim under the rails where the lands are low.",
        parts=["bed.x_rail_*"], path=(TO_BED, 150.0), handle={"people": 2, "method": "carry"},
        tools=["dial indicator 0.01 mm and magnetic base", "1 m straightedge", "shim stock 0.02-0.1 mm", "torque wrench"]))
    a(S("X02", ph, "X racks",
        "Fit the racks on their lands, teeth facing away from the rails. Butt each joint with a short piece of rack "
        "meshed across it as a gauge, then tighten; shim under a rack where the pinion's mesh needs it.",
        parts=["bed.rack_bottom.*", "bed.rack_top.*"], path=(TO_BED, 150.0), tools=["rack joining gauge", "torque wrench"]))
    a(S("X03", ph, "X blocks onto the rails",
        "Slide the four HGH25CA blocks off their dummy rails onto the X rails at the rail ends (never off the rail: the balls "
        "fall out). Set them at the gantry's station, 90 mm apart in pairs.",
        parts=["gantry_drives.x_block_*"], path=((1.0, 0.0, 0.0), 300.0), pose=pose0, tools=["block dummy rails"]))
    # ---------------------------------------------------------------- column
    ph = "Gantry column (welded on the bench, stood up onto the X blocks)"
    a(S("G01", ph, "Column box",
        "Tack the M12 weld nut for the sheave axle inside the back flange first: it can't be reached once the box is closed. "
        "On a flat table, tack the two webs and two flanges into a box around spacer blocks, check it square and untwisted, "
        "then weld the corners in 50 mm stitches alternating sides and ends. Weld in the top cap. The bottom cap is bolted, "
        "so the counterweight can go in from below.",
        parts=["gantry_frame.web_*", "gantry_frame.flange_*", "gantry_frame.cap_top", "gantry_frame.sheave_axle_nut"], unit="column",
        tools=["MIG welder", "welding table", "framing square", "6 F-clamps"]))
    a(S("G02", ph, "Y rail risers and feet",
        "Weld the two Y riser bars on the +x web, parallel within 0.5 mm, and the two feet (base plate and gussets) on the "
        "back flange at each end. Flatten the risers as the lands (B05), then drill and tap M6.",
        parts=["gantry_frame.y_riser_*", "gantry_frame.foot_*"], unit="column",
        tools=["MIG welder", "1 m straightedge", "drill guide", "M6 taps"]))
    a(S("G03", ph, "Top rope sheave",
        "Hold the rope sheave in the column top through the +x web slot and push the M12 axle bolt through the front flange, "
        "the sheave, and into the weld nut on the back flange.",
        parts=["gantry_frame.rope_sheave"], unit="column", tools=["hex keys"]))
    a(S("G04", ph, "Stand the column onto the X blocks",
        "Lay the column on its back on a trestle at 900 mm under its top end, with its bottom foot resting on the bottom X "
        "blocks and two M6 screws loosely through the foot into the blocks as a hinge. Both people lift at the top end and walk "
        "it up until the top foot lands on the top blocks. Fit all foot screws, line the feet up square to the rails and "
        "tighten.",
        moves="column", path=(TO_BED, 400.0), pose=pose0,
        handle={"people": 2, "method": "tilt", "axis": 1, "trestle": 900.0},
        tools=["900 mm trestle", "torque wrench", "5 mm hex key"]))
    # ---------------------------------------------------------------- X drives
    ph = "X drives"
    for nm in ("bottom", "top"):
        a(S(f"D0{1 if nm == 'bottom' else 2}", ph, f"X drive, {nm}, on the bench",
            "Press the two 61902 bearings into the housing and the shaft into them; screw the housing under the lower plate. "
            "Fit the pinion on the shaft's flat, 4 standoffs, the motor plate, the motor with its 20T pulley, the 60T on the "
            "shaft, and the belt; tension it by sliding the motor before tightening its nuts.",
            parts=[f"gantry_drives.x_bearing_{nm}", f"gantry_drives.x_brg_{nm}_*", f"gantry_drives.x_shaft_{nm}", f"gantry_drives.x_pinion_{nm}",
                   f"gantry_drives.x_pivot_plate_{nm}", f"gantry_drives.x_standoff_{nm}_*", f"gantry_drives.x_motor_plate_{nm}",
                   f"gantry_drives.x_pulley60_{nm}", f"gantry_drives.x_pulley20_{nm}", f"gantry_drives.x_belt_{nm}",
                   f"gantry_drives.x_motor_{nm}"], unit=f"x_drive_{nm}",
            tools=["bearing press or vice", "hex keys", "belt tension gauge"]))
    for k, nm in ((3, "bottom"), (4, "top")):
        a(S(f"D0{k}", ph, f"Fit the {nm} X drive",
            "Slide the spacer block onto the foot from the side, under the column. Slide the drive in from the side along the rack, "
            "its tab over the spacer and the pinion 4 mm back from the rack, and fit the 2 M8 low-head screws through the tab's 10 mm slots loosely. Push the drive towards the rack until the backlash just "
            "goes (rock the gantry: no free play, no binding anywhere along the rack), then tighten.",
            parts=[f"gantry_drives.x_tab_spacer_{nm}"], moves=f"x_drive_{nm}", pose=pose0, handle={"people": 1, "method": "carry"},
            path=[((1.0, 0.0, 0.0), 150.0), ((0.0, 1.0 if nm == "bottom" else -1.0, 0.0), 4.0)], paths={f"gantry_drives.x_tab_spacer_{nm}": ((1.0, 0.0, 0.0), 100.0)},
            tools=["hex keys"]))
    # ---------------------------------------------------------------- Y axis
    ph = "Y axis (on the column)"
    a(S("Y01", ph, "Y rails",
        "Bolt the two Y rails on the risers; set the first straight against the straightedge and the second parallel with a "
        "dial indicator on a block, 0.02 mm over the length.",
        parts=["gantry_drives.y_rail_*"], path=(TOWARDS_COL, 150.0), pose=pose0,
        tools=["dial indicator", "1 m straightedge", "torque wrench"]))
    a(S("Y02", ph, "Y blocks onto the rails",
        "Slide the four Y blocks onto the rails from the top ends. The rails are near vertical: put a rail stop clamp under "
        "each pair before letting go.",
        parts=["y_carriage.y_block_*"], path=(DOWN_BED, 300.0), pose=pose0,
        tools=["block dummy rails", "4 rail stop clamps"], fixture="rail stop clamps under the Y blocks, until C05"))
    a(S("Y03", ph, "Y screw, supports and brake on the bench",
        "The ball nut comes on the screw: leave it there. Fit the BK20 (with its bearings, lock nut torqued to the "
        "catalogue figure) on the top journal, the BF20 on the bottom one, and the brake on its standoffs below the BF20. "
        "Bolt the nut housing onto the nut's flange: it rides on the nut until the carriage arrives.",
        parts=["gantry_drives.y_screw", "y_carriage.y_nut", "y_carriage.y_nut_bracket", "gantry_drives.y_bk20", "gantry_drives.y_bf20",
               "gantry_drives.y_brake"], unit="y_screw", tools=["hook spanner", "hex keys"]))
    a(S("Y04", ph, "Fit the Y screw",
        "Bolt the spacers and the screw assembly on the column face. Set the screw parallel to the rails with a dial "
        "indicator on a Y block: 0.05 mm in both directions, shimming the supports.",
        parts=["gantry_drives.y_spacer_*"], moves="y_screw", path=(TOWARDS_COL, 150.0), pose=pose0,
        handle={"people": 1, "method": "carry"}, tools=["dial indicator", "shim stock", "torque wrench"]))
    a(S("Y05", ph, "Y motor and belt",
        "Bolt the motor plate on the column's top cap, the motor on the plate. Fit the 30T pulley on the motor, 20T on the "
        "screw, the belt, and tension it by sliding the motor in its slots.",
        parts=["gantry_drives.y_motor_plate", "gantry_drives.y_pulley_*", "gantry_drives.y_belt", "gantry_drives.y_motor"],
        path=(DOWN_BED, 200.0), pose=pose0, tools=["hex keys", "belt tension gauge"]))
    # ---------------------------------------------------------------- Y carriage
    ph = "Y carriage (built on the bench)"
    a(S("C01", ph, "Y plate and Z rails",
        "Bolt the Z risers on the Y plate, then the Z rails on the risers, straight and parallel (0.02 mm). Bolt on the rope "
        "anchor, the Z chain's fixed tab and the Y chain bracket.",
        parts=["y_carriage.y_plate", "y_carriage.z_riser_*", "y_carriage.z_rail_*",
               "y_carriage.rope_anchor", "y_carriage.z_chain_fix", "y_carriage.y_chain_bracket", "sensors.z_home*"], unit="carriage",
        path=(TOWARDS_COL, 100.0),
        paths={"y_carriage.rope_anchor": ((1.0, 0.0, 0.0), 100.0),
               "y_carriage.y_chain_bracket": ((1.0, 0.0, 0.0), 100.0), "y_carriage.z_chain_fix": ((0.0, -1.0, 0.0), 60.0)},
        tools=["dial indicator", "hex keys", "torque wrench"]))
    a(S("C02", ph, "Z blocks",
        "Slide the four Z blocks onto the Z rails from their lower ends.",
        parts=["z_axis.z_block_*"], unit="carriage", path=((0.0, 0.0, 1.0), 300.0), tools=["block dummy rails"]))
    a(S("C03", ph, "Z screw",
        "Z nut stays on its screw; bolt its housing onto its flange. Fit the BK15 and BF15 on the journals, bolt them on their "
        "spacers, the screw parallel to the Z rails within 0.05 mm.",
        parts=["y_carriage.z_screw", "z_axis.z_nut", "z_axis.z_nut_bracket", "y_carriage.z_bk15", "y_carriage.z_bf15", "y_carriage.z_spacer_*"], unit="carriage",
        path=(TOWARDS_COL, 100.0),
        tools=["hook spanner", "dial indicator", "hex keys"]))
    a(S("C04", ph, "Z motor and belt",
        "Bolt the motor mount on the Y plate's top edge, the motor on it; 40T pulley on the motor, 20T on the screw, belt, tension.",
        parts=["y_carriage.z_motor_mount", "y_carriage.z_pulley_*", "y_carriage.z_belt", "y_carriage.z_motor"], unit="carriage",
        path=((0.0, 0.0, -1.0), 150.0), paths={"y_carriage.z_motor": ((0.0, 0.0, 1.0), 200.0)},
        tools=["hex keys", "belt tension gauge"]))
    a(S("C05", ph, "Fit the carriage on the Y blocks",
        "Wind the Y nut to the blocks' height. Both people offer the carriage up to the four Y blocks, nut bracket over the "
        "nut, and fit two screws in each block. Fit the rest, tighten, then bolt the nut flange into the bracket. Take off "
        "the rail stops; hold the carriage with the screw (the brake is not powered yet).",
        moves="carriage", path=(TOWARDS_COL, 250.0), pose=pose0, handle={"people": 2, "method": "carry"},
        tools=["hex keys", "torque wrench"]))
    # ---------------------------------------------------------------- Z axis and spindle
    ph = "Z axis and spindle"
    a(S("Z01", ph, "Z plate",
        "Bolt the Z plate on the four Z blocks and onto the nut housing, then the Z chain bracket on its upper edge.",
        parts=["z_axis.z_plate", "z_axis.z_chain_bracket", "sensors.z_target"], path=(TOWARDS_COL, 200.0), pose=pose0,
        paths={"z_axis.z_chain_bracket": ((0.0, -1.0, 0.0), 80.0)},
        tools=["hex keys", "torque wrench"]))
    a(S("Z02", ph, "Spindle clamp bases",
        "Bolt the two clamp bases on the Z plate through their deep counterbores.",
        parts=["z_axis.clamp_*_base"], path=(TOWARDS_COL, 200.0), pose=pose0, tools=["8 mm hex key, 200 mm long", "torque wrench"]))
    a(S("Z03", ph, "Spindle",
        "Two people set the spindle into the bases (plugs facing +x), fit the caps and tighten the M10s evenly to clamp it.",
        parts=["z_axis.clamp_*_cap", "spindle.body"], path=(TOWARDS_COL, 300.0), pose=pose0,
        handle={"people": 2, "method": "carry"}, tools=["hex keys", "torque wrench"]))
    # ---------------------------------------------------------------- counterweight
    ph = "Counterweight (into the column from below)"
    a(S("W0A", ph, "Top slab on the bench",
        "Screw its 4 UHMW shoes on, weld the sheave fork on its top face and fit the sheave on its M12 axle.",
        parts=["counterweight.slab_7", "counterweight.shoe_top_*", "counterweight.sheave_fork", "counterweight.sheave"], unit="cw_top",
        tools=["MIG welder", "3 mm hex key", "18 mm spanners"]))
    a(S("W0B", ph, "Bottom slab on the bench",
        "Screw its 4 UHMW shoes on.", parts=["counterweight.slab_0", "counterweight.shoe_bottom_*"], unit="cw_bottom",
        tools=["3 mm hex key"]))
    a(S("W01", ph, "Top slab, sheave and rope",
        "Move the head to the top of its travel, so the counterweight's place is at its lowest. With the bottom cap off, "
        "push the top slab up into the column. Reeve the rope: dead end on the column top, down "
        "round the slab's sheave, up over the top sheave, down to the rope anchor on the Y plate. Hang the slab on it and "
        "hang two M12 tie rods from it.",
        parts=["gantry_frame.rope"], moves="cw_top", paths={"gantry_frame.rope": None},
        path=((0.0, 1.0, 0.0), 500.0), pose=(X_ASM, g["Y_WORK"][1], TIP_HI), handle={"people": 1, "method": "carry"},
        tools=["13 mm and 19 mm spanners", "rope swaging tool"]))
    for k in range(6, 0, -1):
        a(S(f"W{8 - k:02d}", ph, f"Slab {k}",
            "Push the slab up onto the tie rods under the last one and run a nut up under it.",
            parts=[f"counterweight.slab_{k}"], path=((0.0, 1.0, 0.0), 300.0), pose=(X_ASM, g["Y_WORK"][1], TIP_HI),
            handle={"people": 1, "method": "carry"}, tools=["19 mm spanner"]))
    a(S("W08", ph, "Bottom slab and bottom cap",
        "Fit the bottom slab with its shoes on the tie rods, tighten the stack, then bolt the bottom cap on the column.",
        parts=["gantry_frame.cap_bottom"], moves="cw_bottom",
        path=((0.0, 1.0, 0.0), 300.0), pose=(X_ASM, g["Y_WORK"][1], TIP_HI), handle={"people": 1, "method": "carry"},
        tools=["19 mm spanner", "hex keys"]))
    # ---------------------------------------------------------------- chains, tool rack
    ph = "Cable chains and tool rack"
    a(S("K01", ph, "Chain arm and brackets",
        "Bolt the X chain arm on the top foot and the Y chain's fixed bracket on the column's front face.",
        parts=["gantry_frame.chain_arm", "gantry_drives.y_chain_fix"], path=(DOWN_BED, 200.0), pose=pose0,
        paths={"gantry_drives.y_chain_fix": (TO_BED, 100.0)},
        tools=["hex keys"]))
    a(S("K02", ph, "Cable chains",
        "Lay each chain in with its end brackets; open every second link's bars so the cables can be laid in later.",
        parts=["bed.x_chain", "gantry_drives.y_chain", "y_carriage.z_chain"], path=None, pose=pose0,
        tools=["hex keys", "flat screwdriver"]))
    a(S("K03", ph, "Tool rack",
        "Screw the two stands to the substrate at the right end, then the spine and fork plate on them; set the fork plate "
        "parallel to the spoilboard face with the spindle as the gauge (A later commissioning step teaches the pockets).",
        parts=["atc_rack.stand_*", "atc_rack.spine", "atc_rack.fork_plate"], path=(TO_BED, 200.0),
        tools=["hex keys", "cordless drill"]))
    # ---------------------------------------------------------------- electrical and air
    ph = "Cabinet, sensors, cables and air"
    YW = (0.0, 1.0, 0.0)
    a(S("E01", ph, "Hang the enclosure",
        "Take the door off. Offer the empty enclosure up to the uprights and bolt it through its back wall: 4 x M8 through the "
        "uprights, nuts behind.", parts=["cabinet.enclosure"], path=(YW, 150.0, "world"), handle={"people": 2, "method": "carry"},
        tools=["13 mm spanners"]))
    a(S("E02", ph, "Backplate on the bench",
        "Bolt the DIN rails, the 3 wiring ducts, the supplies, drivers, VFD, controller and EMC filter to the backplate (M4, nuts "
        "behind); clip the breakers, contactor, relays, 24 V supply and terminals on the rails. Wire it to the wire list: every "
        "wire ferruled and numbered both ends, PE to every metal part.",
        parts=["cabinet.backplate", "cabinet.din_*", "cabinet.duct_*", "cabinet.terminals", "cabinet.controller", "cabinet.psu_*", "cabinet.vfd",
               "cabinet.drv_*", "cabinet.rcd", "cabinet.mcb_*", "cabinet.contactor", "cabinet.safety_relay", "cabinet.brake_relay",
               "cabinet.valve_relays", "cabinet.emc_filter", "wire.*"], unit="backplate",
        tools=["7 mm spanner", "3 mm hex key", "ferrule crimper", "wire stripper", "screwdrivers"]))
    a(S("E03", ph, "Backplate into the enclosure",
        "Both people lift the wired backplate in onto the 4 studs and screw it down.", moves="backplate", path=(YW, 200.0, "world"),
        handle={"people": 2, "method": "carry"}, tools=["5 mm hex key"]))
    a(S("E04", ph, "Gland plate, fan, filter, door",
        "Screw the gland plate under the enclosure, the filter fan on the right side and clip the exhaust grille into the left; "
        "hang the door.", parts=["cabinet.gland_plate", "cabinet.fan", "cabinet.exhaust", "cabinet.door"], path=((0.0, 0.0, 1.0), 100.0, "world"),
        paths={"cabinet.fan": ((-1.0, 0.0, 0.0), 100.0, "world"),
               "cabinet.door": (YW, 100.0, "world"), "cabinet.exhaust": ((1.0, 0.0, 0.0), 20.0, "world")}, tools=["4 mm hex key", "7 mm spanner"]))
    a(S("E05", ph, "Home switches and the front E-stop",
        "Screw the X flags to the substrate at the park position, the X home brackets on the feet's ends, the Y home bracket on "
        "the column web, and set each sensor 4 mm off its target (Z's was fitted with the carriage). Screw the front E-stop box "
        "on the left outrigger's tip.",
        parts=["sensors.x_*", "sensors.y_*", "estop.front_box"], path=((-1.0, 0.0, 0.0), 100.0),
        paths={"sensors.x_flag_*": (TO_BED, 100.0), "estop.front_box": ((1.0, 0.0, 0.0), 100.0, "world")}, tools=["4 mm hex key", "17 mm spanners"]))
    a(S("E06", ph, "Cable ducts",
        "Screw the trunking on the chain tray's rear shelf from the X chain's fixed end to the bed's right end, down the stand's left "
        "upright, and the tray under the cabinet.", parts=["ducts.beam", "ducts.riser", "ducts.tray"], path=((0.0, 0.0, 1.0), 100.0),
        paths={"ducts.beam": ((0.0, -1.0, 0.0), 100.0), "ducts.riser": ((1.0, 0.0, 0.0), 60.0, "world"), "ducts.tray": ((-1.0, 0.0, 0.0), 100.0, "world")},
        tools=["cordless driver"]))
    a(S("E07", ph, "Air: regulator, valves, pop-up pins",
        "Bolt the filter-regulator and the valve manifold through the right upright, behind the cabinet. Screw the 3 pop-up pin cylinders up under "
        "the substrate (pins through its 13 mm holes).", parts=["air.*", "popup.*"], path=((-1.0, 0.0, 0.0), 80.0, "world"),
        paths={"popup.*": ((0.0, 0.0, 1.0), 120.0)}, tools=["4 mm hex key", "8 mm spanner", "cordless driver"]))
    a(S("E08", ph, "Lay the cables and hoses",
        "Lay each cable and hose in the Z, Y and X chains in the order of the cable list (heaviest at the sides, nothing "
        "crossing), tie them at each chain end to its bracket, and run them in the trunking to the gland plate. Leave 300 mm "
        "spare at each end. Clip the trunking lids on.", parts=["cable.*", "hose.*", "ducts.*_lid"], path=None, paths={"*": None},
        pose=g["ASM_PARK"],
        tools=["cable ties", "side cutters"]))
    a(S("E09", ph, "Terminate at the machine",
        "Fit the motor and encoder plugs, the spindle's power, fan and sensor plugs, the brake and the sensors; push the air "
        "hoses into the spindle's fittings and the pop-up pins' tee.", tools=["crimp tool", "screwdrivers"]))
    a(S("E10", ph, "Terminate in the cabinet; mains lead",
        "Through the glands: each cable to its terminals per the wire list, shields to the EMC clamps, PE to the PE bar. Fit "
        "the 3 m mains lead and its 15 A plug.", tools=["ferrule crimper", "screwdrivers", "gland spanners"]))
    a(S("E11", ph, "Electrical tests",
        "Before power: earth continuity < 0.5 ohm to every metal part, insulation resistance > 1 Mohm at 500 V (VFD and drivers "
        "disconnected). Powered: RCBO trip test, both E-stops drop the contactor and the VFD's STO, door E-stop and front "
        "E-stop each break both channels.", tools=["multimeter", "insulation tester", "RCD tester"],
        why="the installation tests AS/NZS 3000 calls for; for an electrician to sign off"))
    # ---------------------------------------------------------------- commissioning
    ph = "Commissioning"
    a(S("M01", ph, "Square the gantry and home",
        "Power the drives. Jog each axis slowly over its travel; set the X home switches so the column sits square to the "
        "rails (measure the diagonal from the column to two rack marks); set the soft limits.",
        tools=["tape", "square"]))
    a(S("M02", ph, "Spoilboard",
        "Screw the two spoilboard boards to the substrate (screw heads 6 mm below the face), then surface the whole board "
        "1 mm deep with a 50 mm surfacing cutter.",
        parts=["bed.spoilboard.*"], path=(TO_BED, 200.0), handle={"people": 2, "method": "carry"}, pose=g["ASM_PARK"],
        tools=["cordless drill", "50 mm surfacing cutter"]))
    a(S("M03", ph, "Tool rack",
        "Fit collets and cutters in the six holders (in the tightening fixture), slide each into its fork, then teach each "
        "pocket position with the spindle.",
        parts=["atc_rack.holder_*"], path=((1.0, 0.0, 0.0), 80.0), pose=g["ASM_PARK"], tools=["ER32 collet spanner", "holder tightening fixture"]))
    a(S("M04", ph, "First tool",
        "With the spindle stopped, press the tool release and push the first holder up into the spindle nose; release.",
        parts=["spindle.holder", "tool"], path=((0.0, 0.0, 1.0), 120.0), pose=g["ASM_PARK"], tools=["ER32 collet spanner"]))
    return steps


# ==================================================================== checks
def match(patterns, names):
    out = []
    for p in patterns:
        out += [n for n in names if fnmatch.fnmatchcase(n, p)]
    return list(dict.fromkeys(out))


def lift_force(step, kg, cg_frac=0.5, length=1.0, pivot_h=0.0):
    """Force each person exerts handling `kg` the step's way: carry, tilt up about one end, slide, or lever."""
    h = step["handle"]
    n = h.get("people", 1 if kg <= KG_PERSON else 2)
    m = h.get("method", "carry")
    if m == "tilt":
        s = max(-1.0, min(1.0, (h["trestle"] - pivot_h) / length))
        return kg * cg_frac * math.cos(math.asin(s)) / n, n, f"tilted up from a {h['trestle']:.0f} mm trestle, {n} at the far end"
    if m == "slide":
        return kg * h.get("mu", 0.3) / n, n, f"slid (friction {h.get('mu', 0.3)}), {n} pushing"
    return kg / n, n, f"carried by {n}"


def check(g, items, require, motor_kg, world_vec):
    """Coverage, lifts and units; returns the steps with what was found, for the page."""
    steps = g["ASM_STEPS"]
    names = [it["name"] for it in items if it["kind"] != "outside"] + list(MOTORS) + list(g.get("CABLE_NAMES", []))
    kg = {it["name"]: it["kg"] for it in items}
    kg.update({m: motor_kg for m in MOTORS})
    kg.update(g.get("EXTRA_KG", {}))
    centre = {it["name"]: it["part"].centre() for it in items}
    bbox = {it["name"]: it["part"].bounding_box() for it in items}
    count = {n: [] for n in names}
    unmatched = []
    for st in steps:
        st["adds"] = match(st["parts"], names)
        for p in st["parts"]:
            if not match([p], names):
                unmatched.append(f"{st['id']}: {p}")
        for n in st["adds"]:
            count[n].append(st["id"])
    # R57: every part fitted in exactly one step
    groups = {}
    for n, where in count.items():
        groups.setdefault(n.split(".")[0], []).append((n, where))
    text = "The assembly procedure shall fit every part in exactly one step (parts not fitted, or fitted twice)"
    for grp, lst in sorted(groups.items()):
        bad = [n for n, w in lst if len(w) != 1]
        require("R57", text, len(bad), "<=", 0, "", case=f"{grp}: {len(lst)} parts" + (f"; {', '.join(bad[:4])}" if bad else ""))
    require("R57", text, len(unmatched), "<=", 0, "", case="step patterns that match no part" + (f": {', '.join(unmatched[:4])}" if unmatched else ""))
    # units: built before they are moved, moved once
    units = {}
    for i, st in enumerate(steps):
        if st["unit"]:
            units.setdefault(st["unit"], {"parts": [], "built": [], "moved": []})
            units[st["unit"]]["parts"] += st["adds"]
            units[st["unit"]]["built"].append(i)
        if st["moves"]:
            units.setdefault(st["moves"], {"parts": [], "built": [], "moved": []})["moved"].append(i)
    for u, d in units.items():
        bad = (len(d["moved"]) != 1) + (not d["built"]) + (bool(d["moved"]) and bool(d["built"]) and max(d["built"]) > d["moved"][0])
        require("R59", "Each bench-built unit shall be finished before it is fitted, and fitted once", bad, "<=", 0, "", case=u)
    # R58: lifts
    installed = set()
    for st in steps:
        loads = []
        loose = [n for n in st["adds"]]
        for n in loose:
            f, k, how = lift_force(dict(st, handle={kk: v for kk, v in st["handle"].items() if kk != "method"}), kg[n])
            loads.append((f, k, how, n, kg[n]))
        if st["moves"]:
            ps = units[st["moves"]]["parts"] + ([] if True else [])
            m = sum(kg[n] for n in ps)
            ax = st["handle"].get("axis", 1)
            pts = [n for n in ps if n in centre]
            lo = min(bbox[n].min()[ax] for n in pts)
            hi = max(bbox[n].max()[ax] for n in pts)
            cg = sum(centre[n][ax] * kg[n] for n in pts) / sum(kg[n] for n in pts)
            pivot_h = g["UNIT_PIVOT_H"].get(st["moves"], 0.0)
            f, k, how = lift_force(st, m, (cg - lo) / (hi - lo), hi - lo, pivot_h)
            loads.append((f, k, how, st["moves"], m))
        if loads:
            f, k, how, what, m = max(loads)
            st["lift"] = dict(kg=round(m, 1), people=k, how=how, what=what, force=round(f, 1))
            require("R58", f"No one shall lift, push or hold more than {KG_PERSON:g} kg in any step ({PEOPLE} people, no hoist)",
                    f, "<=", KG_PERSON, "kg", case=f"{st['id']} {st['title']}: {what}, {m:.1f} kg {how}")
        installed |= set(st["adds"])
    return units


def V_(a, b):
    """Shared volume, robust to golf's occasional failure on touching faces: nudged 3 um and tried again."""
    from golf_py import Location
    for d in ((0, 0, 0), (0.003, 0.002, 0.001), (-0.002, 0.003, -0.002)):
        try:
            return float((a.moved(Location.translation(*d)) & b).volume() if any(d) else (a & b).volume())
        except Exception:
            continue
    return 0.0


# ==================================================================== fasteners and welds
def _bb(part):
    b = part.bounding_box()
    return tuple(b.min()), tuple(b.max())


def _overlap(a, b, pad=0.0):
    return all(a[0][i] - pad <= b[1][i] and b[0][i] - pad <= a[1][i] for i in range(3))


def _gap(a, b):
    return max(0.0, max(max(a[0][i] - b[1][i], b[0][i] - a[1][i]) for i in range(3)))


def check_joints(g, items, require, joints, welds):
    """Every fastener through real holes, with enough thread engaged, its head and nut on material and clear of
    everything else, fitted no earlier than its parts; every weld between parts that touch. Returns per-joint results."""
    import fasteners as FA
    steps = g["ASM_STEPS"]
    step_ix = {st["id"]: i for i, st in enumerate(steps)}
    fitted = {}
    for i, st in enumerate(steps):
        for n in st["adds"]:
            fitted[n] = i
    geo = {it["name"]: it for it in items if it["kind"] != "outside" and it["name"] != "gantry_frame.rope" and it["name"] not in g["CHAIN_SPECS"]}
    bbs = {n: _bb(it["part"]) for n, it in geo.items()}
    names_all = set(fitted)
    tol = 0.5        # mm^3: booleans of touching faces leave slivers
    out = []
    text60 = ("Every joint shall have its fasteners through real holes, enough thread engaged (1.0 d in steel, 1.5 d in 6061), "
              "heads and nuts seated on material and clear of everything else, fitted no earlier than its parts (fasteners failing)")
    for J in joints:
        f, d = J["f"], J["dir"]
        fails = []
        if not J["ok_len"] or not f["L"]:
            fails.append("no standard length fits the grip and hole")
        for n in J["parts"]:
            if n not in names_all:
                fails.append(f"{n} is not in the procedure")
        if J["step"] not in step_ix:
            fails.append(f"step {J['step']} does not exist")
        else:
            late = [n for n in J["parts"] if n in fitted and fitted[n] > step_ix[J["step"]]]
            if late:
                fails.append(f"fastened in {J['step']} before {late[0]} is fitted")
        engaged = []
        if not fails:
            L = f["L"]
            T = J["parts"][-1] if (J["tapped"] or f["type"] in ("TEK", "WOOD", "STUD")) and not f["nut"] else None
            Dh, kh = FA.head_size(f)
            rr = max(Dh / 2, FA.ISO.get(f["d"], (0,) * 8)[6] * 0.6 if f["nut"] else 0.0, f["d"] / 2) + 1.0
            for p in J["pts"]:
                why = []
                q = tuple(p[i] + d[i] * L for i in range(3))
                h0 = tuple(p[i] - d[i] * (kh + 1) for i in range(3))
                fb = (tuple(min(h0[i], q[i], p[i]) - rr for i in range(3)), tuple(max(h0[i], q[i], p[i]) + rr for i in range(3)))
                world_j = geo[J["parts"][0]]["group"] == "world" if J["parts"][0] in geo else False
                cands = [n for n, bb in bbs.items() if _overlap(fb, bb) and n != J["name"] and (geo[n]["group"] == "world") == world_j]
                if f["type"] == "SET":
                    cands = [n for n in cands if n in J["parts"]]
                sh = FA.shank(p, d, f)
                for n in cands:
                    if n == T or (f["type"] == "TEK" and n in J["parts"]):
                        continue
                    v = V_(sh, geo[n]["part"])
                    if v > tol:
                        why.append(f"shank hits {n} ({v:.0f} mm^3)")
                if T and T in geo:
                    if f["type"] in ("TEK", "WOOD", "STUD"):
                        v = V_(sh, geo[T]["part"])
                        e = v / (math.pi * (f["d"] / 2 - 0.05) ** 2) if f["type"] != "STUD" else \
                            v / (math.pi * ((f["d"] / 2 - 0.05) ** 2 - FA.ISO[f["d"]][3] ** 2))
                        need = 2.0 if f["type"] == "TEK" else FA.ENGAGE[J["into"]] * f["d"]
                    else:
                        tap = FA.ISO[f["d"]][3]
                        v = V_(FA.shank(p, d, f, r=tap * 0.95), geo[T]["part"])
                        if v > tol:
                            why.append(f"no tapped hole, or too shallow, in {T} ({v:.0f} mm^3)")
                        vn = V_(sh, geo[T]["part"])
                        e = vn / (math.pi * ((f["d"] / 2 - 0.05) ** 2 - tap ** 2))
                        need = 0.0 if f["type"] == "SET" else FA.ENGAGE[J["into"]] * f["d"]
                    engaged.append(e)
                    if e < need - 0.05:
                        why.append(f"{e:.1f} mm of thread in {T}, needs {need:.1f}")
                hd = FA.head(p, d, f)
                if hd is not None:
                    for n in cands:
                        v = V_(hd, geo[n]["part"])
                        if v > tol:
                            why.append(f"head hits {n}")
                nt = FA.nut(p, d, f, J["grip"])
                if nt is not None:
                    for n in cands:
                        v = V_(nt, geo[n]["part"])
                        if v > tol:
                            why.append(f"nut hits {n}")
                st_ = FA.seat(p, d, f)
                if st_ is not None and J["parts"][0] in geo and f["type"] != "STUD":
                    if V_(st_, geo[J["parts"][0]]["part"]) <= 0.01:
                        why.append(f"head does not bear on {J['parts'][0]}")
                if why:
                    fails.append(why[0])
        lab = f"{len(J['pts'])} x {FA.label(f)}" if f["L"] else f"{len(J['pts'])} x M{f['d']:g}"
        require("R60", text60, len(fails), "<=", 0, "",
                case=f"{J['step']} {J['name']}: {lab}" + (f"; {fails[0]}" if fails else (f"; {min(engaged):.1f} mm engaged" if engaged else "")))
        out.append(dict(J, fails=fails, engaged=min(engaged) if engaged else None))
    textw = "Every weld shall join parts that touch, welded no earlier than both are fitted (welds failing)"
    for W in welds:
        fails = []
        for n in (W["a"], W["b"]):
            if n not in names_all:
                fails.append(f"{n} is not in the procedure")
        if not fails:
            gp = _gap(bbs[W["a"]], bbs[W["b"]]) if W["a"] in bbs and W["b"] in bbs else 0.0
            if gp > 1.0:
                fails.append(f"{gp:.1f} mm apart")
            if W["step"] not in step_ix:
                fails.append(f"step {W['step']} does not exist")
            elif max(fitted[W["a"]], fitted[W["b"]]) > step_ix[W["step"]]:
                fails.append("welded before both parts are fitted")
        require("R65", textw, len(fails), "<=", 0, "", case=f"{W['step']} {W['name']}: {W['how']}" + (f"; {fails[0]}" if fails else ""))
    return out


# ==================================================================== interference, paths and tool access (world frame)
EXEMPT = [("*pinion*", "bed.rack_*"), ("*belt*", "*pulley*"), ("gantry_frame.rope", "*"), ("*chain", "*"), ("tool", "spindle.holder"),
          ("tool", "atc_rack.holder_*"), ("feet.*", "floor_frame.foot_nut_*"), ("cabinet_stand.foot_*", "cabinet_stand.foot_nut_*")]


def _exempt(a, b):
    for p, q in EXEMPT:
        if (fnmatch.fnmatchcase(a, p) and fnmatch.fnmatchcase(b, q)) or (fnmatch.fnmatchcase(b, p) and fnmatch.fnmatchcase(a, q)):
            return True
    return False


def _legs(path):
    if path is None:
        return None
    if isinstance(path, list):
        return [tuple(l) for l in path]
    return [tuple(path)]


class Space:
    """The parts in the world frame with the axes at a given pose (cached)."""

    def __init__(self, g, items, W):
        from golf_py import Location
        self.L, self.W, self.g = Location, W, g
        self.rot = Location.about(*g["TILT_AXIS"])
        self.it = {it["name"]: it for it in items if it["kind"] != "outside"}
        self.cache, self.bbc = {}, {}

    def group(self, n):
        return self.it[n]["group"] if n in self.it else "fixed"

    def off(self, grp, pose):
        R = self.g["REF"]
        dx, dy, dt = pose[0] - R[0], pose[1] - R[1], pose[2] - R[2]
        return {"x": (dx, 0, 0), "xy": (dx, dy, 0), "xyz": (dx, dy, dt), "cw": (dx, -dy / self.g["REEVE"], 0)}.get(grp, (0, 0, 0))

    def part(self, n, pose):
        k = (n, tuple(pose))
        if k not in self.cache:
            it = self.it[n]
            if it["group"] == "world":
                p = it["part"]
            else:
                o = self.off(it["group"], pose)
                p = it["part"].moved(self.W * self.L.translation(*o))
            self.cache[k] = p
            self.bbc[k] = _bb(p)
        return self.cache[k]

    def bb(self, n, pose):
        self.part(n, pose)
        return self.bbc[(n, tuple(pose))]

    def vec(self, v, frame):
        return tuple(v) if frame == "world" else tuple((self.rot * self.L.translation(*v)).position())

    def pt(self, p, grp, pose):
        if grp == "world":
            return tuple(p)
        o = self.off(grp, pose)
        return tuple((self.W * self.L.translation(*(p[i] + o[i] for i in range(3)))).position())


def check_space(g, items, require, joints, W):
    """R66: nothing overlaps in the built machine. R61: each part's path into place is clear of what is already there.
    R62: each fastener's tool reaches it at its step. All in the world frame, with the axes where each step puts them."""
    import fasteners as FA
    from golf_py import Location
    SP = Space(g, items, W)
    steps = g["ASM_STEPS"]
    names = sorted(SP.it)
    fitted, unit_of, moved_at = {}, {}, {}
    for i, st in enumerate(steps):
        for n in st["adds"]:
            fitted[n] = i
            if st["unit"]:
                unit_of[n] = st["unit"]
        if st["moves"]:
            moved_at[st["moves"]] = i
    tol = 1.0
    P0 = tuple(g["ASM_POSE0"])          # the built machine, head up mid-bed
    # ---- R66: the built machine
    text66 = "No two parts shall overlap in the built machine (shared volume, mm^3; meshing teeth, belts on pulleys, chains and rope excepted)"
    worst = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if _exempt(a, b) or not _overlap(SP.bb(a, P0), SP.bb(b, P0), 0.01):
                continue
            v = V_(SP.part(a, P0), SP.part(b, P0))
            if v > tol:
                worst.setdefault(a.split(".")[0], []).append((v, f"{a} and {b}"))
    for grp in sorted({n.split(".")[0] for n in names}):
        lst = sorted(worst.get(grp, []), reverse=True)
        require("R66", text66, lst[0][0] if lst else 0.0, "<=", tol, "mm^3", case=f"{grp}: " + (lst[0][1] + f" (+{len(lst) - 1} more)" if lst else "clear"))

    def present(i, u, upto):
        """Parts already there at step i (upto: include step i itself)."""
        out = []
        for n, j in fitted.items():
            if n not in SP.it or (j > i or (j == i and not upto)):
                continue
            if u:
                if unit_of.get(n) == u:
                    out.append(n)
            elif unit_of.get(n) is None or moved_at.get(unit_of[n], 1e9) < i or (upto and moved_at.get(unit_of[n], 1e9) == i):
                out.append(n)
        return out
    # ---- R68: the electrical and air parts over the whole travel: moving ones clear of what stands still, and the reverse
    text68 = ("The cabinet, stand, ducts, sensors, E-stop and air parts shall clear every moving part over the whole travel "
              "(shared volume, mm^3, worst of 12 poses)")
    newp = tuple(g["E_PREFIXES"])
    T0, T1 = g["X_TRAVEL"]
    poses = [(x, y, t) for x in (T0, (T0 + T1) / 2, T1) for y in g["Y_WORK"] for t in (g["TIP_MIN"], g["ZN_MAX"] - g["TIP_TO_NOSE"])]
    moving = [n for n in names if SP.group(n) in ("x", "xy", "xyz", "cw")]
    still = [n for n in names if SP.group(n) in ("fixed", "world")]
    w68 = {}
    for P in poses:
        for a_ in moving:
            for b_ in still:
                if not (a_.startswith(newp) or b_.startswith(newp)) or _exempt(a_, b_):
                    continue
                if not _overlap(SP.bb(a_, P), SP.bb(b_, P), 0.01):
                    continue
                v = V_(SP.part(a_, P), SP.part(b_, P))
                k = (b_ if b_.startswith(newp) else a_).split(".")[0]
                if v > w68.get(k, (0, ""))[0]:
                    w68[k] = (v, f"{a_} and {b_} at x {P[0]:.0f}, y {P[1]:.0f}, tip {P[2]:.0f}")
    for k in sorted({n.split(".")[0] for n in names if n.startswith(newp)}):
        v, c = w68.get(k, (0.0, "clear"))
        require("R68", text68, v, "<=", tol, "mm^3", case=f"{k}: {c}")
    # ---- R61: paths
    text61 = "Every part shall reach its place along its stated path without touching what is already fitted (shared volume, mm^3)"
    for i, st in enumerate(steps):
        pose = tuple(st["pose"] or g["ASM_POSE0"])
        movers = []
        if st["moves"]:
            movers.append(([n for n in g["ASM_UNITS"][st["moves"]]["parts"] if n in SP.it], st["path"]))
        for n in st["adds"]:
            if n not in SP.it:
                continue
            p = st["path"]
            for pat, q in st["paths"].items():
                if fnmatch.fnmatchcase(n, pat):
                    p = q
            movers.append(([n], p))
        worst_v, worst_c = 0.0, "clear"
        for parts, path in movers:
            legs = _legs(path)
            if not legs:
                continue
            world = all(SP.group(n) == "world" for n in parts)
            vs = [tuple(c * l[1] for c in SP.vec(l[0], l[2] if len(l) > 2 else ("world" if world else "local"))) for l in legs]
            offs, cur = [], [-sum(v[k] for v in vs) for k in range(3)]
            for v in vs:
                for t in (0.0, 0.34, 0.67):
                    offs.append(tuple(cur[k] + v[k] * t for k in range(3)))
                cur = [cur[k] + v[k] for k in range(3)]
            last = vs[-1]
            n_l = math.sqrt(sum(c * c for c in last)) or 1.0
            offs.append(tuple(-last[k] / n_l * 0.6 for k in range(3)))
            there = [n for n in present(i, st["unit"], False) if n not in parts]
            for o in offs:
                T = Location.translation(*o)
                for n in parts:
                    bb = SP.bb(n, pose)
                    sbb = (tuple(bb[0][k] + o[k] for k in range(3)), tuple(bb[1][k] + o[k] for k in range(3)))
                    moved = None
                    for m in there:
                        if _exempt(n, m) or not _overlap(sbb, SP.bb(m, pose), 0.01):
                            continue
                        moved = moved or SP.part(n, pose).moved(T)
                        v = V_(moved, SP.part(m, pose))
                        if v > worst_v:
                            worst_v, worst_c = v, f"{n} hits {m}"
        require("R61", text61, worst_v, "<=", tol, "mm^3", case=f"{st['id']} {st['title']}: {worst_c}")
    # ---- R62: tool access, at the step each fastener is tightened
    text62 = ("Every fastener shall be reachable by its tool at the step it is tightened: a hex key straight down its axis for the "
              "key's short arm, a socket or a spanner from some side on nuts (shared volume, mm^3)")
    step_ix = {st["id"]: i for i, st in enumerate(steps)}

    def hits(solid, there, pose):
        cb = _bb(solid)
        v = 0.0
        hit = None
        for m in there:
            if not _overlap(cb, SP.bb(m, pose), 0.01):
                continue
            w = V_(solid, SP.part(m, pose))
            if w > v:
                v, hit = w, m
        return v, hit
    for J in joints:
        f, d = J["f"], J["dir"]
        if f["type"] == "STUD" or not f["L"] or J["step"] not in step_ix:
            continue
        i = step_ix[J["step"]]
        st = steps[i]
        pose = tuple(st["pose"] or g["ASM_POSE0"])
        grp = SP.group(J["parts"][0]) if J["parts"][0] in SP.it else {"gantry_drives": "x", "y_carriage": "xy"}.get(J["parts"][0].split(".")[0], "fixed")
        there = present(i, st["unit"], True)
        dw = SP.vec(d, "world" if grp == "world" else "local")
        Dh, kh = FA.head_size(f)
        if f["type"] == "LHCS":
            key = FA.LOW[f["d"]][2]
        else:
            key = FA.ISO[f["d"]][2] if f["d"] in FA.ISO else 4.0
        arm = FA.KEY_SHORT.get(key, 30.0)
        worst_v, worst_c = 0.0, "clear"
        for p in J["pts"]:
            pw = SP.pt(p, grp, pose)
            ends = []
            if f["type"] in ("SHCS", "LHCS", "SET"):
                ends.append(("hex key", [FA._along(pw, dw, key / 2 + 0.8, -(kh + arm), -(kh + 0.3))]))
            elif f["type"] == "CSK":
                ends.append(("hex key", [FA._along(pw, dw, key / 2 + 0.8, -arm, -0.3)]))
            elif f["type"] in ("TEK", "WOOD"):
                ends.append(("driver", [FA._along(pw, dw, 4.0, -100.0, -0.3)]))
            if f["type"] == "HEX" or f["nut"]:
                # a nut or hex head: a socket on its axis, or an open spanner from any of 8 sides
                if f["nut"]:
                    z0 = J["grip"] + 0.5 + (1.6 if f["washer"] else 0.0)
                    z1 = z0 + FA.ISO[f["d"]][7]
                    sock = FA._along(pw, dw, FA.ISO[f["d"]][6] * 0.85, z1 + 0.3, z1 + 40.0)
                else:
                    z0, z1 = -kh, 0.0
                    sock = FA._along(pw, dw, FA.ISO[f["d"]][6] * 0.85, -(kh + 40.0), -(kh + 0.3))
                c = tuple(pw[k] + dw[k] * (z0 + z1) / 2 for k in range(3))
                ax = (1.0, 0.0, 0.0) if abs(dw[0]) < 0.9 else (0.0, 1.0, 0.0)
                u_ = (dw[1] * ax[2] - dw[2] * ax[1], dw[2] * ax[0] - dw[0] * ax[2], dw[0] * ax[1] - dw[1] * ax[0])
                nu = math.sqrt(sum(x * x for x in u_))
                u_ = tuple(x / nu for x in u_)
                w_ = (dw[1] * u_[2] - dw[2] * u_[1], dw[2] * u_[0] - dw[0] * u_[2], dw[0] * u_[1] - dw[1] * u_[0])
                sides = [sock]
                for kk in range(8):
                    ang = math.pi * kk / 4
                    rdir = tuple(u_[q] * math.cos(ang) + w_[q] * math.sin(ang) for q in range(3))
                    s0 = FA.ISO[f["d"]][6] * 0.7
                    sides.append(FA._along(tuple(c[q] + rdir[q] * s0 for q in range(3)), rdir, (z1 - z0) / 2 + 0.3, 0.0, 60.0))
                ends.append(("spanner", sides))
            for what, options in ends:
                best = None
                for sol in options:
                    v, m = hits(sol, there, pose)
                    if best is None or v < best[0]:
                        best = (v, m)
                    if v <= tol:
                        break
                if best[0] > worst_v:
                    worst_v, worst_c = best[0], f"{what} hits {best[1]}"
        require("R62", text62, worst_v, "<=", tol, "mm^3", case=f"{J['step']} {J['name']}: {FA.tool(f)}; {worst_c}")
