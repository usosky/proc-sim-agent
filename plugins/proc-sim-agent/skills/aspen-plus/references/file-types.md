# Aspen Plus files: what each holds, how to get it, what proc-sim-agent reads

## Model files

In the commands below, `fw` stands for `python scripts/fw.py`, run from the skill folder (see SKILL.md).

| File | Format | Holds | Editable? (does editing it change the model) | Notes |
|---|---|---|---|---|
| `.inp` input file | text | the whole input, no results | **Yes, the documented way**: export, edit, File > Open (Input Files); an `.inp` cannot be imported into an open case, only opened | `fw inp-check`, `inp-find`, `his --inp` (input-language.md) |
| `.bkp` backup | ASCII | all input and results, no intermediate convergence data | **No hand edits by this skill.** Aspen reads it on Open and on Import (File > Import > File merges it into the open case) | Portable across computers and **newer** versions; best for archiving and version folders. On rerun Aspen reinitializes and reconverges. |
| partial `.bkp` ("insert") | ASCII | input of some objects only: no results, no components | Made by Aspen (right-click an object > Export); imported into any case to add those objects | help: "What is an Insert?", "Exporting Partial Backup Files" |
| `.apw` document | binary | input, results and convergence state (quick restart) | No | Tied to the version that wrote it. |
| `.apwz` compound | zip | the model (a .bkp inside) plus every file it uses | Only through the `.bkp` inside | Good for sending a complete case; `examples-index` reads the .bkp inside. |
| `.apmbd` | binary | embedded objects (spreadsheets, pictures) | No (AspenTech: do not edit) | Keep it next to its `.bkp` or `.inp` (same name). |
| `.appdf` | binary | problem-definition arrays, intermediate convergence data | No | Rebuilt by Aspen; not needed for archiving. |
| `.def` | text | Export Definition file, saved with the document to keep EO variables | No | May hold the Windows user name: never read. |
| `.for` | text | Fortran saved with the case | No | Usually empty when inline Fortran is interpreted. |
| `.ads` | ? | appears beside saved V15 cases; not in the file-format topics | Unknown: treat as Aspen's, do not read or edit | |
| `.apt` template, `.apsst` stream-summary template, `.slb` stream library | | | No | |

To keep a simulation you need at least one of: the `.apw`, the `.apwz`, or the `.bkp` **plus**
its `.apmbd` if there is one (Aspen help, "File Formats in Aspen Plus").

**Policy: the skill never hand-edits `.apw`, `.appdf`, `.apmbd` or `.bkp`.** It changes models
through `.inp` files (opened in Aspen), Aspen's own Import (a section saved as `.bkp`), or
automation; input-language.md has the routes. Each route needs Aspen Plus with a licence: the
agent prepares text or drives Aspen, and Aspen applies the change. AspenTech does not generally
advise editing a `.bkp` directly; when a user repairs one by hand, they work on a copy and save it
with ANSI encoding (a UTF-8 save makes it unreadable to Aspen). The one exception in this
repository is `tools/scrub_aspen_files.py`, which blanks identifying lines in copies for sharing.

## Run outputs (text)

Run outputs are not editable: the next run or export rewrites them.

| File | How to get it (V12-V15) | Holds | proc-sim-agent |
|---|---|---|---|
| `.his` history | written by every run; view with Home > Summary > History; save from the editor or File > Export | input echo (numbered input-language lines, inline Fortran), input-translation messages, flowsheet analysis (convergence blocks, computation order), block-by-block trace with loop iterations, message IDs, and the summary of errors written at save | `fw his`, `fw his-diff` |
| `.cpm` run messages | File > Export > Save as type *Run Messages (\*.cpm)*; must be exported, it is not kept otherwise | what the Control Panel showed: progress, loop iterations, RadFrac iteration tables, messages **without IDs**, summary of simulation errors | `fw cpm` |
| `.rep` report | File > Export > *Report files (\*.rep)*; content set in Setup > Report Options | run control, flowsheet balance, convergence and design-spec results, every block's inputs/results, stream tables | `fw rep` |
| `.inp` input file | File > Export > *Aspen Plus Input Files*, *Input Files with Graphics* (object positions kept in a long comment) or *Input and Graphics Data File* (.inp + .apmbd); every .his starts with the input of its run | the whole input as text, no results; opens with File > Open > Input Files; the engine runs it with `aspen <runid>` | `fw inp-check`, `his --inp`, `inp-find`, `inp-diff` (input-language.md) |
| `.sum` summary | File > Export > Summary | results for programs; the same RUN-STATUS records as the results section of a `.bkp`; File > Import > Summary loads results into a case | run stamp only (freshness); no digest yet |
| `.xml` results | File > Export | results for Aspen Pinch and Icarus | not read |

Diagnostic detail of the .his and the Control Panel is set separately: globally in
Setup > Specifications > Diagnostics, per block in the block's Block Options > Diagnostics. For
heavy diagnostics raise the history level, not the Control Panel level (faster runs). The .his
has a size limit (Setup > Calculation Options > Limits, 500 MB by default).

## The file contract: one run, one set of files

After each run the user:

1. saves the `.bkp` and exports the `.rep` with the same name into the version folder;
2. when the run fails, also exports the `.cpm` (File > Export > Run Messages);
3. says which folder and file, the steps done and any deviation (and why), and their questions.

The agent then reads the files itself (no pasted tables) and first checks that the `.his`, `.rep`
and `.bkp` come from the same run. Sync clients (OneDrive, Proton Drive) and copies rewrite file
times, so the check reads the run stamps inside the files and never the file times:

| File | Stamp read | Means |
|---|---|---|
| `.his` | header of the last run (ORIGINAL, EDIT or RESTART RUN, date, time; `RUN ID`) | start of the last run in the file |
| `.bkp` | results section (`$_SUMMARY_FILE`): `RUN-STATUS` date, time and input file; line 1 `DATETIME` | results of a run on ...; when the file was saved |
| `.sum` | the same `RUN-STATUS` records | as the `.bkp` |
| `.rep` | first-page header (date and time) or the page-header date; `INPUT FILE NAME` | report written at the end of the run |
| `.cpm` | the last control-panel event (`<< Report exported 23:03:03 Fri Oct 2, 2026>>`) | latest event; never marks the others stale |

A file is **stale** when it describes an earlier run than another file of the same case (same
name in one folder): a different run ID (another session) and older by more than a minute; a
`.rep`, `.bkp` or `.cpm` stamped before the start of the last run in the `.his`; otherwise more
than 12 hours older than the newest stamp (one long run can put the `.rep` hours after the start).
`his`, `rep`, `cpm`, `bkp` and `check` print a `WARNING:` line first when the file read is stale,
and `sim-scan` lists stale files at the top. The fix: run, save, then File > Export > Report.
When the files agree, the commands print one line with their stamps ("Run stamps agree (one
run)"): a `.his` a few seconds or minutes before the `.rep` is one run, not two.
A `.bkp` saved without results after the run gets a note: its input may differ from the run's.

A `.his` keeps several runs when the case was run more than once in a session (EDIT RUN); the
digests describe the last run and say how many the file holds. `.apw` files are binary: their
run time cannot be read.

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
