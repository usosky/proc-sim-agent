# aspen-plus (proc-sim-agent)

Aspen Plus assistant for Claude Code. Claude works like a senior process engineer: it builds
models with you stage by stage (and can write them as input files you open in Aspen), shows how
AspenTech's example models set up similar processes, gives numbered steps with click paths
checked against your installed Aspen Plus help, and checks results with numbers. It reads your
.his, .rep, .cpm and .bkp files to troubleshoot runs, review models, lint calculator Fortran and
compare versions, and it searches your own library of papers and notes. Everything stays on your
computer.

## Install

```text
/plugin marketplace add usosky/proc-sim-agent
/plugin install aspen-plus@proc-sim-agent
```

Then ask: *"Set up proc-sim-agent for my Aspen Plus help."* Claude runs `fw.py setup --auto` (finds
`C:\ProgramData\AspenTech\Aspen Plus V15.0\HtmlHelp` or similar) and builds the index
(`fw.py help-index`, a few resumable runs of about 100 s each).

## Contents

```text
skills/aspen-plus/
  SKILL.md                 when and how Claude uses the tools; answer style; privacy
  references/              build-mode.md, input-language.md, examples.md, messages.md,
                           calculators.md, workflows.md, gui-navigation.md, file-types.md,
                           answer-style.md, help-map.md
  templates/               BUILD.md plan template; starting .inp files (flash, column,
                           electrolyte absorber)
  scripts/fw.py            command line (standard-library Python 3.8+)
  scripts/fwlib/           help index (MadCap WebHelp + SQLite FTS5), example-model and library
                           indexes, .his/.rep/.cpm/.bkp parsers, input-file checker, stream
                           checks, simulation-folder scan
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
| `examples-index`, `examples-search`, `examples-show`, `examples-list` | the Aspen Plus example library (or any folder of models) |
| `inp-check`, `inp-find`, `comp-find`, `his --inp` | write and check input files: lint, syntax from your own runs, databank aliases from the examples, a run's input as .inp |
| `check` | mass, element and charge balances, apparent/true basis, KPI expressions from a .rep or a pasted stream table |

Works with Aspen Plus V12-V15 help (MadCap WebHelp). See the repository README for details,
privacy notes and the worked example.
