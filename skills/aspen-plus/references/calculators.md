# Calculator blocks, design specs and Parameters: rules that prevent most problems

Flowsheeting Options > Calculator (and Design Spec, Sensitivity) use the same three pieces:
the **Define** sheet (variables), the code (**Calculate** sheet: inline Fortran or Excel) and
the **Sequence** sheet (when it runs). Check exact field names in your version with
`fw.py help-search "calculator define sheet" --book hlpflwop`.

## 1. Define sheet

Each row: name, information flow (Import / Export / Tear), type, reference, units. The help states
it plainly: Import variables can only be read; Export and Tear variables can be changed.

| Type | Use for | Pitfall |
|---|---|---|
| Mole-Flow / Mass-Flow / StdVol-Flow | flow of **one component** in one stream/substream | choose the component the reaction is based on (key component) |
| Mole-Frac / Mass-Frac | fraction of one component | - |
| Stream-Var | stream-level variable: TEMP, PRES, total MOLE-FLOW, VFRAC... | Stream-Var MOLE-FLOW is the **total** flow, not a component flow |
| Block-Var | a block input or result (sentence + variable, with ID1/ID2 for arrays such as reaction number) | reading and writing the same block gives ADFORT.8 |
| Parameter (number, Init value) | scenario inputs and values shared between calculators and design specs | set the Init value in exactly **one active** block |
| Unary-Param / Binary-Param | property parameters (e.g. MW of a component) | units follow the parameter |
| Local-Param | internal results you want to see on the Results sheet | "initial value missing" information is harmless |

- Aspen uses Imports and Exports to place the calculator in the computation order (see 3).
- Not allowed as Export: Mole-Frac, Mass-Frac, StdVol-Frac, Stream-Prop, and the Stream-Var
  enthalpies, entropies, densities and LFRAC. Set flows (or a feed's component flows) instead.
- When a row uses both the total flow and component flows of the same stream, define the
  component flows first (Move Up/Down).
- Units on the Define row are the units the code sees. They are copied from the global unit set
  when the row is created and do not follow later unit changes. Writing `1.0D5` Pa when the row
  is in bar is a classic silent error; put the units in a comment next to each use.
- Names must match the code exactly. A misspelt name in the code is a new local variable that
  starts at zero; the `his` digest lint reports names that are used but never defined or set.
- Values a calculator (or a design spec) writes stay in the model after the run. If you stop
  writing a variable, its last written value remains until you change it or Reinitialize.

## 2. Inline Fortran (fixed form)

- Statements start in **column 7** (6 spaces); a comment has `C` in column 1; a continuation line
  has a character in column 6; nothing after **column 72** is read (silently); **no tabs**.
- Use double precision literals (`1.0D0`, `8.314D0`) and intrinsics (`DEXP`, `DLOG`, `DABS`, `DSQRT`).
- Declarations (arrays, COMMON, explicit types) go in the Declarations dialog, not on the
  Calculate sheet. The Calculate sheet can also use the built-in spreadsheet or Excel instead
  of Fortran; with Excel every variable must be Import or Export.
- Copy every Import to a local variable at the top and work on the copy (avoids ADFORT.7):
  ```fortran
  C     ---- local copies of imports
        TL  = TIN
        PL  = PIN
  C     ---- guards on the copies, never on the imports
        IF (TL .LT. 200.0D0) TL = 298.15D0
  ```
- Guard divisions and logs (`IF (X .LT. 1.0D-30) X = 1.0D-30`) and clip exports to physical
  ranges (conversions between 1D-6 and 0.999).
- Keep only fitted constants and physical constants in the code. Process conditions (T, P,
  compositions, flows) are read from streams or blocks; scenario values are Parameters. Then the
  model reacts to flowsheet changes instead of hiding inputs in code.

## 3. Sequence sheet

Options: First, Last, Before <block>, After <block>, Report, Based on order in sequence, and
**Use import/export variables**, which the help recommends: Aspen places the calculator after
the blocks/streams it imports from and before those that read its exports.
- First and Last run once per complete run, not once per Sensitivity case.
- Report runs while the report is written; exports have no effect there (use it only to print).
- An explicit point (First, Last, Before, After) fixes the position, and Aspen then **does not
  use the Import/Export list for ordering**; the help warns it can stop other sequencing
  mechanisms from working. Fine for a calculator that sets a block input just before that block
  (ADFORT.8 is then harmless), but:
- A calculator that **reads a Parameter varied by a design spec** must use import/export
  sequencing; otherwise Aspen sees no path from the Vary variable to the spec and deletes the
  spec's convergence block (see messages.md, flowsheet-analysis messages).
- A calculator that references a deactivated block, or runs Before/After one, is deactivated
  too ("deactivated by association", listed in the history file). Its exports then stop
  changing but keep their last values.
- After changing the sequence, run and read the computation order in the Control Panel or the
  `his` digest: the calculator must sit where you expect.

## 4. Parameters

- A Parameter is a numbered flowsheet variable (Define row type Parameter, number, Init value).
- Give the Init value in **one active** block. If the only Init sits in a deactivated block,
  Aspen uses a missing-value placeholder (about 1E35): enormous flows, mass imbalances, conversions
  scaled to nothing (messages.md, "SAMPLED VARIABLE ... HAS NOT BEEN CALCULATED", GETADD.36).
- Use Parameters for scenario inputs (a target recovery, a derating factor, a cycle time) so a case
  study changes one number.

## 5. Design specs

- Sheets: Define, Spec, Vary (plus Fortran and Declarations). Converged when
  |Spec - Target| < Tolerance, in the spec's units.
- Spec, Target and Tolerance accept numbers, variable names or Fortran expressions, and numbers
  follow the **Windows regional settings**: with a comma decimal separator type `0,001`. A comma
  inside a Fortran expression can then be misread; compute such expressions on the Fortran sheet.
- To change the Target from a Sensitivity block (or a case study), make the Target a Parameter.
- Vary: only block inputs or feed-stream variables (or a Parameter); not integer inputs such as a
  feed stage. The value already entered on the block/stream form is the first guess.
- Give realistic Lower/Upper limits. If the answer lies outside them, Aspen stops at the limit
  that comes closest and the spec is not met: check the spec's results, not only the run status.
- Optional step sizes are fractions of (upper - lower); Secant defaults are 0.01 and 1, with
  30 flowsheet evaluations.
- Flat or non-monotonic responses (e.g. a recovery that stays at 100 % while one reactant is in
  excess) stall the secant method. Convergence > Conv Options > Methods > Secant (or the Parameters sheet of a
  user Secant block): Bracket = **Yes** for flat regions, **Check Bounds** if it also gets stuck at
  a limit (it then tries the other limit too).
- A varied value stays in the model after the run (like calculator exports): Reinitialize (Home >
  Run > Reset) to start again from the value typed on the form, or Home > Run > Reconcile to copy
  the converged value into the form.
- To use a deactivated spec: right-click > Activate, then Reinitialize, then Run.
- In true-species electrolyte models, varying the flow of an electrolyte component often fails;
  vary a pure-component stream that is mixed in, or use the apparent approach.

## 6. Streams written by calculators

Use the Mole-Flow (or Mass-Flow) basis with **Total flow empty** on the stream's Input form.
With a total typed in, Aspen rescales the components (STSTRM.29) and can undo what the
calculator wrote.

## 7. Reactions driven by calculators

When a calculator sets an RStoic conversion, cap it at what the limiting co-reactant can supply,
or RStoic rescales it (URE07.3) and the co-reactant disappears completely. For A + B -> C with the
conversion based on A:
```fortran
      XMAX = 0.999D0 * FB / FA
      IF (XMAX .LT. 1.0D-6) XMAX = 1.0D-6
      IF (XCONV .GT. XMAX) XCONV = XMAX
```
`FA` and `FB` are Import rows (component Mole-Flow of A and B in the reactor feed) and must be
defined before the lines are pasted; for other stoichiometry divide by the coefficients.

## 8. Closed loops (solids, catalyst, solvent)

Steady state needs every loop to be mass-balanced. Fresh material added on every pass with no
outlet accumulates, and the tear never converges (CONVI.1, then BALMAS.1/CHKCVG.1). Either
- keep the loop open and model one steady cycle (the regenerated stream is fed back as a feed in
  the state that re-enters the first unit), or
- close it with a purge (FSplit) plus a make-up stream set by a calculator, and vary the
  circulating flow (a Parameter) with the design spec.
Zero-flow warnings in iteration 0 after Reinitialize are expected in closed loops.

## 9. Pressures

Enter pressure **changes** where the physics is a drop or rise (0 or negative = drop on
Heater/RStoic/Flash forms; pressure increase on Compr/Pump), not absolute pressures copied from
one case: absolute values break when the inlet pressure changes. In blocks with several feeds
the outlet pressure is based on the lowest feed pressure, so a low-pressure recycle can drag the
outlet down; set the outlet pressure explicitly if that is wrong for your case.

## 10. Working practice

- File > Save As a **new version** before each change; **one change per version**, one folder per
  version, a short notes file saying what changed and why (`sim-scan` shows it).
- Run after each step. Read the computation order and the messages, not only the final status.
- Verify calculator code outside Aspen: copy the Fortran into a small program, feed the "Value
  read" numbers from the calculator's Results sheet, and compare with "Value written":
  ```fortran
        PROGRAM TEST
        IMPLICIT DOUBLE PRECISION (A-H, O-Z)
        TIN = 298.15D0
        PIN = 101325.0D0
  C     ... paste the calculator code here ...
        WRITE(*,*) 'XCONV =', XCONV
        END
  ```
  `gfortran -ffixed-form test.f && ./a.out` (or port the code to Python). Matching to 6 digits
  proves the code Aspen ran is the code you think it ran.
- Work in a local folder, not a cloud-synced one (OneDrive, Dropbox, Google Drive): sync conflicts copy
  open .apw files. Copy the .bkp back at milestones.
