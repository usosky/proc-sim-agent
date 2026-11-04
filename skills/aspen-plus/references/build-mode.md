# Build mode: building a model with the user

Use this when the user wants a new model, or a new section of one, rather than an answer: "set up a
model of this paper", "build the absorber-stripper loop", "extend the flowsheet with the
regenerator". You act as the senior engineer: you frame the job, write the build guide with check
values, say what to enter and why, review every run with numbers and keep the status document up
to date. The user runs Aspen Plus and sends back the files.

In the commands below, `fw` stands for `python scripts/fw.py`, run from the skill folder (see SKILL.md).

## Principles

- **Simplest model that answers the question first**: equilibrium before rate-based, Flash2, Sep
  and RStoic before columns and kinetic reactors, open loops before recycles. Add detail only when
  a check shows it is needed.
- **Expected values before every run**, from an independent check model, with tolerances.
- **One change per version**, run after every step, one folder per version (workflows.md section 3).
- **Every number checked in code, not by eye**: `fw check` on the report, never retyped tables.
- **The user stays in charge**: you propose, they run. Say what the model cannot represent each
  time a result is used for a decision.

## The method

| Step | What | Kept in |
|---|---|---|
| 1 | Frame the job in one exchange | build guide, section 1 |
| 2 | Data card: every value with its source and status | `data-card.md` |
| 3 | What Aspen can and cannot represent | build guide, section 3 |
| 4 | Expected values from a check model, before any run | build guide, section 4; `expected.csv` |
| 5 | Versions and gates | build guide, section 5 |
| 6 | Instructions for each step | build guide, section 6 |
| 7 | Gate acceptance | build guide, section 7 |
| 8 | Run review after every run | the answer; `STATUS.md` |
| 9 | Living status document | `STATUS.md` |
| 10-13 | Modelling rules, sensitivities, next steps, checks before delivery | below |

Templates: `templates/build-guide.md`, `templates/status.md`, `templates/data-card.md`,
`templates/expected.csv`, `templates/fortran-calculator.txt`. Ask once whether to keep them in the
user's model folder; never create files there without a yes.

## 1. Frame the job (one exchange)

Settle, and write into section 1 of the build guide:
- the scope boundary and the interface stream ("capture unit only, from intake to the raw product
  at the battery limit; that stream is the hand-over to the downstream model");
- the decisions the model must support, and the KPIs with exact formulas written as
  `fw check --metric` expressions (`capture=1 - flow(GAS-OUT, CO2)/flow(GAS-IN, CO2)`);
- the references and what each provides (`fw docs-search` the user's library);
- conventions: release, unit set, version numbering, folder, file and case names;
- the differences from a sibling model, each with its reason, in a table;
- what is out of scope.

Similar AspenTech examples show how a process is usually set up: `fw examples-search "<process
words>"`, then `examples-show <id>` and its PDF guide (examples.md). Use them to choose property
methods, chemistry and block models, not to copy models.

## 2. Data card

A table: item | value in the model | source (paper table or figure, SI, datasheet, own calculation)
| status (data, vendor, assumed, model, bound). Check the card against raw data where possible
(point | data | card | deviation). Say when a value was read from a plot. Every assumed line later
becomes a data request (step 12).

## 3. What Aspen can and cannot represent

A table: phenomenon | in Aspen? | how we represent it | what stays outside. Decide the
calculators here: only where Aspen has no block. Name the limits that matter for the decision
(equilibrium stages instead of mass transfer, no kinetics, no hydraulics, no dynamics).

## 4. Expected values before any Aspen run

- Build an independent check model (Python, or a workbook; established property libraries where
  they fit). Compile every Fortran calculator and run it in a harness: `fw fortran-check "<file>"`
  lints it and compiles it with gfortran when gfortran is installed (calculators.md section 10).
- Give a check value with a tolerance for every step: about 0.1 % on calculator outputs and flows;
  about 3 % on duties and machine powers where Aspen's property method differs from the check model.
- Test the calculators' edge cases before delivery: extreme inputs, zero flows, under-specified
  steps.
- Write the check values of each version into `expected.csv`; after the run
  `fw check "<model.rep>" --expect "expected.csv"` gives the review table.

## 5. Versions and gates

- Steps v0.01, v0.02 ...: one change per version, run after every step, Save As the next version,
  one folder per version.
- **v1.00 gate**: the reference is reproduced (paper, vendor or validation case).
- **v1.0x**: the project basis (site, feed, auxiliaries, machines, scale, reporting).
- **v2.00 gate**: frozen, with acceptance checks.
- Never edit a gate file. A `FROZEN` file in a gate's folder (or the version marked frozen in
  STATUS.md) makes `com-run`, `com-sweep` and `com-edit` refuse it.
- Keep a **case-input table** (the only values that change between case files of one version) and
  a list of design inputs, changed only as a deliberate sensitivity.

Typical steps before the v1.00 gate:

| Step | Adds | Usual check |
|---|---|---|
| 1 | components and property method (chemistry, Henry components, binaries) | property analysis against data: vapour pressure, T-xy of the key pair, pH of a reference solution |
| 2 | feeds | composition, flow and state equal the reference basis |
| 3 | first unit, simplest model | mass and element balance (`fw check`); the trend you predicted, for the reason you gave |
| 4 | the other units, one at a time | the same, plus the unit's own target (duty, purity, conversion) |
| 5 | recycles, closed one by one (tear estimates from the open-loop run) | loop converged, recycle within a few % of the open-loop estimate, overall element balance |
| 6 | design specs and calculators | target reachable within the vary limits (sensitivity first), converged, no hidden inputs |
| 7 | the reference case | the gate table (step 7) |

## 6. Instructions for each step

Each step in the build guide has, in this order:
1. "Save As `<MODEL>_vX.YY`" in its folder.
2. Numbered click paths with exact values and units (gui-navigation.md; check unfamiliar forms
   with `fw help-search`), or an input file you wrote and checked (`fw inp-check`,
   input-language.md).
3. The check values, with tolerances, and what you expect with the reason ("the reboiler duty
   rises steeply below a lean loading of 0.2: stripping the last CO2 needs more steam per mole").
4. What to do if a value is off.

Calculator Fortran is delivered as a separate file per version, `<MODEL>_vX.Y_fortran.txt`, made
from `templates/fortran-calculator.txt` and pasted as plain text, never inside prose. State the
units on every Define row: the code sees those units (calculators.md section 1).

## 7. Gate acceptance

A table of checks with their pass condition: the control panel (0 errors; which warnings are
acceptable and why); the overall flowsheet balance (relative difference threshold,
`balance(MASS)` in `expected.csv`); calculator flags; KPI targets with tolerances; consistency
checks (for example the energy closure of a cycle).

## 8. After each run: the run review

The file contract (SKILL.md, file-types.md): the user saves the `.bkp` and exports the `.rep` with
the same name into the version folder, plus the `.cpm` when the run fails, and says which folder
and file, the steps done, any deviation and why, and their questions. Then:

1. Read the files yourself. `fw his "<folder>"`, `fw rep`, `fw bkp`: converged? errors? warnings
   that change results (messages.md)? A `WARNING:` line at the top means a file is from an older
   run than another file of the case: ask for "run, save, then File > Export > Report" first.
2. `fw check "<model.rep>" --elements <the elements that matter> --metric ...`: block mass and
   element balances, electroneutrality, apparent vs true basis, KPIs.
3. `fw check "<model.rep>" --expect "expected.csv"`: the table *| Item | Expected | Model | Verdict |*
   (pass, fail, missing). Rows are `item, source, expected, tol_abs` or `tol_rel` (`3%` works);
   `source` is a metric expression, `temp(S)`, `pres(S)`, `vfrac(S)`, `block(B1, HEAT DUTY)` or
   `balance(MASS)`, in the units of the report.
4. Answer: what passed; the review table; numbered fixes, each with its root cause (state your own
   earlier mistakes plainly: "that was my instruction"); the messages that are harmless; the next
   run's steps with expected values; the "what to send next time" list. Never tune an input to hit
   a number without saying which input changed and why it is legitimate.
5. Update STATUS.md.

## 9. The living status document (STATUS.md)

One per model (`templates/status.md`): a revision line with the date and what changed; "Read for
this revision" (runs, papers, help topics); "Checks run here"; "Modelling rules kept"; a summary
(frozen versions with key KPIs, open fixes, next step); "What to send after each step"; the roadmap
(version, adds, status); the version history (file, content, last saved or run, result); problems
ranked by their effect on the answer; messages and fixes; sources.

Before overwriting a copy in a synced folder, compare it with the last revision you wrote; never
overwrite a newer or user-edited copy (sync clients can restore older revisions). Name one copy as
the reference.

## 10. Modelling rules

- A built-in block for every physical step; a calculator only where Aspen has no block.
- Calculators read flowsheet values; only fitted constants and physical constants are typed in the
  Fortran.
- Scenario choices are Parameters, with the Init value in exactly one active block.
- Targets by design specs; vary feeds, not intermediate streams; scale the vary limits when the
  plant is scaled.
- Flashes run adiabatic unless the step is isothermal by design.
- Type every machine efficiency (a blank Compr or MCompr efficiency means 0.72); machine
  efficiencies in Aspen, motor and drive efficiencies in the KPI calculator.
- In a true-component electrolyte run, write apparent acids and bases to the feeds and read the ions.
- Several interacting design specs: converge them together (Broyden).
- KPIs in one KPI calculator, per unit of product, with explicit formulas.

## 11. Sensitivities

- Use them before a design spec (is the target reachable, is the response monotonic?) and to
  choose operating points. One input changed at a time, the main target held by its design spec.
- Tabulate the KPI and the variables that explain it (duties, a second composition, pH), then read
  the table: where the curve bends, what limits it physically, what the chosen point costs.
- Many points or cases: `fw com-sweep` runs them on a copy and writes a CSV (automation.md).
- Record the chosen point in STATUS.md with the study it came from.

## 12. Next steps and data requests

Rank them by their effect on the answer. Each data request replaces one assumed line of the data
card.

## 13. Before delivering a guide

- Regenerate every number quoted in the text from the check model and confirm it appears correctly
  (wrong numbers in a guide cost the user a run).
- Lint and compile every Fortran file: `fw fortran-check "<file>"`.
- Say what was not verified ("Aspen was not run here: check values come from the check model").

## Answer shape in build mode

The step header (`v0.04: degasser, adiabatic flash`), then the instructions of section 6, then
"Next action" in one line. Keep explanations short and engineering-focused; the build guide and
STATUS.md carry the history.
