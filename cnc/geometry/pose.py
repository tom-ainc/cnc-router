"""The envelopes posed for display, and the pose the detailed moving groups are drawn at."""
from cnc.params import TIP_MIN
from cnc.geometry.bed import atc, bed, rack_b, rack_t, rail_b, rail_t, spoil, substrate, xchain
from cnc.geometry.moving import gantry, head

POSE = (1200.0, 600.0, TIP_MIN + 100)
g_frame, g_other = gantry(POSE[0])
h_car, h_z, h_sp, h_tool = head(*POSE)
fixed_local = {"bed": bed, "substrate": substrate, "spoilboard": spoil, "rail_bottom": rail_b, "rail_top": rail_t, "x_chain": xchain,
               "rack_bottom": rack_b, "rack_top": rack_t, "atc_rack": atc}
# (the envelopes above are the clash-check solids; the detailed parts are shown, see "detailed parts" below)
REF = (0.0, 0.0, TIP_MIN)      # the pose the moving groups are drawn at; the viewer moves them from here
