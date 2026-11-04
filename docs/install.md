# Installing proc-sim-agent on Windows

The skill runs where Aspen Plus is installed: a Windows PC. The run-file readers also work on
Linux and macOS (for files copied there), but the help index, the example library and automation
need the Aspen Plus installation.

Commands below work in PowerShell and in Git Bash. `fw` stands for `py -3 scripts\fw.py`, run from
the installed skill folder (for example `%USERPROFILE%\.claude\skills\aspen-plus`).

## 1. Requirements

| Needed for | What |
|---|---|
| everything | Python 3.8 or newer: `py -3 --version` (python.org installer; the `py` launcher avoids the Microsoft Store alias) |
| help answers | Aspen Plus V12, V12.1, V14 or V15 installed (its help files are read on your PC) |
| an agent | Claude Code, or GitHub Copilot (CLI or VS Code agent mode) |
| PDF library (optional) | `py -3 -m pip install pypdf` |
| automation (optional) | `py -3 -m pip install pywin32` and a licensed Aspen Plus on the same PC |
| compiling calculator code (optional) | `gfortran` on PATH (MinGW-w64 or MSYS2) |

## 2. Get the repository

While the repository is private you need access to it and a signed-in Git:

```text
gh auth login
gh repo clone usosky/proc-sim-agent
cd proc-sim-agent
```

(or `git clone https://github.com/usosky/proc-sim-agent.git` with Git Credential Manager).

## 3. Install the skill

`tools\install_skill.py` copies `skills\aspen-plus` (no links) to where an agent looks for skills:

```text
py -3 tools\install_skill.py --target claude
py -3 tools\install_skill.py --target copilot
```

| Option | Installs to | Read by |
|---|---|---|
| `--target claude` | `%USERPROFILE%\.claude\skills\aspen-plus` | Claude Code |
| `--target copilot` | `%USERPROFILE%\.copilot\skills\aspen-plus` | GitHub Copilot CLI (checked with 1.0.105) |
| `--target agents` | `%USERPROFILE%\.agents\skills\aspen-plus` | Copilot CLI; Codex and Gemini CLI (untested) |
| `--project "<folder>"` | `<folder>\.github\skills\aspen-plus` | Copilot in that workspace, also VS Code agent mode |
| `--project "<folder>" --project-kind claude` | `<folder>\.claude\skills\aspen-plus` | Claude Code and Copilot in that workspace |

`--dry-run` shows what would happen; `--force` replaces an installed copy (use it to update);
`--uninstall` removes it. The installer warns when one agent would see two copies (Copilot reads
both `.copilot` and `.agents`): keep one. It never touches `%USERPROFILE%\.proc-sim-agent`, where
the indexes live. Start a new agent session after installing.

**VS Code agent mode:** project skills in `.github\skills` (and `.claude\skills`) are found per the
VS Code documentation; which personal folders it reads was not checked for this release. After
installing, look for `aspen-plus` in Copilot Chat's list of skills; docs/live-tests.md (L0)
records what VS Code does.

**Claude Code plugin (alternative):** the repository is also a Claude Code marketplace.

```text
/plugin marketplace add usosky/proc-sim-agent
/plugin install aspen-plus@proc-sim-agent
```

Use either the plugin or the `--target claude` copy, not both (Claude Code would see two skills).

## 4. First run: index the help

Ask the agent *"Set up proc-sim-agent for my Aspen Plus help"*, or run in the skill folder:

```text
py -3 scripts\fw.py setup --auto
py -3 scripts\fw.py help-index
py -3 scripts\fw.py status
```

`setup --auto` finds the help under `C:\ProgramData\AspenTech\...\HtmlHelp` (V15:
`C:\ProgramData\AspenTech\Aspen Plus V15.0\HtmlHelp`) and the newest example library. If your help
is elsewhere, point to the folder that holds `apwn.mcwebhelp`:

```text
py -3 scripts\fw.py setup --help-root "C:\ProgramData\AspenTech\Aspen Plus V15.0\HtmlHelp"
```

Repeat `help-index` until it prints `complete`: each run works for about 100 seconds and resumes
(exit code 3 means "not finished yet"). The full V15 help took about 4-5 minutes in total in
testing. Searches work on a partial index and say so.

Optional, in any order:

```text
py -3 scripts\fw.py examples-index
py -3 scripts\fw.py setup --library "D:\Papers\Process simulation"
py -3 scripts\fw.py docs-index
py -3 scripts\fw.py setup --sims "D:\Simulations"
py -3 scripts\fw.py sim-scan
```

## 5. Automation (optional)

```text
py -3 -m pip install pywin32
py -3 scripts\fw.py com-check --start
```

`com-check` says whether Windows, pywin32 and the Aspen Plus automation server are available;
`--start` starts Aspen Plus once (it takes a licence for a few seconds), prints its version and
quits. The `com-*` commands always work on copies (references/automation.md in the skill).

## 6. Your model folders

One folder per model, one subfolder per version, with the `.bkp` and the `.rep` (File > Export >
Report) of the last run, plus the `.cpm` (File > Export > Run Messages) when a run fails, and a
short `notes.md` saying what changed. The skill checks that `.bkp`, `.his` and `.rep` come from the
same run from the stamps inside the files (cloud sync clients rewrite file times). When you build
a model with the agent, a build guide and a `STATUS.md` in the model folder keep the plan, the check
values and the history.

## 7. Updating

```text
git pull
py -3 tools\install_skill.py --target claude --force
```

Plugin users: `/plugin marketplace update proc-sim-agent`, then reinstall `aspen-plus@proc-sim-agent`.

## 8. Where data is stored

`%USERPROFILE%\.proc-sim-agent\`: `config.json` and the SQLite indexes. Set `PROC_SIM_AGENT_HOME` to
use another folder; delete the folder to start over. The indexes contain text from your licensed
help and documents: do not share them.

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found, or the Microsoft Store opens | use `py -3` |
| garbled characters in the console | nothing to do: the tool writes UTF-8 itself; use Windows Terminal for the best display |
| "cannot read it now: ... Aspen Plus may hold it" | close the case in Aspen Plus (or wait for the run to end) and run the command again |
| very long folder paths | supported; if another tool fails on them, shorten the path |
| "No MadCap help found" | point `--help-root` at the folder with `apwn.mcwebhelp` |
| "SQLite FTS5: NO" in `status` | update Python (python.org builds include FTS5); searches still work, slower |
| PDFs show "no-text" | scanned PDFs have no text layer; run OCR first |
| index stale after an Aspen update | `py -3 scripts\fw.py help-index --rebuild` |
| `com-check`: pywin32 not installed | `py -3 -m pip install pywin32` |
| `com-check`: Apwn.Document not registered | repair the Aspen Plus installation |
