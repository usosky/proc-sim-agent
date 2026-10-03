---
description: RStoic conversion scaled down because a calculator sets it too high (URE07.3)
tags: [messages, calculator]
runs: 3
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---

My Aspen Plus V15 run finishes, but the history file shows this warning in every iteration, and
there is no hydrogen at all in the reactor outlet:

```
  *   WARNING WHILE EXECUTING UNIT OPERATIONS BLOCK: "R-101" (MODEL: "RSTOIC")
                                                               (URE07.3)
      COMPONENT "H2" HAS ZERO FLOWRATE IN THE OUTLET STREAM.
      FRACTIONAL CONVERSION HAS BEEN MODIFIED BY
      A FACTOR OF "0.8721400"
```

R-101 has one reaction, A + H2 -> B, with the conversion based on component A. The conversion is
written by a Fortran calculator called KIN from a kinetic correlation. What does the warning mean
and how do I fix it properly?
