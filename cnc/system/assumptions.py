"""Assumptions the requirements rest on."""
from se import assume
from cnc.params import CLAMP_H, STOCK_T, TILT, TOOL_D

assume(f"Bed tilt is {TILT:g} deg from vertical", why="answer to a question; the sketch shows 20 deg (110 deg)")
assume(f"The 300 on the sketch is the Z travel", why="it is labelled '(Z-travel) 300'")
assume(f"Stock up to {STOCK_T:g} mm, cutter up to {TOOL_D:g} mm, workholding no taller than {CLAMP_H:g} mm", why="not given")
assume(f"One 60 V 350 W supply per driver", why="user confirmed: four supplies, one per motor").confirmed = True
assume("Motor torque follows the published 48 V DM860T pull-out curve", why="the 60 V supplies and the closed-loop drivers differ from the test")
assume("Spindle is the 380 V version: 17.8 A rated, 29 kg, no-load current 35 % of rated", why="user's correction; figures from the same-body GDZ143x133-9")
assume("On a future 3-phase supply the largest cut is a 25 mm cutter, 25 mm deep, at 10 m/min and 12 000 rpm", why="the steppers' speed, not the spindle, caps it")
assume("Dust collector and compressor run on other circuits", why="the 15 A circuit cannot also carry them")
assume("Rapids X 15, Y 10, Z 5 m/min; 1 m/s^2; 300 N cutting force at 6 m/min", why="hobby router targets, not given")
assume("The X and Z cable chains may stand above 1800 mm; the ceiling is 2400 mm",
       why="user: the 1800 mm limit is for assembly and operating ergonomics; Y can be jogged down to work on the Z chain. Ceiling not given")
assume(f"The head may overhang the floor frame while cutting; parked at the left end it sits in the room's corner",
       why="user accepted the 1342 mm cutting envelope")
assume("Sheet is located on retractable (pop-up) pins along its bottom edge, so the cutter can profile that edge", why="a fixed ledge would be cut")
