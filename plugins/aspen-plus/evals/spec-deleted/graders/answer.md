---
type: llm
weight: 3
---

PASS if the answer:
- identifies the explicit execution point of calculator RECYC (Execute Before SPLIT-1) as the cause:
  with an explicit sequence Aspen does not use RECYC's Import/Export list for ordering, so it sees no
  path from the varied Parameter RECFRAC to the sampled variable and deletes the spec's convergence
  block;
- tells the user to set RECYC's Sequence sheet to "Use import/export variables" while keeping RECFRAC
  as an Import on the Define sheet;
- says to rerun (Reinitialize, then Run) and check the new computation order, and that the second
  error disappears because it is only a consequence of the first.

FAIL if the main fix is something else (more iterations, different tear streams, deleting the
spec, changing tolerances) or if it says the second error is an independent problem.
