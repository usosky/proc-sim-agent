# proc-sim-agent

Agent Skills for process simulation software. This plugin holds one skill, `aspen-plus`: an
assistant for chemical engineers who work in Aspen Plus. It is an independent open-source project
and is not affiliated with, sponsored or endorsed by Aspen Technology, Inc.

## What the skill does

- Builds a model with you stage by stage, with expected values before every run.
- Writes the model as an Aspen Plus input file that you open in Aspen Plus.
- Reads the files your runs produce (history, report, Control Panel messages, backup) to find the
  cause of an error, review a model and compare versions.
- Checks mass, element and charge balances and your KPIs against the values you expect.
- Answers how-to questions from the Aspen Plus help and example library installed on your own
  computer, and from your own papers and notes.
- On Windows, runs, sweeps and edits copies of a model through Aspen Plus automation.

## What you need

| Need | For |
|---|---|
| Python 3.8 or newer | everything (standard library only) |
| Aspen Plus V12 to V15 installed on the computer | the help and example search |
| Windows, `pywin32` and an Aspen Plus licence | automation only |
| `pypdf` (optional) | indexing your PDFs |
| `gfortran` (optional) | compiling calculator code as a check |

No AspenTech content is included. On first use the skill indexes the help and the example models
that came with your own Aspen Plus installation, on your computer.

## What it runs, reads, writes and sends

- **Runs** the Python scripts in this plugin's skill folder, on your computer, when the agent
  calls them. The scripts start another program only in these cases: `gfortran`, to compile a
  calculator file you asked to check; `pdftotext`, to read a PDF when no Python PDF library is
  installed; the Windows `tasklist` command, to see whether an Aspen Plus process that the script
  started has exited (it ends none); and Aspen Plus itself, through its automation interface, when
  you ask to start it as a check, read values from a model, or run, sweep or edit a copy. The
  skill names `python -m pip install pypdf` and `python -m pip install pywin32` for the optional
  packages; pip downloads them from PyPI only when you or the agent run that command.
- **Reads** the folders you register or name: the Aspen Plus help and example folders, your
  library of documents and your model folders. `setup --auto` looks for the help and the examples
  under `C:\ProgramData\AspenTech`, `C:\Program Files\AspenTech` and
  `C:\Program Files (x86)\AspenTech`. For automation it also reads the Windows registry to find the
  Aspen Plus automation server. It does not read Aspen's `.def` and `.scr` files.
- **Writes** its search indexes and one configuration file to the folder `.proc-sim-agent` in your
  user folder (the environment variable `PROC_SIM_AGENT_HOME` moves it), and the files you ask for
  (input files, stream tables as CSV, the results of automated runs) where you name them. When you
  build a model with it, the agent writes a build guide and a `STATUS.md` in your model folder
  after you agree. Automation works on copies in a new folder and never changes your model file.
  The scripts delete only what they created: their temporary folders, an index you ask them to
  rebuild, and the files of an automation command that failed.
- **Sends** nothing. The scripts use no network and collect no usage data. The agent you use sends
  what it reads to its model provider under your account's terms, so keep confidential files out
  of the conversation when that matters.

## Install from GitHub (Claude Code)

```text
/plugin install proc-sim-agent --marketplace usosky/proc-sim-agent
```

GitHub Copilot, Codex and Gemini CLI use the skill folder directly; the installation guide in the
repository shows how.

## More

The documentation, the tests and the change log are in the repository:
https://github.com/usosky/proc-sim-agent

## Licence, trade marks, funding

MIT licence (see the LICENSE file). Aspen Plus is a trade mark of Aspen Technology, Inc.; the name
is used only to say which software the skill works with.

Developed by Denis Usosky within the AuSpire project. Co-funded by the European Union under the
Marie Sklodowska-Curie Grant Agreement No 101177949 (AuSpire). Views and opinions expressed are
however those of the author(s) only and do not necessarily reflect those of the European Union or
the Research Executive Agency. Neither the European Union nor the granting authority can be held
responsible for them.
