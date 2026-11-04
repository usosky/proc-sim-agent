PASS if the answer does all of the following:
- explains that the conversion written by calculator KIN asks for more H2 than the RStoic feed
  contains, so RStoic scales the conversion down by the printed factor and H2 leaves with zero flow;
- fixes it in KIN by capping the conversion at what the H2 feed can supply (H2 flow divided by the
  flow of A, for this 1:1 stoichiometry), ideally with a small margin such as 0.999 so H2 is not
  exactly zero;
- says the flows of A and H2 must be defined on the calculator's Define sheet as Import variables
  of type Mole-Flow (component flows, not the total Stream-Var MOLE-FLOW) before they are used;
- gives the click path or the Fortran lines (fixed form, column 7) needed.

FAIL if it only suggests ignoring the warning, loosening tolerances or adding iterations, or if it
invents a different meaning for URE07.3.
