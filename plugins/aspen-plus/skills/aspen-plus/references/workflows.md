# Workflows

`fw` below means `python "${CLAUDE_SKILL_DIR}/scripts/fw.py"` (see SKILL.md for Windows).
Building a new model with the user is in build-mode.md; writing input files in input-language.md.

## 1. Troubleshoot a run

1. Get the evidence, newest first: `fw his <file or folder>` (has message IDs), else
   `fw cpm <file>` (Control Panel export), else the text the user pasted. Note the engine version
   and whether the run finished ("RUN SAVED", summary of errors).
2. Read the digest in this order: flowsheet-analysis errors, then errors in the final pass, then
   final-pass warnings, then property/Fortran warnings. Iteration-0-only warnings after a
   Reinitialize are usually harmless.
3. Look up each ID in messages.md. For one that is not there, search the help with a distinctive
   phrase of the message (`fw help-search "temperature crossover"`) and read the best topic.
4. Trace one root cause before listing fixes: one missing Parameter value or one unbalanced loop
   explains many messages. Check the computation order and the loop history in the digest.
5. For calculators: `fw his <file> --fortran` shows the code with lint (column 72, tabs,
   undefined names, assigned imports). Check the Define rows against calculators.md.
6. Answer in the fix format of answer-style.md; give the expected messages after the fix.

## 2. Review a model (or get up to speed on one)

1. `fw sim-scan <folder>`: versions, file types, last run status, stale or missing exports,
   leftover engine files, the notes column.
2. `fw bkp <model.bkp>`: components, property methods, blocks and connectivity, calculators,
   design specs (active or not), tears, convergence options.
3. `fw his <model.his>`: messages, loops, block results; `fw his-diff old.his new.his` shows what
   changed in the input between two versions.
4. `fw rep <model.rep>`: run status, overall balance, key block results (duties, powers),
   `--streams A,B` for stream tables, `--block NAME` for one block, `--find TEXT`.
5. Report: status, what the model represents, inactive objects (deactivated blocks, disabled
   specs), risks (unconverged loops, warnings that change results, inputs hidden in code), key
   numbers in a table.

## 3. Implement a change, one version at a time

1. File > Save As a new version (new folder or name); never edit the only copy.
2. One change per version, so before/after comparisons stay clean. Write a one-line note (what and
   why) in the version folder.
3. Predict the result before running (hand balance, the calculator code run in Python/gfortran
   with the "value read" numbers).
4. Run (Reinitialize when the change affects convergence or initial values), export .rep and .cpm.
5. Compare: `fw his-diff`, `fw rep` key results, messages that appeared or disappeared; `fw check`
   for balances and KPIs.
6. Only then start the next change.

## 4. Verify a model against a reference (paper, SI, datasheet, previous version)

1. Collect the reference values with their units and conditions (table, page).
2. Pull the model values from the .rep (`fw rep --block`, `--streams`, `--find`). Convert units
   explicitly (the report uses the model's unit set: cal/s, Gcal/hr, kW...; 1 cal/s = 4.1868 W).
3. Table: item | model | reference | difference (%) | comment. Match sign conventions (Aspen duties
   are negative for heat removed).
4. Explain each difference above about 1 %: different specification (for example a pump with zero
   pressure increase because the feed is already specified at outlet pressure), different
   version or databank, a deactivated block, an annualisation basis (h/year).
5. Never adjust the model to match without telling the user which input changed.

## 5. Convergence problems

- Tear loop: read the loop history (`fw his`/`fw cpm`). Steady decrease: more iterations or
  Broyden. Oscillation or growth: a block inside fails every other pass, the loop accumulates
  material, or an input is missing; fix that first. Give tear estimates close to the expected
  values (Streams > tear > Input) and Reinitialize.
- Design spec: check that the spec is reachable within the Vary limits (run a Sensitivity over the
  range first); flat or non-monotonic response: Secant Bracket = Yes / Check Bounds. With specs
  and tears in the same loop, converge the inner loop tighter than the outer one; how specs are
  nested is set in Convergence > Conv Options > Defaults > Sequencing (Design spec nesting).
- Changed only a tolerance or a convergence parameter and nothing reruns: Aspen reruns only the
  blocks affected by an input change ("Use affected block logic", same Sequencing sheet).
  Reinitialize, or clear that option for the test.
- Columns: give temperature estimates (Estimates sheet), check the feed stage and the
  specifications are feasible (distillate rate vs feed composition), start from a converged
  simpler case.
- Help topics worth reading in the user's version: search "resolving sequence and convergence
  problems", "troubleshooting design specifications", "diagnosing design specification convergence".

## 6. Choosing a property method (first pass; confirm with the Methods Assistant)

See how AspenTech's examples model the same system first: `fw examples-search "<system>"
--has electrolyte` or `--method <METHOD>`, then `fw examples-show <id>` (examples.md).


| System | Usual choice | Watch |
|---|---|---|
| Hydrocarbons, gases, any pressure | PENG-ROB, RK-SOAVE | water and polar components need care |
| Polar, non-electrolyte liquids, below about 10 bar | NRTL, UNIQUAC (WILSON if no liquid-liquid split) | binaries must exist for every key pair (GM05I.1 if all are zero) |
| Same with carboxylic acids (vapour-phase association) | NRTL-HOC, UNIQ-HOC | |
| Polar at high pressure | SR-POLAR, PRWS, PSRK, RKSMHV2 | mixing-rule parameters |
| Electrolytes, acid gases in amines or water | ELECNRTL, ENRTL-RK | chemistry, true vs apparent approach, PRPCHK.1 at boundaries |
| Supercritical gases in liquids | add them as Henry components | HENRY-1 parameters |
| Water or steam only | IAPWS-95 / STEAM-TA | |

Check: binaries present (Methods > Parameters > Binary Interaction), a T-xy or P-xy plot
against data for the key pair, pure-component vapour pressure at TB (LCCHCK.1).

## 7. Starting values for screening studies (replace with project data)

| Item | Typical starting value |
|---|---|
| Centrifugal compressor isentropic efficiency | 0.72-0.80 |
| Discharge temperature per stage | below about 150-200 °C; intercool and knock out condensate before each stage |
| Pump efficiency | Aspen's default curve is for water; enter 0.5-0.75 for other services |
| Minimum approach in heat exchangers | 10 °C liquid-liquid, 15-20 °C with gas, 3-5 °C refrigeration |
| Cooling water | supply 25-30 °C, return 35-45 °C |
| Reflux ratio | 1.1-1.5 x minimum |
| Tear tolerance | Aspen default is fine; tighten when a design spec sits inside the loop |

## 8. Searching the user's library

`fw docs-search "<words>"` finds pages in their PDFs and notes; `fw docs-read <doc> --pages 12-14`
prints them. Quote the document title and page when using a number from it. Library content is
the user's: do not copy it into public files.

## 9. When Aspen Plus cannot do it directly

Say so, then offer the closest route: a Calculator (Fortran or Excel) for an algebraic model; a
user unit-operation model (Fortran subroutine, Aspen Custom Modeler) for a custom block; a property
regression (Data Regression run) when parameters are missing; Aspen Adsorption or Aspen Plus
Dynamics for cyclic or dynamic processes; an external Python or spreadsheet calculation with the
interface values copied by hand (document them as fixed inputs).
