# Installing and setting up proc-sim-agent

## 1. Requirements

- Claude Code (desktop, IDE extension or terminal).
- Python 3.8 or newer on the same computer. On Windows, install from python.org and tick
  "Add python.exe to PATH", or use the `py` launcher (`py -3`). Check: `python --version`.
- Aspen Plus V12, V12.1, V14 or V15 installed, so its help files are on disk.
- Optional: `pip install pypdf` (or `pymupdf`) to index PDF files.

## 2. Install the plugin

In Claude Code:

```text
/plugin marketplace add usosky/proc-sim-agent
/plugin install aspen-plus@proc-sim-agent
```

Restart Claude Code if the skill does not appear (`/plugin` lists installed plugins).
Updates: `/plugin marketplace update proc-sim-agent`, then `/plugin` shows the new version.
The repository was first published as `usosky/modelaide`; GitHub redirects the old address, but if
you added it under that name, remove it (`/plugin marketplace remove proc-sim-agent`) and add
`usosky/proc-sim-agent` again.

## 3. Register and index the help

Ask Claude *"Set up proc-sim-agent for my Aspen Plus help"*, or run from the plugin's
`skills/aspen-plus/scripts` folder:

```bash
python fw.py setup --auto
python fw.py help-index      # repeat until it prints "complete"
```

`--auto` looks in `C:\ProgramData\AspenTech\*\HtmlHelp`, `C:\ProgramData\AspenTech\*\*\HtmlHelp`,
`C:\Program Files\AspenTech\*\HtmlHelp` and `C:\Program Files (x86)\AspenTech\*\HtmlHelp`.
If your help is elsewhere (or you copied it), point to the folder that contains `apwn.mcwebhelp`:

```bash
python fw.py setup --help-root "C:\ProgramData\AspenTech\Aspen Plus V15.0\HtmlHelp"
```

Each `help-index` run works for about 100 seconds and saves its progress (exit code 3 = not
finished yet). The full V15 help (about 10,500 topics) took about 4-5 minutes in total in
testing; a network or cloud-synced folder is slower. `python fw.py status` shows progress. You can search while
indexing; results then say the index is incomplete.

The same commands work for Aspen HYSYS and Aspen Adsorption help folders (`HYSYS.mcwebhelp`,
`adsorption.mcwebhelp`); use `--product aspen-hysys` with `help-index`/`help-search`. The
curated references are written for Aspen Plus.

## 4. Optional: your library and your models

```bash
python fw.py setup --library "D:\Papers\Process simulation"
python fw.py docs-index      # repeat until "complete"
python fw.py setup --sims "D:\Simulations"
python fw.py sim-scan
```

Suggested model layout: one folder per model, one subfolder per version, with the `.bkp` and the
`.his`, `.rep` (File > Export > Report) and `.cpm` (File > Export > Run Messages) of the last run,
plus a short `notes.md` saying what changed. When you build a model with Claude, a `BUILD.md` in
the model folder keeps the plan, checkpoints and baseline.

## 5. Optional: the example library

Aspen Plus installs a few hundred example models (`File > Open > Open Local Example`). Indexing
them lets Claude find how AspenTech modelled a similar process (property method, chemistry,
blocks, convergence):

```bash
python fw.py setup --examples "C:\Program Files\AspenTech\Aspen Plus V15.0\GUI\Examples"
python fw.py examples-index
python fw.py docs-index      # optional: also indexes the examples' PDF guides
```

`setup --auto` registers the newest installed examples folder by itself. The index stays on
your computer like the help index.

## 6. Where data is stored

`%USERPROFILE%\.proc-sim-agent\` (Windows) or `~/.proc-sim-agent/`: `config.json` and the SQLite indexes.
Set the environment variable `PROC_SIM_AGENT_HOME` to use another folder. Delete the folder to start
over. The indexes contain text from your licensed help and documents: do not share them.

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found | use `py -3`, or reinstall Python with "Add to PATH" |
| "No MadCap help found" | point `--help-root` at the folder with `apwn.mcwebhelp` |
| "SQLite FTS5: NO" in `status` | update Python (FTS5 ships with python.org builds); searches still work, slower |
| PDFs show "no-text" | scanned PDFs have no text layer; run OCR first |
| Index seems stale after an Aspen update | `python fw.py help-index --rebuild` |
