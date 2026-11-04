# Live tests (Windows, licensed Aspen Plus V15)

These tests need a Windows PC with a licensed Aspen Plus, so they cannot run in CI. Use official
AspenTech examples copied to a temporary folder, never your own models. Report the results as
text (command outputs, pass or fail, what you saw); no model files are shared.

Commands run from the skill folder (`skills\aspen-plus` in a clone, or the installed copy such as
`%USERPROFILE%\.claude\skills\aspen-plus`), in PowerShell or Git Bash. `fw` below stands for
`py -3 scripts\fw.py`. Pick a small example with a few blocks and a feed, for instance:

```text
py -3 scripts\fw.py examples-search "flash" --block FLASH2 -n 5
```

Copy it to `C:\Temp\psa-live\` and work only on copies there.

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
