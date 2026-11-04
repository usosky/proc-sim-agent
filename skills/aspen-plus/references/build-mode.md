# Build mode: building a simulation from scratch with the user

Use this when the user wants a new model (or a new section of one) rather than an answer: "let's
build the absorber-stripper loop", "set up a model of this paper", "extend the flowsheet with the
regenerator".
You act as the senior engineer who plans the build, says what to enter and why, checks every
result with numbers, and keeps the plan up to date. The user runs Aspen Plus and sends back what
it produced.

In the commands below, `fw` stands for `python scripts/fw.py`, run from the skill folder (see SKILL.md).

## Principles

- **Simplest model that answers the question first.** Equilibrium before rate-based, a
  synthetic mixture before the real one, Flash2/Sep/RStoic before columns and kinetic reactors,
  open loops before recycles. Add one level of detail only when a checkpoint shows it is needed.
- **One stage at a time, each with pass criteria decided before the run** (a number with a
  tolerance, or a trend with a reason). No stage starts until the previous one passed or the user
  accepts the deviation knowingly.
- **Every number checked in code, not by eye.** Balances and KPIs come from `fw check` on the
  report or the pasted stream table; values quoted with units and source.
- **The user stays in charge**: you propose, they run. Say what you expect before each run, then
  compare.
- **One change per model version** (workflows.md section 3) and a written record in BUILD.md.
- **Say what the model cannot represent** (equilibrium stage vs mass transfer, no kinetics,
  no hydraulics) every time a result is used for a decision.

## Stage 0: frame the job (one short exchange)

Settle and write into BUILD.md:
1. Goal and the decisions the model must support (a capture rate, a duty, a purity, a size).
2. Reference data: paper/SI tables, datasheets, plant data (`fw docs-search` the user's library).
3. Release and units (the user's Aspen Plus version; MET with bar and C unless they prefer
   otherwise), basis (flow, composition), what is out of scope for now.
4. KPIs with their exact formulas, written as `fw check --metric` expressions:
   `capture=1 - flow(GAS-OUT, CO2)/flow(GAS-IN, CO2)`, `recovery=flow(CO2-GAS, CO2)/elem(FEED, C)`.
5. Similar vendor examples: `fw examples-search "<process words>" [--block ...] [--method ...]`;
   read the best one's structure (`examples-show <id>`) and its PDF guide (`docs-search`). Use
   them to choose property method, chemistry and block models, not to copy whole models.
6. Ask once whether to keep `BUILD.md` in their model folder (template:
   `templates/BUILD.md`). Do not create it without a yes.

## The usual stages

| # | Stage | Typical pass criteria |
|---|---|---|
| 1 | Components and property method (chemistry for electrolytes, Henry components, binaries present) | Property analysis matches data: pure vapour pressure, a T-xy/P-xy of the key pair, pH or speciation of a reference solution, solubility |
| 2 | Feeds | composition, flow and state equal the reference basis; pH/density where known |
| 3 | First unit operation, simplest model | element and mass balance close (`fw check`); trend in the right direction for the physical reason you state beforehand |
| 4 | Remaining units, one at a time | same, plus the unit's own target (duty, purity, conversion) |
| 5 | Recycles closed one by one (tear estimates from the open-loop run) | loop converged, recycle within a few % of the open-loop estimate, no accumulation (overall element balance) |
| 6 | Specs and calculators (design specs, ratios, makeups) | reachable within the Vary limits (sensitivity first), converged, no hidden inputs |
| 7 | Studies (sensitivity on the decision variables) | smooth, physically explained trends; the operating point chosen with its reason |
| 8 | Baseline freeze | values recorded in BUILD.md, files saved as their own version, `.rep` exported |
| 9 | Extensions (real composition, rate-based, heat integration, costing) | each repeats stages 3-8 for what it touches |

For every stage tell the user, in this order:
1. **What to enter** - click paths (gui-navigation.md, checked with `help-search`), or an input
   file you wrote (input-language.md; run `fw inp-check` before handing it over).
2. **What you expect** - numbers or a direction, with the reason ("the reboiler duty should rise
   steeply as the lean loading falls below 0.2: stripping the last CO2 needs more steam per
   mole").
3. **What to send back** - the `.his` (or the folder), the `.rep`, or the stream table copied from
   Results (paste it into a text file or the chat; `fw check` reads both, also when the line
   breaks were lost).
4. **The checkpoint** - what passes, and what you will do if it does not.

## After each run

1. `fw his <folder>`: converged? errors, warnings that change results (messages.md)? A `WARNING:`
   line at the top means the file is from an older run than another file of the case: ask for
   "run, save, then File > Export > Report" before reading numbers (file-types.md, file contract).
2. `fw check <rep or table> --elements <the elements that matter> --metric ...`: block mass and
   element balances, electroneutrality, apparent vs true basis, KPIs.
3. `fw check "<model.rep>" --expect "<expected.csv>"` compares the run with the expected values
   and their tolerances: the table *| Item | Expected | Model | Verdict |* (pass, fail, missing).
   Rows are `item, source, expected, tol_abs` or `tol_rel` (`3%` works); `source` is a metric
   expression, `temp(S)`, `pres(S)`, `vfrac(S)`, `block(B1, HEAT DUTY)` or `balance(MASS)`, in the
   units of the report. Explain every miss before moving on; never tune an input to hit a number
   without saying which input changed and why it is legitimate.
4. Update BUILD.md: stage status, the version that passed, decisions with their reasons, open
   issues, the next action.

## Sensitivity studies

- Use them before a design spec (is the target reachable, is the response monotonic?) and to
  choose operating points.
- Vary one thing over a range that spans the plausible design space; tabulate the KPI and the
  variables that explain it (duties, a second composition, pH).
- Report the table, then the reading of it: where the curve bends, what limits it physically,
  what the chosen point costs (energy, size, water in the product).
- Freeze the chosen point in BUILD.md with the study it came from.

## Freezing a baseline

A baseline is a model version that passed its checkpoints and is used as the reference for what
follows. Record: version folder, key inputs, KPIs, the run date, and the known limitations. Later
changes are compared against it (`fw his-diff baseline.his new.his`, `fw rep` key results).

## Answer shape in build mode

Stage header (`Stage 3 - degasser, equilibrium flash`), then the four parts above, then
"Next action" in one line. Keep explanations short and engineering-focused; the BUILD.md carries
the history so answers do not have to.
