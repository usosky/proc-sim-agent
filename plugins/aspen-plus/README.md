# aspen-plus (ModelAide)

Aspen Plus assistant for Claude Code. Claude answers like a senior process engineer: numbered
steps with click paths checked against your installed Aspen Plus help, the reason for each
choice, typical values, and the messages to expect. It reads your .his, .rep, .cpm and .bkp files
to troubleshoot runs, review models, lint calculator Fortran and compare versions, and it searches
your own library of papers and notes. Everything stays on your computer.

## Install

```text
/plugin marketplace add usosky/modelaide
/plugin install aspen-plus@modelaide
```

Then ask: *"Set up ModelAide for my Aspen Plus help."* Claude runs `fw.py setup --auto` (finds
`C:\ProgramData\AspenTech\Aspen Plus V15.0\HtmlHelp` or similar) and builds the index
(`fw.py help-index`, a few resumable runs of about 100 s each).

## Contents

```text
skills/aspen-plus/
  SKILL.md                 when and how Claude uses the tools; answer style; privacy
  references/              messages.md, calculators.md, workflows.md, gui-navigation.md,
                           file-types.md, answer-style.md, help-map.md
  scripts/fw.py            command line (standard-library Python 3.8+)
  scripts/fwlib/           help index (MadCap WebHelp + SQLite FTS5), library index,
                           .his/.rep/.cpm/.bkp parsers, simulation-folder scan
evals/                     evaluation cases for `claude plugin eval`
```

## Commands

| Command | Purpose |
|---|---|
| `setup`, `status` | register help, library and simulation folders; show index state |
| `help-index`, `help-search`, `help-read`, `help-toc` | build and query the local help index |
| `docs-index`, `docs-search`, `docs-read`, `docs-list` | your PDFs and notes |
| `sim-scan` | model folders: versions, run status, stale or missing exports |
| `his`, `his-diff` | run digest with message IDs, convergence, block results, Fortran lint; input diff |
| `rep`, `cpm`, `bkp` | report, Control Panel and backup readers |

Works with Aspen Plus V12-V15 help (MadCap WebHelp). See the repository README for details,
privacy notes and the worked example.
