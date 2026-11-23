"""R1-R5: the sheet and travels."""
import math
from cnc.params import TILT, TIP_MIN, TIP_TO_NOSE, X_TRAVEL, X_WORK, YCH, Y_RAIL, Y_WORK, ZN_MIN, Z_TRAVEL, Z_TRAVEL_REQ
from cnc.geometry.world import wpt
from cnc.system.requirements import require

require("R1", "X travel shall put the tool centre past both 2400 mm sheet edges by tool radius + 3 mm",
        min(X_WORK[0] - X_TRAVEL[0], X_TRAVEL[1] - X_WORK[1]) if X_TRAVEL[0] <= X_WORK[0] else -1, ">=", 0, "mm")
require("R2", "Y travel shall put the tool centre past both 1200 mm sheet edges by tool radius + 3 mm",
        min(Y_WORK[0] - (Y_RAIL[0] + YCH), (Y_RAIL[1] - YCH) - Y_WORK[1]), ">=", 0, "mm")
require("R3", "Z travel shall be at least 300 mm", Z_TRAVEL, ">=", Z_TRAVEL_REQ, "mm")
n_bed = wpt(0, 0, 100)
o_bed = wpt(0, 0, 0)
tilt_meas = math.degrees(math.atan2(n_bed[2] - o_bed[2], o_bed[1] - n_bed[1]))   # normal's angle above horizontal
require("R4", "The bed shall lean back 10 deg from vertical", tilt_meas, "==", TILT, "deg", tolerance=0.01)
require("R5", "The tool shall reach 2 mm into the spoilboard", ZN_MIN - TIP_TO_NOSE, "<=", TIP_MIN, "mm")
