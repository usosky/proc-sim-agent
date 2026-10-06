# Writing models as input files (.inp)

An input file is the whole problem definition as text: components, property method, flowsheet,
streams, blocks, calculators, specs. Aspen Plus opens one with **File > Open > Files of type:
Input Files (\*.inp)**, and the engine runs one directly (`aspen <runid>` in the *Customize Aspen
Plus V15* window). Every `.his` starts with the input of its run, so any run the user has made is
also a correct, version-matched input file.

`fw` below means `python "${CLAUDE_SKILL_DIR}/scripts/fw.py"`.

## When to write a file instead of giving click paths

| Write an .inp | Give GUI steps |
|---|---|
| many components, chemistry reactions, streams or calculator lines to enter | one or two fields to change |
| a new model or a new section built from a plan (build-mode.md) | the user wants to learn the forms |
| the same change in several model versions | Excel calculators, embedded objects, custom ACM/user models |
| reviewing exactly what a model contains (`fw his --inp`) | BatchSep blocks (connections do not survive an .inp) |

An input file carries no results and, unless it was exported "with graphics", no flowsheet
drawing: expect Aspen's own arrangement of the blocks on screen; tidy it once, then save as `.bkp`.

## The cycle

1. **Start from something that runs.** In order of preference:
   - the user's own model: `fw his "<run.his>" --inp base.inp` writes the input of its last run;
   - an example: `fw examples-show <id> --chemistry-inp`, or `--section "BLOCK RADFRAC"` to see how
     AspenTech set a block up (examples.md);
   - the template below.
2. **Write the file** in the version folder the user names (one folder per model version, see
   workflows.md section 3). Name it after the model; the run ID is the file name, so keep it short
   and without spaces.
3. **Check it:** `fw inp-check <file.inp>`. Fix every ERROR. Read each WARNING; keep one only when
   you can say why it is fine. The checker does not know every keyword: Aspen Plus is the judge.
4. **The user opens and runs it:** File > Open > Input Files (\*.inp) > Run. Then **File > Save As**
   `.bkp` in the same folder (the .inp keeps no results) and export `.rep`.
5. **Read the run:** `fw his <folder>` (messages with IDs; the input echo shows how Aspen read
   the file), `fw rep`, `fw check` for balances and KPIs.
6. Translation errors point at input lines: the `.his` echo numbers the lines of the file as read.

## Language rules (checked against V15 input echoes)

- A paragraph keyword starts in column 1 (`BLOCK`, `STREAM`, `CALCULATOR` ...); its statements are
  indented (4 spaces). Write keywords and IDs in upper case.
- Lines up to 80 characters; continue a statement with ` &` at the end of the line. A list
  continues by itself after a trailing `/` (`METHANOL CH4O /` then `WATER H2O` on the next line).
- `;` starts a comment line. Numbers like `25.` or `1.5E-3`. Text in single quotes for databank
  names and titles, double quotes for expressions (`SPEC "X" TO "0.01"`, `LIMITS "20" "80"`).
- IDs (blocks, streams, components, calculators): 8 characters or fewer, starting with a letter;
  `-` is allowed (`CO2-REAC`). Ions are named with their charge (`H3O+`, `CO3-2`, `MEAH+`). IDs
  with other special characters go in double quotes: `"NACL(S)" NACL`.
- Units: `IN-UNITS` sets them for the whole file; one value can override it: `PRES=70. <mbar>`,
  `TEMP=20. <C>`, `MOLE-FLOW=1000. <kmol/hr>`. **Without IN-UNITS every number is read in ENG
  units** (F, psia, lbmol/hr).
- Inline Fortran: `F` in column 1, code from column 7 to 72; `C` in column 1 for comments. The
  rules of calculators.md apply (fixed form, no tabs, copy imported variables before changing them).

## Template: a complete small model

```
TITLE 'Methanol-water flash'
IN-UNITS MET PRESSURE=bar TEMPERATURE=C DELTA-T=C PDROP=bar
DEF-STREAMS CONVEN ALL
DATABANKS 'APV150 PURE41' / 'APV150 AQUEOUS' / 'APV150 SOLIDS' &
         / 'APV150 INORGANIC' / NOASPENPCD
PROP-SOURCES 'APV150 PURE41' / 'APV150 AQUEOUS' / 'APV150 SOLIDS' &
         / 'APV150 INORGANIC'
COMPONENTS
    METHANOL CH4O /
    WATER H2O
PROPERTIES NRTL
FLOWSHEET
    BLOCK MIX IN=FEED MAKEUP OUT=S1
    BLOCK HEAT IN=S1 OUT=S2
    BLOCK FL1 IN=S2 OUT=VAP LIQ
STREAM FEED
    SUBSTREAM MIXED TEMP=25. PRES=1.5 MOLE-FLOW=100.
    MOLE-FRAC METHANOL 0.4 / WATER 0.6
STREAM MAKEUP
    SUBSTREAM MIXED TEMP=25. PRES=1.5
    MOLE-FLOW WATER 10.
BLOCK MIX MIXER
    PARAM
BLOCK HEAT HEATER
    PARAM TEMP=80. PRES=0
BLOCK FL1 FLASH2
    PARAM TEMP=80. PRES=1.
STREAM-REPOR MOLEFLOW MASSFLOW MOLEFRAC
```

Complete files to start from are in `${CLAUDE_SKILL_DIR}/templates/`:
`flash-calculator-sensitivity.inp`, `column-specs.inp` (RadFrac with internal specs inside a design
spec) and `electrolyte-absorber.inp` (true-component chemistry, Henry components, pH, sensitivity).
Copy one into the user's folder and edit it; do not edit the templates.

**Databanks are release-specific.** `APV150` is V15 (V15 default pure databank `PURE41`). For
another release copy `DATABANKS` and `PROP-SOURCES` from one of the user's runs in that release
(`fw his <file> --echo`, first lines). `inp-check` says which release the names belong to.

**Binary parameters:** the file names only the method (`PROPERTIES NRTL`). After opening it, check
**Properties > Methods > Parameters > Binary Interaction > NRTL-1** (or the method's form): pairs
with databank values are filled in; an empty pair has none, and the user must supply it
(regression, estimation, literature) before results are used. Never type binary values that do not
come from a databank, a regression or a paper.

## Paragraphs

Forms below were read from V15 input echoes (`.his`) or match the keywords stored in V15 `.bkp`
files; *unconfirmed* marks forms not yet seen in a V15 run. `fw inp-find <KEYWORD>` shows more from
the user's own runs.

Components, properties, chemistry:
```
COMPONENTS
    H2O H2O /
    CO2 CO2 /
    MEA C2H7NO /
    H3O+ H3O+ /
    HCO3- HCO3- /
    CO3-2 CO3-2
HENRY-COMPS GLOBAL CO2 N2
CHEMISTRY C-1
    STOIC 1 H2O -2. / H3O+ 1. / OH- 1.
    STOIC 2 CO2 -1. / H2O -2. / HCO3- 1. / H3O+ 1.
    K-STOIC 1 A=132.899 B=-13445.9 C=-22.4773
    K-STOIC 2 A=231.465 B=-12092.1 C=-36.7816
    DISS NAOH NA+ 1. / OH- 1.
PROPERTIES ELECNRTL CHEMISTRY=C-1 HENRY-COMPS=GLOBAL TRUE-COMPS=YES
```
- Second word on a `COMPONENTS` line is the databank alias (formula, sometimes with an isomer
  suffix: `TEA C6H15N-2`); none for a component defined by the user (add `FORMULA`, properties, or
  `ESTIMATE`). Solids: `CISOLID-COMPS ID ...`. **Get aliases with `fw comp-find <name or formula>`**
  (the aliases the indexed example models use, e.g. `MEA C2H7NO`) or `fw inp-find COMPONENTS`;
  when neither has it, the user looks it up in Components > Specifications > Find. Never guess an
  alias: a wrong one silently picks another compound or fails.
- Components of type Solid (salts that precipitate, inert solids) are also listed in
  `CISOLID-COMPS "NACL(S)"`; the help: *required only if you use components of type Solid in the
  MIXED substream*.
- `K-STOIC` A, B, C, D: ln K = A + B/T + C ln T + D T (T in K; default basis mole fraction times
  activity coefficient). A reaction without K-STOIC takes K from Gibbs energies of formation.
- `CHEMISTRY=` on a PROPERTIES statement matches the V15 .bkp keyword (next to HENRY-COMPS and
  TRUE-COMPS, which V15 echoes confirm). *Unconfirmed:* the positional forms of `DISS` (complete
  dissociation), `SALT` (precipitation) and `K-SALT`, written like STOIC and K-STOIC; the first
  run of `templates/electrolyte-absorber.inp` confirms DISS.
- `TRUE-COMPS=YES` is the true-component approach; use it whenever the chemistry produces volatile
  species (CO2, NH3, H2S, HCl) - Aspen help, *Choosing the True or Apparent Approach*.
- A `PROPERTIES` statement inside a BLOCK paragraph sets that block's method:
  `PROPERTIES NRTL HENRY-COMPS=GLOBAL FREE-WATER=STEAM-TA SOLU-WATER=3 TRUE-COMPS=YES`.

Streams:
```
STREAM FEED
    SUBSTREAM MIXED TEMP=25. PRES=1. MOLE-FLOW=100.
    MOLE-FRAC CO2 0.1 / H2O 0.9
STREAM MAKEUP
    SUBSTREAM MIXED TEMP=25. PRES=1.
    MOLE-FLOW H2O 10. / MEA 1.
```
Exactly two of TEMP, PRES, VFRAC. Either component flows, or a total flow on SUBSTREAM plus
fractions (MOLE-FRAC, MASS-FRAC). A stream that is computed (a tear) may carry estimates the same
way.

Blocks (each needs a `FLOWSHEET` line `BLOCK id IN=... OUT=...`):
```
BLOCK MIX MIXER
    PARAM
BLOCK SPL FSPLIT
    FRAC PURGE 0.05
BLOCK SEP1 SEP
    PARAM
    FRAC STREAM=CO2 SUBSTREAM=MIXED COMPS=CO2 FRACS=1.
BLOCK COOL HEATER
    PARAM TEMP=40. PRES=0
BLOCK KO FLASH2
    PARAM TEMP=40. PRES=0
BLOCK HX1 HEATX
    PARAM T-HOT=37. CALC-TYPE=DESIGN U-OPTION=PHASE F-OPTION=CONSTANT  &
        CALC-METHOD=SHORTCUT
    FEEDS HOT=LEAN COLD=RICH
    OUTLETS-HOT LEAN2
    OUTLETS-COLD RICH2
BLOCK P1 PUMP
    PARAM PRES=10.
BLOCK K1 COMPR
    PARAM TYPE=ISENTROPIC PRES=5. SEFF=0.75
BLOCK V1 VALVE
    PARAM P-OUT=1.5
BLOCK R1 RSTOIC
    PARAM TEMP=120. PRES=120.
    STOIC 1 MIXED CO2 -1. / H2 -1. / HCOOH 1.
    CONV 1 MIXED CO2 0.82
BLOCK C1 RADFRAC
    PARAM NSTAGE=20
    COL-CONFIG CONDENSER=TOTAL
    FEEDS F 10
    PRODUCTS D 1 L / B 20 L
    P-SPEC 1 1.013
    COL-SPECS D:F=0.4 MOLE-RR=2.
    SPEC 1 MOLE-FRAC 0.99 COMPS=METHANOL STREAMS=D
    VARY 1 MOLE-RR 0.5 10.
    SPEC 2 MOLE-RECOV 0.99 COMPS=METHANOL STREAMS=D BASE-STREAMS=F
    VARY 2 D:F 0.2 0.6
```
- `PRES=0` (Heater, Flash2) means no pressure drop; a negative value is a pressure drop.
- Flash2/Flash3: exactly two of TEMP, PRES, VFRAC, DUTY. Heater: two of TEMP (or DELT, DEGSUB,
  DEGSUP), PRES, VFRAC, DUTY.
- RadFrac: every connected stream in FEEDS or PRODUCTS (stage; `ON-STAGE` for a vapour feed to the
  bottom stage; phase L/V for products); one COL-SPECS value per condenser and per reboiler
  (`COL-CONFIG CONDENSER=NONE REBOILER=NONE` for an absorber needs none); internal SPEC/VARY pairs
  adjust them. `MOLE-RECOV` specs and `VARY n MOLE-RR low high [max step]` were seen in V15 runs;
  a `MOLE-FRAC` spec is *unconfirmed* (same pattern).
- Other blocks (RPlug, RCSTR, RGibbs, MCompr, Extract ...): get the exact form first (below).

Flowsheeting objects:
```
CALCULATOR C-1
    DEFINE FMU MOLE-FLOW STREAM=MAKEUP SUBSTREAM=MIXED COMPONENT=WATER  &
        UOM="kmol/hr"
    DEFINE FTOT STREAM-VAR STREAM=FEED SUBSTREAM=MIXED VARIABLE=MOLE-FLOW  &
        UOM="kmol/hr"
F     FMU = 0.1 * FTOT
    READ-VARS FTOT
    WRITE-VARS FMU
DESIGN-SPEC DS-1
    DEFINE XCO2 MOLE-FRAC STREAM=GAS SUBSTREAM=MIXED COMPONENT=CO2
    SPEC "XCO2" TO "0.01"
    TOL-SPEC "0.0001"
    VARY STREAM-VAR STREAM=SOLV SUBSTREAM=MIXED VARIABLE=MOLE-FLOW  &
        UOM="kmol/hr"
    LIMITS "10" "500"
SENSITIVITY S-1
    DEFINE XMV MOLE-FRAC STREAM=VAP SUBSTREAM=MIXED COMPONENT=METHANOL
    DEFINE QFL BLOCK-VAR BLOCK=FL1 VARIABLE=QCALC SENTENCE=PARAM UOM="kW"
    TABULATE 1 "XMV"
    TABULATE 2 "QFL"
    VARY BLOCK-VAR BLOCK=FL1 VARIABLE=TEMP SENTENCE=PARAM UOM="C"
    RANGE OPT-LIST=RANGE LOWER="70" UPPER="95" INCR="5"
CONV-OPTIONS
    PARAM TEAR-METHOD=WEGSTEIN
    WEGSTEIN MAXIT=100
DISABLE
    DESIGN-SPEC DS-1
STREAM-REPOR MOLEFLOW MASSFLOW MOLEFRAC
```
- DEFINE types: `MOLE-FLOW`, `MASS-FLOW`, `MOLE-FRAC` (with COMPONENT), `STREAM-VAR` (VARIABLE=TEMP,
  PRES, MOLE-FLOW ...), `BLOCK-VAR` (BLOCK, VARIABLE, SENTENCE, and ID1 for indexed values such as
  a reaction number). UOM sets the unit the code sees.
- Calculator: READ-VARS are imported, WRITE-VARS exported; these also fix the calculation order.
- Design spec: SPEC, TOL-SPEC, VARY and LIMITS are all required. Sensitivity: VARY, RANGE and at
  least one TABULATE.

## Getting a form you have not written before

1. `fw inp-find RGIBBS` (or a paragraph or statement keyword: `DESIGN-SPEC`, `COL-SPECS`): shows the
   paragraph as the user's own Aspen Plus wrote it in earlier runs (registered simulation folders,
   or pass a folder). Same release, so the safest source.
2. `fw examples-show <id> --section "BLOCK RGIBBS"`: how AspenTech set the block up. The .bkp
   stores the same keywords, but list sentences carry named fields (`FEEDS FEED-SID=F
   FEED-STAGE=60` is `FEEDS F 60` in an input file); `PARAM` keywords are the same in both.
3. The help: `fw help-search "<block> input language"`; Aspen Polymers topics *Using Input
   Language* have formal descriptions of several paragraphs.
4. Ask the user to build that one block in the GUI and **File > Export > Input file**, or to tick
   *Edit keyword input before starting calculations* (Run Settings) and copy the generated text.

## What the checker does and does not catch

`inp-check` finds: missing IN-UNITS, COMPONENTS or PROPERTIES; components used but not declared;
streams with two sources or two destinations; blocks without a BLOCK paragraph or not connected;
feeds without two state variables or without flow; missing minimum block specs (Flash2/3, Heater,
Pump/Compr/MCompr, Valve, RStoic STOIC+CONV, RadFrac, FSplit); unbalanced reactions (charge;
elements when aliases are formulas); chemistry that no PROPERTIES statement uses; the apparent
approach with volatile products; DESIGN-SPEC/SENSITIVITY statements missing; READ-VARS or
WRITE-VARS not defined; DISABLE of unknown objects; Fortran column, tab and naming problems;
unbalanced quotes and parentheses; lines over 80 characters; databanks of another release.

It does not know: whether a keyword exists for that block, whether values make physical sense,
whether specs are feasible, whether binary parameters exist. Those show up in the run: read the
`.his` with `fw his`.
