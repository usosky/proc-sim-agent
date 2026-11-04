PASS if the answer frames the job before any click paths and covers most of these:
- scope and boundary of the model (what is in, what is out, the hand-over stream);
- a data card: each value with its source (table, figure, own calculation) and a status such as
  data, assumed or bound; values read from Fig. 5 marked as read from a plot; the missing heat
  losses listed as assumptions that become data requests;
- what Aspen can and cannot represent here (for example equilibrium against rate-based stages,
  and what stays outside the model);
- expected values from an independent check before the first run, with tolerances;
- versions and gates: small steps (one change per version), a first gate where the paper's case is
  reproduced, the plant basis only after that, a frozen version that is not edited;
- it asks before writing a build guide or status file into the user's folders.

FAIL if it starts with a complete click-path build of the whole flowsheet without framing, invents
numbers from the paper, or skips the reproduce-the-paper gate.
