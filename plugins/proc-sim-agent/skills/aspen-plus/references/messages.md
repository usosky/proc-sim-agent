# Aspen Plus run messages: meaning, usual cause, fix

Curated from real runs (Aspen Plus V12.1-V15) and written in general terms. The quoted wording
is Aspen's; block and stream names are placeholders.

In the commands below, `fw` stands for `python scripts/fw.py`, run from the skill folder (see SKILL.md).

Where to read them: the .his file prints every message with its ID (for example `URE07.3`,
at the end of the header line or on the line below). The Control Panel and the .cpm export
show the same text **without** the ID, so match on the wording. The help rarely documents the
IDs; for a message not listed here search the help with a distinctive phrase of its wording
(`fw help-search "temperature crossover"`).

Severity: ` *   WARNING`, ` **  ERROR`, `*** SEVERE ERROR`, `**** TERMINAL ERROR`; INFORMATION
has no asterisks. The header names the phase: physical property system / input translation,
flowsheet analysis, "while executing" (simulation), "while generating results".

Reading order that saves time:
1. Errors and severe errors, in the order they first appear.
2. Warnings in the **final** pass. A warning seen only in iteration 0 (the first pass after
   Reinitialize, when tear streams are still empty) is usually harmless if the loop converged.
3. Property and Fortran warnings from input translation.
4. Everything else.
The `his` digest groups repeats, marks iteration-0-only warnings and lists the IDs found.

## Index by symptom

| Symptom | Look at |
|---|---|
| Run stops before calculating, "YOUR PROBLEM WILL NOT RUN" | Flowsheet-analysis messages, below |
| Design spec's convergence block deleted | "SPEC ... VARY VARIABLE DOWNSTREAM OF SAMPLED VARIABLES" |
| Tear does not converge; error/tol changes sign and grows | CONVI.1, BALMAS.1, CHKCVG.1; calculators.md section 8 |
| Enormous flows (1E24 and up), loop mass imbalance | "SAMPLED VARIABLE ... HAS NOT BEEN CALCULATED", GETADD.36 |
| Conversion reduced by a factor; a reactant leaves with zero flow | URE07.3 |
| Blocks bypassed, zero flow on the first pass | UHE01.4, UHE02I.1, URE07.1, USP01I.1, CMSTIN.1, WEGSTN2.1 |
| Reaction dropped / no reactions active | URE07.2, URE07.5 |
| "NOT IN A DATA BANK", "STRUCTURE ... HAS NOT BEEN DEFINED" | PDATAFAP.1, PCERTE.10 |
| Component flows rescaled to a total | STSTRM.29 |
| Fortran READ-VAR warnings | ADFORT.7, ADFORT.8 |
| Heat exchanger temperature cross | HEATX.4, HXTQCRV.1, TGSUPP.1 |
| Compressor "FEED STREAM IS BELOW DEW POINT" | CMSTIN.9 |
| RadFrac reactive flash failure | VFLASH.1, UDL03A.48 |
| Property parameter bounds, odd vapour pressure, formula/MW mismatch | LCLIMS.3, LCLIMS.4, LCCHCK.1, LOADMW.5, PCMNAT.1, PCESSR.1 |
| "INCONSISTENT PROPERTIES DETECTED" | PRPCHK.1 |
| "NRTL BINARY PARAMETERS ... ARE ZERO" | GM05I.1 |
| Components land in a Sep outlet that has specifications; charge balance or Henry errors; nonsense KPIs | "Run lessons" below: blank rows in a Sep outlet |
| Machine power about 20 % off, very hot compressor stages, product pressure off target | "Run lessons": efficiencies, Compr specifications |
| No *Report Files* type in File > Export | "Run lessons": no results in the session |
| Errors only in the first row of a sensitivity, or only in the first passes of a loop | "Run lessons": first-row and first-pass messages |

## Flowsheet-analysis messages printed without an ID

**`SPEC <spec> VARIES VARIABLE DOWNSTREAM OF SAMPLED VARIABLES.`** (warning), followed by
**`SPEC <spec> VARY VARIABLE DOWNSTREAM OF SAMPLED VARIABLES OR NEED READ-VAR FOR VARY VARIABLE.
CONVERGENCE BLOCK $OLVERnn WILL BE DELETED.`** (error)
- Means: Aspen found no calculation path from the design spec's Vary variable to the variable the
  spec samples, so it cannot converge the spec and drops its convergence block.
- Usual cause: the Vary variable is a Parameter that a calculator reads, and that calculator has
  an explicit execution point (Sequence = First/Last/Before/After a block). With an explicit
  point Aspen ignores the calculator's Import/Export list when it orders the flowsheet, so it does
  not see that the calculator reads the varied Parameter.
- Fix: on that calculator's Sequence sheet choose *Use import/export variables* and keep the
  Parameter as an Import on its Define sheet. Reinitialize, run, and check the new computation
  order: the calculator now sits inside the spec's loop, before the blocks it writes.
- Second cause: there is no path at all, because a recycle that should carry the varied variable
  to the sampled one is not connected (the stream ends as a product). Fix the connectivity first.

**`YOUR PROBLEM WILL NOT RUN BECAUSE OF ERRORS FOUND DURING FLOWSHEET ANALYSIS.`** - always the
consequence of an earlier flowsheet-analysis error; fix that one.

**`SAMPLED VARIABLE '<name>' HAS NOT BEEN CALCULATED. VALUE IS MISSING.`**, often together with
the loop imbalance below and a URE07.3 factor many orders of magnitude below 1
- Usual cause: a Parameter has its Init value only in a block that has been deactivated (or in no
  block). Aspen then works with its missing-value placeholder (about 1E35), and every flow
  computed from it explodes. One missing number can produce all the warnings of the run.
- Fix: give the Parameter its Init value in an active calculator (Define > that row > Init
  value), Reinitialize, Run. Rule: when you deactivate a block, move the Init of every Parameter
  it defined to an active block (GETADD.36 then remains as a reminder).

**`STREAMS CROSSING THE LOOP CONVERGED BY $OLVERnn ARE NOT IN MASS BALANCE ... IMBALANCE MAY BE
DUE TO A LARGE RECYCLE FLOW, AND A RELATIVELY LOOSE TEAR STREAM TOLERANCE.`** (warning)
- Small imbalance (percent level): tighten the tear tolerance (Convergence > Tear) or check that the
  loop really converged.
- Huge imbalance (orders of magnitude): a missing value (see above) or a loop that accumulates
  material (fresh feed with no outlet, see calculators.md section 8).

## Messages by ID

### ADFORT.7 - `FORTRAN READ-VAR <var> IN FORTRAN BLOCK <calc> APPEARS ON THE LEFT-HAND SIDE OF AN ASSIGNMENT STATEMENT.`
Flowsheet analysis, warning. The inline Fortran assigns a value to a variable declared as Import.
Usual cause: an input guard written on the import itself, e.g. `IF (TIN .LT. 200.0D0) TIN = 298.15D0`.
Fix: copy every import to a local variable at the top of the code (`TL = TIN`) and change only the
copy. The `his` digest's Fortran lint lists the offending variables.

### ADFORT.8 - `READ-VAR <var> in CALCULATOR block <calc> is reading from a block with WRITE-VAR in the calculator. We will ignore this READ-VAR in sequencing.`
Flowsheet analysis, warning. The calculator reads from the same block it writes to (for example it
reads a reactor's temperature and sets its conversion). Aspen's own advice: harmless if the value
read is an unvaried input; otherwise vary a Parameter and read the Parameter, or give the calculator
an explicit execution sequence. With an explicit Sequence (Execute Before that block) the order is
fixed and the warning is harmless. It disappears if the value is read from elsewhere (the feed
stream, a Parameter).

### APLX2S.3 - `INITIAL VALUE OF LOCAL PARAMETER "<name>" IS MISSING.`
Simulation, information, while executing a calculator. A Local-Param variable has no initial value;
normal for a variable the calculator only writes (a result shown on its Results sheet). Harmless.

### BALMAS.1 - `BLOCK <block> IS NOT IN MASS BALANCE: MASS INLET FLOW = ..., MASS OUTLET FLOW = ...`
Sequence monitor, error. Aspen's own text gives the two usual causes: a tear stream, or a stream
flow changed by a calculator, transfer, balance or convergence block after the block had been
executed. Most often the consequence of a tear loop that never converged: fix the convergence first.
If the loop converged, look for a calculator or transfer that writes a stream after its consumer ran
(check the computation order).

### CHKCVG.1 - `Convergence block $OLVERnn did not converge normally in the final pass`
Sequence monitor, error. The final-pass companion of CONVI.1; read the convergence history (the
`his` digest prints it) before raising iteration limits.

### CMSTIN.1 - `TOTAL FLOW IS ZERO. BLOCK IS BYPASSED.` (Compr)
Simulation, warning. First pass with an empty tear stream; harmless if it does not recur in the
final pass (it disappears when you run again without Reinitialize).

### CMSTIN.9 - `FEED STREAM IS BELOW DEW POINT` (Compr)
Simulation, warning. Part of the compressor feed is liquid, typically a stage fed straight from an
intercooler with water- or condensable-saturated gas. Add a knock-out drum (Flash2 at the cooler
outlet conditions) before each stage and route the condensate away.
Related: `UPC02I.3 LIQUID PHASE EXISTS ...` and `CMSTIN.8 FEED STREAM IS BELOW DEW POINT ...` on
Compr or MCompr: liquid in the machine's feed or inside a stage. Put a knock-out drum ahead of the
machine; where liquid is real, set the valid phases to Vapor-Liquid.

### CONVI.1 - `CONVERGENCE BLOCK $OLVERnn NOT CONVERGED IN <n> ITERATIONS`
Simulation, warning. Before raising Maximum iterations, read the history of max err/tol:
- decreasing steadily but slowly: more iterations or a different method (Broyden) can help;
- oscillating with growing amplitude, sign changes: the loop is not mass balanced or a block inside
  it fails on every other pass (look for HEATX.4, URE07.3 inside the loop). More iterations will
  not help; fix the loop.

### GETADD.36 - `PARAMETER <n> WAS INITIALIZED BY DISABLED OBJECT <block>. INITIAL VALUE SET TO THE LAST ACTIVE INITIALIZATION IN SEQUENCE: <value>`
Input translation (DISABLE paragraph), warning. A Parameter's Init value is also given in a
deactivated block; Aspen uses the active one. Harmless once an active block initialises the
Parameter; it goes away if you delete the old block or clear its Init. If no active block
initialises it, see "SAMPLED VARIABLE ... HAS NOT BEEN CALCULATED".

### GM05I.1 - `NRTL BINARY PARAMETERS FOR ALL COMPONENT PAIRS ARE ZERO, YOUR RESULTS MAY NOT BE ACCURATE.`
Physical property system, warning. The activity-coefficient model has no binaries, so the liquid is
treated as ideal. Enter, estimate or regress the binaries, or, when no liquid phase matters (gas
processing), use an equation-of-state method.

### HEATX.4 - `TEMPERATURE CROSSOVER DETECTED. RE-CALCULATING WITH MINIMUM APPROACH TEMP. SPEC`
Simulation, error. The specification (for example a hot outlet temperature) cannot be met with the
current flows; HeatX recalculates with the minimum approach. Inside a recycle it often comes from
flows that change between iterations or keep growing. Check the flows into HeatX first, then use a
more forgiving specification (minimum approach or duty).

### HXTQCRV.1 - `TEMPERATURE CROSS DETECTED IN TQ-CURVE INLET`
Results generation, warning. Same physics as HEATX.4, seen while building the TQ curve; usually
disappears with HEATX.4.

### LCCHCK.1 - `PARAMETER PLXANT ... UNREASONABLE VAPOR PRESSURE CALCULATED AT NORMAL BOILING POINT. VALUE SHOULD BE WITHIN 10% OF 1D5 N/SQM.`
Physical property system, warning. The extended Antoine parameters entered for a component do not
give about 1 bar at its normal boiling point (TB). Check the units of the coefficients (temperature
in K or C, pressure units, ln vs log10), their signs, and TB itself.

### LCLIMS.3 / LCLIMS.4 - `PARAMETER <name>/ELEMENT <n> ... LOWER (UPPER) BOUND VIOLATED FOR COMPONENT <comp>`
Physical property system, warning. An entered or estimated parameter (OMEGA, DHVLWT, ...) is outside
Aspen's sanity bounds. Harmless only if the active property method does not use that parameter for
anything that matters; otherwise review its value, units and source.

### LOADMW.5 - `MW ENTERED FOR COMPONENT <comp> IS DIFFERENT FROM MW CALCULATED FROM ENTERED FORMULA (ATOMNO/NOATOM). CALCULATED VALUE IS USED.`
Physical property system, information. Check the formula entry; for ions the hydrogen count is the
usual slip (compare with PCMNAT.1).

### PCERTE.10 - `STRUCTURE FOR COMPONENT <comp> HAS NOT BEEN DEFINED. PCES CANNOT USE GROUP-CONTRIBUTION METHODS TO ESTIMATE MISSING PROPERTIES.`
Physical property system, information, one per component. Appears when property estimation is
enabled without molecular structures. Harmless when the parameters the method needs are entered or
come from databanks; otherwise define the structure (Components > Molecular Structure).

### PCESSR.1 - `FUNCTIONAL GROUP GENERATION FOR THE UNIFAC METHOD CANNOT BE COMPLETED FOR COMPONENT <comp>. THE FOLLOWING ATOMS WERE NOT MATCHED: ...`
Physical property system, warning. Some atoms of the defined structure are not covered by the
group-contribution method. Harmless unless you rely on that method to estimate parameters or
binaries for this component; then supply groups by hand or data.

### PCMNAT.1 - `NOATOM ENTRY OF "<n>" FOR ATOM "<el>" ... DOES NOT MATCH THE VALUE IN ITS STRUCTURE DEFINITION (<m>).`
Physical property system, warning. Formula (ATOMNO/NOATOM) and molecular structure disagree, often
the hydrogens of an ion. Make them consistent.

### PDATAFAP.1 - `THE FOLLOWING CONVENTIONAL COMPONENTS WERE NOT IN A DATA BANK. CHECK DATA BANK NAMES FOR SPELLING.`
Physical property system, warning. Expected for user-defined components (solids, adducts,
pseudo-components); for real chemicals check the databank name. Make sure every parameter the property
method needs is entered for the components listed.

### PRPCHK.1 - `INCONSISTENT PROPERTIES DETECTED FOR <n> STREAMS` (table: source block, property method, stream, destination block, property method)
Input check, warning. Connected blocks use different property methods (block-level property
options), so a stream leaves one block evaluated with one method and enters the next with another;
enthalpies and phase splits can jump. Make the methods consistent, or accept it knowingly (for
example an electrolyte section next to a non-electrolyte column) and check the balance around the
boundary.

### PSTOP1AP.1 - `THERE ARE HENRY COMPONENTS DEFINED IN THIS CASE, THE BINARY DATABANK WILL BE SEARCHED AUTOMATICALLY FOR ANY AVAILABLE HENRY CONSTANTS.`
Information. Check Methods > Parameters > Binary Interaction > HENRY-1 for pairs that are still
missing; a supercritical gas without Henry constants is handled poorly by activity models.

### STELBP.3 - `THE PAIR PARAMETERS FOR ELECNRTL OPTION SET HAS BEEN RETRIEVED FROM DATABANK <bank>.`
Physical property system, information only.

### STSTRM.29 - `STREAM NAME: <stream> COMPONENT MOLE FLOWS OF SUBSTREAM: "MIXED" ARE NORMALIZED TO THE TOTAL MOLE FLOW VALUE.`
Input translation, warning. The stream's Input form has a Total flow as well as component flows,
so Aspen rescales the components to the total. It matters when a calculator writes a component flow
into that stream: the typed total wins. Fix: Streams > <stream> > Input > Mixed, give the composition
as component Mole-Flow and leave Total flow empty. (Related STSTRM IDs report the same for other
flow bases.)

### TGSUPP.1 - `FLASH CALCULATIONS BYPASSED DUE TO UNREASONABLE SPECIFICATIONS. SPECIFIED PRESSURE (MISSING) ...` (while generating a TQ curve)
Results generation, error. Typically one side of a heat exchanger at the end of a failed run (zero
flow or missing values). Fix the run first; this one then disappears.

### UDL03A.48 / VFLASH.1 - `REACTIVE FLASH FAILURE ... COMPOSITE FEED FLASH FAILED TO CONVERGE; COLUMN CALCULATIONS CONTINUE. IF CALCULATIONS FAIL, SUPPLY T-EST AND OPTIONALLY BOTH X-EST AND Y-EST.`
Simulation, information/warning (RadFrac with reactions or electrolytes). Harmless if the column
converges. If it fails, give a temperature profile on the column's Estimates sheet (two or three
stages are enough), and optionally liquid and vapour composition estimates.

### UHE01.4 - `ZERO FEED TO THE BLOCK. BLOCK BYPASSED` (Heater)
### UHE02I.1 - `AT LEAST ONE FEED HAS ZERO FLOW. BLOCK BYPASSED` (HeatX)
### URE07.1 - `TOTAL FLOW IS ZERO` (RStoic)
### USP01I.1 - `ZERO FEED TO THE BLOCK. BLOCK BYPASSED` (FSplit)
Simulation, warning. First pass after Reinitialize with an empty tear stream: every block downstream
of the tear is bypassed once. Harmless if they do not recur in the final pass. A tear estimate
(Streams > tear stream > Input) avoids them.
In the final pass the upstream outlet is really empty: a flash operated above the bubble pressure of
its feed, a knock-out drum with nothing to knock out, or wrong wiring. Fix the wiring or the
upstream pressure.

### UHE02I.6 - `TUBESIDE STREAM HAS ZERO FLOW ... SPECIFIED U-OPTION NOT ALLOWED - CHANGED TO "CONSTANT"`
Results generation, warning. Symptom of a zero-flow or failed run; fix that first.

### URE07.2 / URE07.5 - `REACTION NO. "<n>" IS DROPPED BECAUSE REACTANT "<comp>" HAS ZERO INLET FLOW RATE ...` / `NO REACTIONS ARE ACTIVE - PROCEEDING WITH OUTLET FLASH`
Simulation, warning. A reactant is absent from the RStoic feed, so its reaction is dropped (and if
none is left the block only flashes). Harmless in iteration 0 of a recycle; if it remains in the
final pass, check the feed of that reactant (recycle flow, splitter fractions, calculator writes).

### URE07.3 - `COMPONENT "<comp>" HAS ZERO FLOWRATE IN THE OUTLET STREAM. FRACTIONAL CONVERSION HAS BEEN MODIFIED BY A FACTOR OF "<f>"`
Simulation, warning. The specified conversion would consume more of `<comp>` than the feed contains,
so RStoic scales the conversion by `<f>` and `<comp>` leaves with zero flow (looks like exactly 100 %
conversion of it). A factor near 1 means a slightly too-high conversion; a factor many orders of
magnitude below 1 means a missing or exploded input upstream (see "SAMPLED VARIABLE ... HAS NOT BEEN CALCULATED").
Fix: cap the conversion at the available amount in the calculator that sets it (calculators.md
section 7); leaving about 0.1 % unreacted avoids the zero-flow trigger.

### WEGSTN2.1 - `VALUE IS MISSING FOR VARIABLE <n>. THIS MAY BE CAUSED BY A ZERO-FLOW STREAM. THE PREVIOUS VALUE OF THE VARIABLE WILL BE USED.`
Simulation, warning, usually first iteration. A tear variable had no value because a stream in the
loop had zero flow. Harmless alone; it points at the zero-flow stream.

## Run lessons (message or symptom -> cause -> fix)

From V15 build sessions; general patterns, placeholders for names.

| Message or symptom | Cause | Fix |
|---|---|---|
| Components land in a Sep outlet that has specifications; `BALCHG.1 ... NOT IN CHARGE BALANCE`; nonsense KPIs; Henry-parameter errors for new components | Blank component rows in a Sep outlet with specifications are not zero: Aspen sends those components there (V15) | Type split fraction 0 for every component that must not go there |
| `FORTRAN WRITE-VAR ... IS WRITING TO AN OUTLET STREAM VARIABLE` | A Define row meant to be read is set to Export | Set it to Import |
| `UFL01.1 FLASH CALCULATIONS FAILED TO CONVERGE`, then `SNSTVI.4 SOME ROWS COMPLETED WITH ERRORS` | A flash fed a tiny vapour-only stream and asked to flash lower | Feed the next stage with the right phase; check the wiring |
| `ANPSH.4 NET POSITIVE SUCTION HEAD IS LESS THAN ZERO` | Dissolved gases make the feed's bubble pressure exceed the suction pressure | Informational with gas-saturated liquids; otherwise check the suction pressure |
| Mixer outlet at vacuum and two-phase | Mixer pressure left at 0 (the lowest inlet pressure) | Type the outlet pressure |
| Stage outlets at 220-320 C on a liquid-ring or near-isothermal machine | The calculation is adiabatic | An artefact if the power is right (the aftercooler carries the heat); otherwise fix the specification |
| Product pressure off target, very hot stages | Compr specified with a pressure increase instead of a discharge pressure | Setup > Specifications: discharge pressure |
| Absurd flash temperature, most of the liquid boiled off | A pressure typed in the wrong units (an mbar value in a bar field) | Check the units of every typed value |
| No *Report Files* type in File > Export | No results in the session | Run first: after opening a `.bkp`, after any input change, after a Report Options change |
| Machine power about 20 % off the expected value | Efficiency left blank: Compr and MCompr then use 0.72 | Type every stage's efficiency |
| `... YOU ARE VARYING A VARIABLE OF AN INTERMEDIATE STREAM` | The design spec varies a block outlet | Vary a feed stream |
| `GM08.1 ... ELECNRTL WITHOUT A SOLVENT`, `URE07.8 ... ALL COMPONENTS ARE DEFINED AS HENRY COMPONENTS` | Gas-only streams in an electrolyte run (first passes of a loop) | Harmless if only in first passes; otherwise a non-electrolyte section for the gas-only parts |
| A spec converges but a make-up is several times the expected value | A recovered stream ends nowhere (it is a product) | Check every recovered stream's From and To in the stream table |
| `MODSEC.9 ... NOT MONOTONIC`, `ASTREM.9 TOTAL FLOW ... BECAME ZERO`, `USP01I.3 ... DOES NOT CONVERGE`, once each in the first row of a sensitivity | Start-up of the first case | Harmless when only in first passes; otherwise check the bounds |
| `ABNDCK.1 INITIAL VALUE FOR DESIGN SPEC VARIABLE ... ABOVE UPPER BOUND` | The start value was scaled with the plant, the limits were not | Scale the vary limits too |
| Total work low by one machine | A work stream left as a product outside the Mixer that sums the work | Connect every work stream |

## Adding entries

Keep entries general (no project names or data); give the phase, severity, Aspen's wording, the
usual cause and a fix confirmed in a real run. Pull requests welcome (CONTRIBUTING.md).
