# Aspen Plus files: what each holds, how to get it, what proc-sim-agent reads

## Model files

| File | Format | Holds | Notes |
|---|---|---|---|
| `.bkp` backup | ASCII | all input and results, no intermediate convergence data | Portable across computers and **newer** versions; best for archiving and version folders. On rerun Aspen reinitializes and reconverges. |
| `.apw` document | binary | input, results and convergence state (quick restart) | Tied to the version that wrote it. |
| `.apwz` compound | zip | the model (a .bkp inside) plus every file it uses | Good for sending a complete case; `examples-index` reads the .bkp inside. |
| `.apmbd` | binary | embedded objects (spreadsheets, pictures) | Keep it next to its `.bkp` (same name). |
| `.appdf` | binary | problem-definition arrays, intermediate convergence data | Rebuilt by Aspen; not needed for archiving. |
| `.apt` template, `.apsst` stream-summary template, `.slb` stream library | | | |

To keep a simulation you need at least one of: the `.apw`, the `.apwz`, or the `.bkp` **plus**
its `.apmbd` if there is one (Aspen help, "File Formats in Aspen Plus").

The `.bkp` is readable text, but edit it only as a last resort: save it with ANSI encoding (a
UTF-8 save makes it unreadable to Aspen) and keep the original.

## Run outputs (text)

| File | How to get it (V12-V15) | Holds | proc-sim-agent |
|---|---|---|---|
| `.his` history | written by every run; view with Home > Summary > History; save from the editor or File > Export | input echo (numbered input-language lines, inline Fortran), input-translation messages, flowsheet analysis (convergence blocks, computation order), block-by-block trace with loop iterations, message IDs, and the summary of errors written at save | `fw.py his`, `fw.py his-diff` |
| `.cpm` run messages | File > Export > Save as type *Run Messages (\*.cpm)*; must be exported, it is not kept otherwise | what the Control Panel showed: progress, loop iterations, RadFrac iteration tables, messages **without IDs**, summary of simulation errors | `fw.py cpm` |
| `.rep` report | File > Export > *Report files (\*.rep)*; content set in Setup > Report Options | run control, flowsheet balance, convergence and design-spec results, every block's inputs/results, stream tables | `fw.py rep` |
| `.inp` input file | File > Export > *Aspen Plus Input Files*, *Input Files with Graphics* or *Input and Graphics Data File* (.inp + .apmbd); every .his starts with the input of its run | the whole input as text, no results; opens with File > Open > Input Files; the engine runs it with `aspen <runid>` | `fw.py inp-check`, `his --inp`, `inp-find` (input-language.md) |
| `.sum` summary | File > Export > Summary | results for programs | `sim-scan` only |

Diagnostic detail of the .his and the Control Panel is set separately: globally in
Setup > Specifications > Diagnostics, per block in the block's Block Options > Diagnostics. For
heavy diagnostics raise the history level, not the Control Panel level (faster runs). The .his
has a size limit (Setup > Calculation Options > Limits, 500 MB by default).

Recommended habit: after each meaningful run export `.rep` and `.cpm` next to the `.bkp`, with the
same name, in that version's folder. Then the run can be reviewed without opening Aspen.

## Engine versions

Headers carry the engine version: `.bkp` (`VERSION "39.0"`), `.his` (`VERSION: 41.0 Build ...`),
`.rep` (`VER: 41.0`).

| Engine | Release |
|---|---|
| 34.0 | V8.8 |
| 35.0 | V9 |
| 36.0 | V10 |
| 37.0 | V11 |
| 38.0 | V12 |
| 39.0 | V12.1 |
| 40.0 | V14 |
| 41.0 | V15 |

A `.bkp` saved in V12.1 and run in V15 shows engine 39.0 in the `.bkp` and 41.0 in the `.his` and
`.rep`; `sim-scan` reports it as "V12.1 file, run in V15". Results can differ slightly between
releases (databank updates, solver changes); say so when comparing with a publication.

## Engine working files and recovery copies

- `_xxxxxxx.*` (underscore + 7 characters: `.inm .in0 .inx .nin .sin .sor .rp1 .rp2 .jnl .scr .ads
  .prd .dyl .plf .sum .his .for`): the simulation engine's working files for an open or crashed
  session. The `.his` among them names the model in its `Runid` line, which is how `sim-scan`
  links them to a model. Safe to delete once Aspen is closed; while a case is open, leave them.
- `$<name>$backup.bk$` (and `.hc$`, `.xm$`) appear next to a case while it is open, and files
  named `<name>$backup.bkp` after a recovered session. The help does not document them: keep them
  until the main file opens and runs, then tidy up.
- A `.bkp` that crashes Aspen on opening: work on a copy and try File > Repair File, which removes
  the ADS and/or shell-settings sections of a backup file.
- `.def` and `.scr`: engine settings and scratch data. They can contain the Windows user name and
  install paths. proc-sim-agent lists them but never reads them.

## Privacy before sharing files

| File | What identifies you | Action |
|---|---|---|
| `.his`, `.rep` | `THIS COPY OF ASPEN PLUS LICENSED TO <organisation>`; `.rep` also `LOCATED IN:` lines; `.his` line `;Directory <path> Runid ...` | remove or replace those lines |
| `.bkp` | `DSET RUN-STATUS VERS (... "<user>" "<computer>")`, input-file path in the run status | blank the user and computer fields |
| `.cpm` | usually nothing | check anyway |
| `.def`, `.scr`, `_xxxxxxx.*` | user name, paths | do not share |

proc-sim-agent's digests leave out the licence line, user and computer names and run folders; raw views
(`rep --find`, `rep --section`) show other text as it is in the file.
`tools/scrub_aspen_files.py` in the repository makes a scrubbed copy for publishing (it keeps
the original encoding).
