# Live tests (Windows, licensed Aspen Plus V15)

These tests need a Windows PC with a licensed Aspen Plus, so they cannot run in CI. Use official
AspenTech examples copied to a temporary folder, never your own models. Report the results as
text (command outputs, pass or fail, what you saw); no model files are shared.

Commands run from the skill folder (`plugins\proc-sim-agent\skills\aspen-plus` in a clone, or the
installed copy such as `%USERPROFILE%\.claude\skills\aspen-plus`), in PowerShell or Git Bash.
`fw` below stands for `py -3 scripts\fw.py`. Pick a small example with a few blocks and a feed,
for instance:

```text
py -3 scripts\fw.py examples-search "flash" --block FLASH2 -n 5
```

Copy it to `C:\Temp\psa-live\` and work only on copies there.

## Install and automation

| # | Test | Pass |
|---|---|---|
| L0 | Install for both agents (below); in Claude Code and in VS Code Copilot agent mode ask *"Set up proc-sim-agent for my Aspen Plus help"* | Both agents load the skill, run `setup --auto` and `help-index` |
| L1 | `fw com-check --start` | Version printed, Aspen quits, licence released; note the "Members" and "Type library" lines |
| L2 | `fw com-tree` on the example with `--node "\Data\Streams" --depth 1`; `fw com-get` one stream temperature | Paths, and values with units |
| L3 | `fw com-run` on the example with one `--set` | `.bkp .rep .cpm .inp` and `automation-log.json`; `check` reads the `.rep`; the value shows in Aspen when the `.bkp` is opened |
| L4 | `fw com-edit` adding a Heater and two streams; open the result | The new block and streams are on the flowsheet; note where Aspen placed them |
| L5 | `fw com-sweep` with 3 points | CSV with a status per point |
| L6 | `--timeout 5` on a larger example | Run stopped, Aspen quit, no server process left |

### L0: install for both agents

Claude Code reads `%USERPROFILE%\.claude\skills`; GitHub Copilot CLI 1.0.105 reads
`%USERPROFILE%\.copilot\skills` and `%USERPROFILE%\.agents\skills`, not `.claude` (checked with
`copilot skill list`). VS Code's personal skill folders were not checked; this test records them.

```text
py -3 tools\install_skill.py --target claude
py -3 tools\install_skill.py --target copilot
```

Then ask each agent the set-up question in a new session. Report which agents loaded the skill.
To see whether VS Code also reads `.claude\skills`, remove the Copilot copy
(`py -3 tools\install_skill.py --target copilot --uninstall`), reload VS Code and check whether
the skill is still listed.

### L1-L6: commands

```text
py -3 -m pip install pywin32
fw com-check --start
fw com-tree "C:\Temp\psa-live\ex\<example>.bkp" --node "\Data\Streams" --depth 1
fw com-get "C:\Temp\psa-live\ex\<example>.bkp" --path "\Data\Streams\<stream>\Output\TEMP_OUT\MIXED"
fw com-tree "C:\Temp\psa-live\ex\<example>.bkp" --node "\Data\Streams\<feed>\Input" --depth 3
fw com-run "C:\Temp\psa-live\ex\<example>.bkp" --out "C:\Temp\psa-live\run1" --set "<input path from com-tree>=<value>"
fw check "C:\Temp\psa-live\run1\<example>.rep"
fw com-edit "C:\Temp\psa-live\ex\<example>.bkp" --out "C:\Temp\psa-live\edit1" --add-stream L4-IN --add-stream L4-OUT --add-block "H1!HEATER" --connect "H1:F(IN)=L4-IN" --connect "H1:P(OUT)=L4-OUT"
fw com-sweep "C:\Temp\psa-live\ex\<example>.bkp" --out "C:\Temp\psa-live\sweep1" --vary "<input path>=<v1>,<v2>,<v3>" --read "<result path>"
fw com-run "C:\Temp\psa-live\ex\<larger example>.bkp" --out "C:\Temp\psa-live\slow" --timeout 5
```

Report for each: the output (text), pass or fail, and these observations:

- L1: the "Members" line (Version, Engine.IsRunning) and the "Type library" line
  (IAP_REINIT_SIMULATION, HAP_ENTERABLE, export codes).
- L2: whether units appear next to the values (`UnitString`).
- L3: the run time; then open `run1\<example>.bkp` and check the changed value. Also compare three
  times, for WP4: the start of the run in `run1\<example>.his` if one was written, the
  `RUN-STATUS` time that `fw bkp` shows, and the `.rep` header time (`fw rep`): is the `.bkp` stamp
  the start or the end of the run?
- L4: whether `--connect` worked (the log shows it) and where Aspen placed H1.
- L6: whether the run was stopped, and in Task Manager whether an `AspenPlus.exe` started by the
  command was left (the command also says so).

The automated part of these checks is `tests\test_com_live.py`. In PowerShell:

```text
$env:PSA_LIVE_ASPEN = "1"
py -3 -m pytest tests\test_com_live.py -v
```

In Git Bash: `PSA_LIVE_ASPEN=1 py -3 -m pytest tests/test_com_live.py -v`. Set
`PSA_ASPEN_EXAMPLES` to the examples folder when `setup --auto` does not find it.

## Input files

| # | Test | Pass |
|---|---|---|
| T0-T3 | The input-file tests of the v0.2 test pack (`inp-tests\README.md` on the Aspen PC; not in this repository) | As in that README |
| T4 | Route A: export an example as *Input File with Graphics*, add one Heater block with two streams, open the `.inp` | The model opens, the old blocks keep their positions, the new block appears (note where) |
| T5 | Route B: a small `.inp` with one new block, saved as `.bkp`, then File > Import into a copy of the example | The blocks merge; note the ID-conflict dialog and every Setup or Options value that changed |

### T4, step by step

1. Copy the example to `C:\Temp\psa-live\T4\`, open it in Aspen Plus V15 and run it.
2. File > Export > *Input File with Graphics*, save as `C:\Temp\psa-live\T4\base.inp`.
3. Ask the agent: *"Copy base.inp in C:\Temp\psa-live\T4 to new.inp and add a Heater HX9 fed by a
   new stream T4-IN (10 kmol/h of one of the model's components, 25 C, 1 bar), outlet T4-OUT at
   40 C, no pressure drop."* Or add these paragraphs yourself (use a component of the model):

   ```text
   FLOWSHEET
       BLOCK HX9 IN=T4-IN OUT=T4-OUT

   STREAM T4-IN
       SUBSTREAM MIXED TEMP=25. <C> PRES=1. <bar> MOLE-FLOW=10. <kmol/hr>
       MOLE-FRAC <component> 1.

   BLOCK HX9 HEATER
       PARAM TEMP=40. <C> PRES=0.
   ```

   The `FLOWSHEET` line goes into the existing `FLOWSHEET` paragraph, not a second one.
4. Run, and keep the outputs for the report:

   ```text
   fw inp-diff "C:\Temp\psa-live\T4\base.inp" "C:\Temp\psa-live\T4\new.inp"
   fw inp-check "C:\Temp\psa-live\T4\new.inp"
   ```

5. File > Open > Input Files > `new.inp`; Run; File > Save As `new.bkp`.
6. Report: the `inp-check` output, the run status, whether the old blocks kept their positions,
   where HX9 and its streams appeared.

### T5, step by step

1. Copy the example again, to `C:\Temp\psa-live\T5\`.
2. Ask the agent: *"Write C:\Temp\psa-live\T5\section.inp: IN-UNITS, the components and property
   method of the example, a Heater HX9 with feed T5-IN and outlet T5-OUT. Use the ID of one existing
   stream of the example for the outlet, so that the import has an ID conflict."*
3. Check it:

   ```text
   fw inp-check "C:\Temp\psa-live\T5\section.inp"
   ```

4. Open `section.inp` in Aspen and save it as `section.bkp` (or, in the *Customize Aspen Plus V15*
   window, in that folder: `aspen section /mmbackup`). Note which of the two you used.
5. Before importing, note in the copy of the example: Setup > Specifications (units, global
   settings), Setup > Report Options, and File > Options.
6. In the copy of the example: File > Import > File, type Backup, `section.bkp`.
7. Report: the *Resolve ID Conflicts* dialog (what it offered, what you chose); whether HX9 and its
   streams are on the flowsheet; each Setup or Options value that changed after the import.

## Run stamps

The freshness check was written from real run files and synthetic files.
These checks confirm it on real runs:

| # | Test | Pass |
|---|---|---|
| R1 | Run an example, change one input, run again in the same session; save the `.bkp`, keep the `.his`, export the `.rep` | `fw his` says the file holds 2 runs and describes the second; `fw sim-scan` shows no warning |
| R2 | Export a summary file (File > Export > Summary, `.sum`) next to the `.bkp` | `fw sim-scan "<folder>" --json`: the `.sum` has a run time under `freshness` |
| R3 | A run that takes more than two minutes: compare the `.his` start, the `RUN-STATUS` time (`fw bkp`) and the `.rep` header time (`fw rep`) | Report the three times: is the `.bkp` stamp the start or the end of the run? |

## Evals in both agents

| # | Test | Pass |
|---|---|---|
| E1 | The eval cases in both agents (`evals/run.py`, or evals/MANUAL.md for VS Code) | Pass rates recorded in the `evals/results/` summary |

Signed in to each CLI, from the repository root:

```text
python evals/run.py --agent claude --repeat 3 --triggers
python evals/run.py --agent copilot --repeat 3 --triggers
```

Add `--use-my-index` to let the agent search your help and example indexes (the cases also work
without them). Commit `evals/results/<date>/<agent>/summary.md` and `summary.json`; the
transcripts stay on your PC. For VS Code agent mode follow evals/MANUAL.md.
