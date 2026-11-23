"""The product tree: the product, its parts, and the things outside it."""
from se import outside, part, product

product("Tilted-bed CNC router, 2400 x 1200", task="new_design")
N_BED = part("BED", "Bed: steel ladder frame, MDF spoilboard, X rails and racks", material="Steel", shows=["bed", "substrate", "spoilboard", "rail_bottom", "rail_top", "rack_bottom", "rack_top", "x_chain"])
N_GAN = part("GAN", "Gantry: box column with a 2:1 Y counterweight inside, feet on 2 x HGR25 X rails, 2 x NEMA34 rack drive", material="Steel", shows=["gantry_frame", "gantry_drives", "x_motors", "x_motor_top", "y_motor", "counterweight"])
N_YC = part("YC", "Y carriage on 2 x HGR25 rails, SFU2520 screw, 30T:20T belt step-up, NEMA34, 24 V brake", shows=["y_carriage", "z_motor"])
N_ZA = part("ZA", "Z axis: plate on 2 x HGR25, SFU2010 with 40T:20T belt step-up, NEMA34", shows=["z_axis"])
N_SP = part("SP", "Salvaged 9 kW ISO30 ATC spindle, 380 V 3-ph 800 Hz", shows=["spindle", "tool"], bought=True)
N_ATC = part("ATC", "Linear tool rack beside the sheet", shows=["atc_rack"])
N_BASE = part("BASE", "Floor frame with front outriggers, rear posts, levelling feet", material="Steel", shows=["floor_frame", "feet"])
N_ELEC = part("ELEC", "Cabinet: new Delta MS300 2.2 kW 1-ph VFD (space left for a 11 kW 400 V one), salvaged PSUs, drivers, controller, E-stop")
outside("floor", "levelling feet on a concrete slab")
outside("supply", "one 240 V 15 A single-phase socket circuit", keeps="input current <= 15 A", kind="electrical")
outside("sheet", "2400 x 1200 sheet, up to 25 mm, leaning on the bed on pop-up pins", keeps="position while cut")
outside("operator", "loads sheets from the front with the gantry parked at the left end")
outside("air", "compressed air 6 bar for ATC, pop-up pins and spindle taper blow", kind="fluid")
outside("dust", "dust hood on the Z plate to a collector on its own circuit", kind="fluid")
