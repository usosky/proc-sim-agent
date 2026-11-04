# <Model name>: build guide

<!-- proc-sim-agent template (templates/build-guide.md). One guide per model, kept in the model
folder; STATUS.md carries the history (templates/status.md). Replace every <...>. -->

Revision <r>, <date>: <what changed>. Aspen Plus <V15>. Check values come from the check model
(section 4); Aspen Plus was not run while this guide was written unless a step says so.

## 0. How to use this guide

- One step per version: File > Save As `<MODEL>_vX.YY` in its own folder `vX.YY\`, do the step,
  run, save.
- After each step: save the `.bkp` and export the `.rep` with the same name into the version
  folder (also the `.cpm`, File > Export > Run Messages, when the run fails). Then send: the folder
  and file name, the steps done and any deviation (and why), and your questions.
- Every step lists check values with a tolerance. If one is off, stop and send the files.

## 1. The job

- Scope: <from ... to ...>; interface stream: <name> (hand-over to <the downstream model>).
- Conventions: v0.01, v0.02 ... one change each; v1.00 gate: the reference reproduced; v1.0x:
  project basis; v2.00: frozen with acceptance checks. Folder `vX.YY\`, file `<MODEL>_vX.YY`.
- Out of scope: <...>

| Reference | What it provides |
|---|---|
| <paper, Table 2> | <feed and conditions> |

| Item | <sibling model> | This model | Why |
|---|---|---|---|
| <property method> | <...> | <...> | <...> |

## 2. Data card

Every value the model uses, with its source and status, is in `data-card.md`
(templates/data-card.md). Assumed lines become data requests (section 9).

## 3. What Aspen can and cannot represent

| Phenomenon | In Aspen? | How we represent it | What stays outside |
|---|---|---|---|
| <...> | <yes / no> | <block, method> | <...> |

Calculators only where Aspen has no block.

## 4. Expected values and the check model

- Check model: <script or workbook, version>. Calculators are compiled and run in a harness
  (`fw fortran-check "<file>"`).
- Tolerances: about 0.1 % on calculator outputs and flows; about 3 % on duties and machine
  powers where the property method differs from the check model.
- Edge cases tested: <extreme inputs, zero flows, under-specified steps>.
- Check values per version: `vX.YY\expected.csv` (templates/expected.csv), compared after the
  run with `fw check "<model.rep>" --expect "expected.csv"`.

## 5. Versions and gates

| Version | Adds | Check or gate | Status |
|---|---|---|---|
| v0.01 | components, property method | property analysis against data | planned |
| v0.02 | feeds | composition, flow, state | planned |
| v1.00 | gate: the reference reproduced | section 7 | planned |
| v1.01 | project basis: <site, feed, machines, scale> | | planned |
| v2.00 | frozen | acceptance checks | planned |

Case inputs (the only values that change between case files of one version):

| Input | Case A | Case B | Unit |
|---|---|---|---|

Design inputs (changed only as a deliberate sensitivity): <...>. A gate file is never edited:
the next change starts with Save As the next version.

## 6. Steps

### v0.0N: <what this step adds>

1. File > Save As `<MODEL>_v0.0N` in `v0.0N\`.
2. **<Ribbon > Pane > Sheet>**: <field> = <value> <unit>.
3. Run (Reinitialize first when <...>).

| Check | Expected | Tolerance |
|---|---|---|
| <stream S1 CO2 flow> | <...> kmol/h | 0.1 % |

If a value is off: <what to look at first>. Calculator code for this step:
`<MODEL>_v0.0N_fortran.txt`, pasted as plain text; units on every Define row.

## 7. Gate acceptance (v1.00, v2.00)

| Check | Pass |
|---|---|
| Control panel | 0 errors; acceptable warnings: <IDs, why> |
| Overall flowsheet balance | relative difference below <1e-4> |
| Calculator flags | <...> |
| KPI targets | <value> +/- <tolerance> |
| Consistency | <for example the energy closure of a cycle> |

## 8. Sensitivities

One input at a time, the main target held by its design spec. Tabulate the KPI and the variables
that explain it, then read the table: where the curve bends and why.

| Study | Varied input and range | Held by | KPI and explaining variables |
|---|---|---|---|

## 9. Next steps and data requests

Ranked by their effect on the answer; each request replaces one assumed line of the data card.

| # | Step or request | Replaces | Effect on the answer |
|---|---|---|---|

## Before delivering this guide

- [ ] Every number in the text regenerated from the check model and found in the text as written.
- [ ] Every Fortran file linted and compiled (`fw fortran-check`).
- [ ] What was not verified is said ("Aspen was not run here: check values come from the check model").

## Sources

| # | Source | Used for |
|---|---|---|
