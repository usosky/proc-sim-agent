---
description: Design spec convergence block deleted because a calculator has an explicit sequence
tags: [messages, calculator, design-spec, sequencing]
---

I added a design spec PURITY that varies Parameter 3 (RECFRAC, the recycle fraction) to reach
99.5 mol% in the product. RECFRAC is read by my calculator RECYC, whose Sequence sheet says Execute
Before block SPLIT-1. Now the run stops before calculating:

```
      **  ERROR DURING FLOWSHEET ANALYSIS
          SPEC PURITY VARY VARIABLE DOWNSTREAM OF SAMPLED
          VARIABLES OR NEED READ-VAR FOR VARY VARIABLE.
          CONVERGENCE BLOCK $OLVER02 WILL BE DELETED.

      **  ERROR DURING FLOWSHEET ANALYSIS
          YOUR PROBLEM WILL NOT RUN BECAUSE OF ERRORS
          FOUND DURING FLOWSHEET ANALYSIS.
```

What is wrong and what exactly should I change?
