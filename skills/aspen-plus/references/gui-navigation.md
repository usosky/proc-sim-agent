# Aspen Plus V12-V15 user interface: where things are

Paths below were checked against the V15 help. V12-V14 use the same ribbon and navigation pane
with small differences; when the user's version differs, or for anything not listed, confirm with
`fw help-search "<form or command name>"` and quote the help's wording.

In the commands below, `fw` stands for `python scripts/fw.py`, run from the skill folder (see SKILL.md).

Notation: **Ribbon tab > group > command**; navigation-pane paths as **Folder > Item > Form |
Sheet**. Forms open from the navigation pane (left); each form has sheets (tabs).

## Files and exports

| Task | Path |
|---|---|
| Save a version | File > Save As > *Aspen Plus Backup Files (\*.bkp)* (copies the .apmbd too) |
| Report file | File > Export > *Report files (\*.rep)* |
| Run messages | File > Export > *Run Messages (\*.cpm)* |
| View the history, input or report | Home > Summary > History / Input / Report (open in a text editor) |
| Input file | File > Export > *Input* (.inp) |
| Repair a backup that will not open | File > Repair File (work on a copy) |
| Report content | Setup > Report Options (General, Flowsheet, Block, Stream, Property sheets) |
| Message detail | Setup > Specifications > Diagnostics (global); <block> > Block Options > Diagnostics |
| History size limit | Setup > Calculation Options > Limits |

## Running

Home tab, Run group (buttons, left to right):

| Command | Does | Key |
|---|---|---|
| Next | goes to the next sheet that still needs input | |
| Run | runs the simulation | F5 |
| Step | runs the next block of the sequence (sequential modular) | Ctrl+F5 |
| Stop | stops a running simulation | |
| Reset | opens the Reinitialize dialog: Simulation, or chosen Blocks / Streams / Convergence blocks | Shift+F5 |
| Control Panel | convergence sequence and engine messages | |
| Reconcile | writes values changed by design specs (or EO runs) back into the inputs | |
| Settings | Run Settings dialog (engine files, run options) | Ctrl+F7 |

Reinitialize (Reset) when a block fails to converge after you changed it or its feeds, when you need a
specific solution of a model with several, and after activating a design spec or a calculator.
Without it Aspen starts from the previous results (and from values that calculators and design
specs wrote last time).

## Results

| What | Path |
|---|---|
| Run status, completion | Results Summary > Run Status |
| Stream table | Results Summary > Streams > Material sheet (also Heat, Work sheets); the *Stream Summary* ribbon tab chooses streams (All, Feeds, Products, Tears, user groups) and the template (display format) |
| Convergence | Results Summary > Convergence > Tear Summary / DesignSpec Summary; Convergence > <block> > Results |
| Utilities, emissions | Results Summary > Operating Costs; Results Summary > CO2 Emissions |
| A block | Blocks > <block> > Results (Status sheet shows its messages) |
| Calculator values read/written | Flowsheeting Options > Calculator > <name> > Results |
| Design spec result | Flowsheeting Options > Design Spec > <name> > Results |
| Sensitivity table | Model Analysis Tools > Sensitivity > <name> > Results > Summary |

Extra stream properties (for example bubble and dew points, TBUB and TDEW) are defined in a
property set (Properties > Prop-Sets) and added to the stream summary through its template or its
property list; the report uses Setup > Report Options > Stream > Property sets.

## Flowsheeting options and analysis

| Object | Path | Sheets |
|---|---|---|
| Calculator | Flowsheeting Options > Calculator > New | Define, Calculate, Sequence, Tears, Stream Flash; Block Options; Results |
| Design spec | Flowsheeting Options > Design Spec > New | Define, Spec, Vary, Fortran, Declarations; Results |
| Transfer | Flowsheeting Options > Transfer | From, To, Sequence |
| Balance | Flowsheeting Options > Balance | |
| Sensitivity | Model Analysis Tools > Sensitivity > New | Vary, Define, Tabulate, Options, Cases, Fortran, Declarations; Results |
| Optimization, Constraint | Model Analysis Tools > Optimization / Constraint | |

Activate or deactivate: right-click the block, stream or flowsheeting object > Deactivate /
Activate. Deactivated objects must still be fully specified. Objects that reference a deactivated
block (calculators, transfers, design specs, sensitivities; anything sequenced Before/After it) are
deactivated with it, and the history file lists them. Prefer deactivating blocks to deactivating
streams.

## Convergence

| Task | Path |
|---|---|
| Default methods for tear / spec blocks | Convergence > Conv Options > Defaults > Default Methods |
| Tear tolerance, trace threshold, flash tears | Convergence > Conv Options > Defaults > Tear Convergence |
| Method parameters (Wegstein, Secant, Broyden, Newton, ...) | Convergence > Conv Options > Methods > <method> |
| Choose tear streams | Convergence > Tear |
| User convergence block | Convergence > Convergence > New (name must not start with $) |
| Calculation sequence | Convergence > Sequence |

Aspen names its own convergence blocks `$OLVER01`, `$OLVER02`, ...; user blocks cannot start with `$`.

## Properties environment

| Task | Path |
|---|---|
| Property method | Methods > Specifications > Global: Method filter (COMMON by default; ALL shows every method), Base method; Henry components; electrolyte chemistry and true/apparent approach |
| Help choosing a method | the *Methods Assistant* button next to the method name |
| Binary parameters | Methods > Parameters > Binary Interaction > <model>-1 (NRTL-1, HENRY-1, ...) |
| Pure-component parameters | Methods > Parameters > Pure Components |
| Molecular structure | Components > Molecular Structure |
| Property sets | Prop-Sets (also reachable from the Simulation environment) |

## Units

Global unit set: Setup > Specifications > Global (or the units selector on the Home ribbon).
Calculator and design-spec rows keep the units they were created with, regardless of later
changes to the global set.
