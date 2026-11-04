---
description: Parameter initialised only in a deactivated calculator gives a missing value and huge flows
tags: [messages, parameters]
runs: 3
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---

I deactivated an old calculator OLDCALC (its job is now done by calculator MAKEUP) and the run
now gives nonsense:

```
    *  WARNING
       SAMPLED VARIABLE 'KFACT' HAS NOT BEEN CALCULATED.
       VALUE IS MISSING.

    *  WARNING
       STREAMS CROSSING THE LOOP CONVERGED BY $OLVER01 ARE NOT IN MASS BALANCE:
       MASS INLET FLOW = 0.48210376E+24, MASS OUTLET FLOW = 0.31477902E+25
```

KFACT is Parameter 2 and MAKEUP reads it. Why are the flows around 1E24 kg/s and how do I fix it?
