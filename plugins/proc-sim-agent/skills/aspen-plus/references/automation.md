# Automation (COM): run, sweep and edit copies of a model

In the commands below, `fw` stands for `python scripts/fw.py`, run from the skill folder (see SKILL.md).

Aspen Plus is an automation server (ProgID `Apwn.Document`): a Python script can open a case,
change inputs, run it, read results and save files. The `com-*` commands do that on **copies**.
They need Windows, a licensed Aspen Plus on the same PC (each session takes a licence like the
GUI) and pywin32 (`python -m pip install pywin32`). Nothing else in the skill needs them.

## When to use automation, an input file or GUI steps

| Use | When |
|---|---|
| GUI steps (gui-navigation.md) | one or two fields; the user wants to learn the forms |
| an `.inp` (input-language.md) | a new model or a new section; many entries; reviewing all of the input |
| automation | the same model run many times (sweeps, cases, a design table); reading many values with their units; small flowsheet edits on a large model that would be slow to retype |

Start with what is already converged: automate runs of an existing model first, then sweeps,
then flowsheet edits. Check the setup once: `fw com-check --start`.

## The commands

```text
fw com-check --start
fw com-tree "<model.bkp>" --node "\Data\Streams" --depth 1
fw com-get "<model.bkp>" --path "\Data\Streams\FEED\Output\TEMP_OUT\MIXED"
fw com-run "<model.bkp>" --out "<new folder>" --set "\Data\Blocks\B1\Input\TEMP=40"
fw com-sweep "<model.bkp>" --out "<new folder>" --vary "\Data\Blocks\B1\Input\TEMP=30,40,50" --read "\Data\Blocks\B1\Output\QCALC"
fw com-edit "<model.bkp>" --out "<new folder>" --add-stream S9 --add-stream S10 --add-block "H1!HEATER" --connect "H1:F(IN)=S9" --connect "H1:P(OUT)=S10"
```

| Command | Does | Writes |
|---|---|---|
| `com-check [--start]` | Windows? pywin32? `Apwn.Document` and the versioned ProgIDs in the registry (engine 41.0 = V15, see file-types.md); `--start` starts the server once, prints its version and quits | nothing |
| `com-get`, `com-tree` | values with units, and node names (a text Variable Explorer), from a temporary copy; no run, no save | nothing |
| `com-run` | copies the model (and its `.apmbd`) to `--out`, applies each `--set` (logs old -> new), runs with a timeout, reads the status flags | `.bkp` `.rep` `.cpm` `.inp` (with graphics), `automation-log.json`; then prints the `rep` and `check` digests |
| `com-sweep` | one session, one run per point (`--vary` lists are taken point by point) | `sweep.csv` (status and flags per point, units in the header), the log |
| `com-edit` | adds or removes blocks and streams, connects ports (names checked against the block's ports first), optional `--set` and `--run` | a new `.bkp` and `.inp`; the user opens the `.bkp` to see the change |

Options: `--reinit` (reinitialize before running), `--timeout <seconds>` (default 900; the run is
stopped and Aspen quits), `--visible` (show the window), `--json`. Exit code 1 means the run did
not complete or the status flags show errors; 2 means the command refused or could not start.
In an interactive Git Bash, `!` inside double quotes expands history: write `--add-block H1=HEATER`
there (PowerShell and agents' shells accept `"H1!HEATER"`).

## Safety rules (built into the commands)

- The source file and its folder are never changed. `--out` must be a new or empty folder outside
  the model's folder. `com-get` and `com-tree` open a temporary copy and delete it.
- A frozen gate is refused for `com-run`, `com-sweep` and `com-edit`: a `FROZEN` marker file in the
  version folder, or `STATUS.md` (in the folder or up to two levels above) listing the version as
  frozen. Save As the next version and automate that one.
- One server per command, always quit at the end (the licence is released only then). Processes
  the command did not start are never touched; if its server does not exit, the output says which
  process (PID) to end.
- Only the paths given with `--set` change. Result nodes (`...\Output\...`) and nodes Aspen marks
  as not enterable are refused, so are paths that do not exist (find them with `com-tree`).
- Dialogs are suppressed. `Engine.Reinit()` without an argument shows one, so `--reinit` uses the
  constant `IAP_REINIT_SIMULATION` from the server's type library and refuses when it is missing.

## Finding node paths

Paths start at `\Data`: `\Data\Streams\<id>\Input\...` and `...\Output\...`,
`\Data\Blocks\<id>\Input\...`, `\Data\Blocks\<id>\Ports\<port>`. `fw com-tree` lists the
children of any node, with values and units at the leaves; widen with `--depth`. In Aspen, the
Variable Explorer shows the same tree: find where it is in the user's version with
`fw help-search "Variable Explorer"`. Notes from the help:

- Node names containing `/` are written in single quotes inside a path.
- Non-scalar variables (profiles, compositions, coefficients) take one to three identifiers: one
  more level each in the tree (for example `...\MOLEFLOW\MIXED\WATER`).
- Prop-set results appear under `\Data\Streams\<id>\Stream Results\Table\...` only when the
  prop-set is in Setup > Report Options.
- Some results are not in the tree at all (convergence monitor, column analysis, batch blocks, time
  profiles: the help names them under "SharedData").

## Units and status

Values are read and written in the units the node shows (its unit set); `com-get` and `com-tree`
print them, and the log records the unit of every change. Never assume a unit: read it.

After a run the commands read `\Data\Results Summary\Run-Status\Output\`:

| Flag | Covers | Value |
|---|---|---|
| `CVSTAT` | convergence | 0 no error, 1 error, 2 warning; missing = feature not used |
| `RSTAT` | Calculator and Transfer blocks | as above |
| `SENSSTAT` | sensitivity | as above |
| `PROPSTAT`, `PPSTAT`, `PCESSTAT` | property analysis, physical properties, property estimation | as above |
| `CSSTAT` | case study | as above |

A clean flag set does not replace reading the run: still read the `.cpm`/`.rep` digests and
check the balances (`fw check`).

## Limitations

- Local only: the client and Aspen Plus run on the same PC (client-server set-ups are no longer
  supported). Every session needs a free licence.
- A report can be exported only from results of the current session: the commands run first.
- `.inp` files cannot be imported into an open case by automation either; Routes A and B in
  input-language.md stay the way to bring text into a model.
- The commands were written from the V15 help and tested against a fake server. Some members are
  confirmed only on a PC with Aspen Plus (the live tests in the repository's docs/live-tests.md):
  the version property, `UnitString`, `Engine.IsRunning` (without it the run is synchronous and
  the timeout is not enforced), the `HAP_ENTERABLE` attribute, and whether a port connects with
  `Add` on the port or on its `Elements`. `fw com-check --start` reports the first ones and the
  type-library constants the commands use.

## Before writing new automation code

Read the topics in the user's help (`fw help-search "Happ"`, then `fw help-read "<title>"`):
"Initialization Methods to be Used with CreateObject()", "Run2 Interface", "Checking the Status
of Runs from Automation", "Exporting Files from an Automation Client", "Members of Class HappLS",
"Members of Class IHAPEngine", "Suppressing Dialog Boxes", "Limitations of Data Access Via Happ
Automation", "Dot Notation for Navigating the Tree", the "Node Attributes" and "Physical
Quantities and Units of Measure" topics, "Referencing Non-Scalar Variables in the Automation
Interface", "Adding and Deleting Blocks", "Adding and Deleting Streams", "Connecting and
Disconnecting Streams", "Example of Creating a New Convergence Block via Automation".

The same server works from other clients: MATLAB uses `actxserver('Apwn.Document')`, VBA and
Excel `CreateObject("Apwn.Document")`. Keep the same rules: work on copies, quit in every case,
read units, check the status flags.
