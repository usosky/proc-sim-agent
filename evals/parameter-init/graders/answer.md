---
type: llm
weight: 3
---

PASS if the answer:
- explains that Parameter 2 (KFACT) most likely had its initial (Init) value only in the deactivated
  calculator OLDCALC, so no active block gives it a value and Aspen uses its missing-value
  placeholder (a very large number), which is why the flows computed from it explode;
- fixes it by entering the Init value for KFACT in an active block (for example MAKEUP's Define
  sheet, KFACT row, initial value), then Reinitialize and Run;
- gives the general rule: when deactivating a block, move the Init values of the Parameters it
  defined to an active block.

FAIL if it blames convergence settings or tear tolerances as the main cause, or suggests only more
iterations.
