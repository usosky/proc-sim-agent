---
description: Inline Fortran with column, tab and import-assignment problems
tags: [calculator, fortran]
---

My calculator gives a Fortran error when I leave the Calculate sheet, and before that I also got
"FORTRAN READ-VAR TR ... APPEARS ON THE LEFT-HAND SIDE OF AN ASSIGNMENT STATEMENT". TR and PR are
Import variables, XOUT is the Export. The code (copied exactly; the second line starts with a tab):

```
IF (TR .LT. 250.0D0) TR = 298.15D0
	RATE = AK * DEXP(-EA / (8.314D0 * TR)) * PR
      XOUT = RATE * TAU / (1.0D0 + RATE * TAU) + CORRECTIONFORPRESSURE * PRESSUREDEPENDENCETERM
```

What is wrong and what should the code look like?
