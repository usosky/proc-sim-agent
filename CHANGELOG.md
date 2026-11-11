# Changelog

All notable changes are listed here. Versions follow [Semantic Versioning](https://semver.org).
The version lives in the two manifests in `plugins/proc-sim-agent/` (`.claude-plugin/plugin.json`
and `plugin.json`), SKILL.md `metadata.version`, `fwlib.__version__`, `CITATION.cff` and
`.zenodo.json`; set the same version in all of them with every release
(`tests/test_directory_preflight.py` checks that they agree), or installed copies will not update.
The marketplace entry in `.claude-plugin/marketplace.json` carries none.

## [0.3.1] - 2026-11-11

Ready to publish; the skill's behaviour is unchanged.

### Migration
- The Claude Code plugin is now called `proc-sim-agent`; it was `aspen-plus`. Plugin users run
  `/plugin marketplace update proc-sim-agent`, then `/plugin uninstall aspen-plus@proc-sim-agent`
  and `/plugin install proc-sim-agent@proc-sim-agent`. The skill is still called `aspen-plus`.
- A copied skill is updated with `py -3 tools\install_skill.py --target claude --force`.
- The skill moved to `plugins/proc-sim-agent/skills/aspen-plus/` and the Agent Plugins manifest to
  `plugins/proc-sim-agent/plugin.json`.

### Removed
- `examples/joule-formic-acid/` with its model, run files and check script, and the ten tests that
  read them. The repository holds no model files: the reference models are AspenTech's examples on
  the user's own installation, found with `examples-index`.

### Packaging
- `plugins/proc-sim-agent/` is the plugin folder: what Claude Code installs and what Anthropic's
  plugin directory scans. It holds `.claude-plugin/plugin.json` (new), the Agent Plugins
  `plugin.json`, a README that says what the scripts run, read, write and send, a copy of the
  LICENSE, and the skill.
- `.claude-plugin/marketplace.json`: one entry `proc-sim-agent` with source
  `./plugins/proc-sim-agent`, without `strict`, `skills` or `version`; `renames` moves an install of
  the old name `aspen-plus`.
- `tools/install_skill.py` copies from the new path; its duplicate warning finds the plugin under
  both names.
- `.zenodo.json` and `CITATION.cff`: new title, description and keywords; `url` in `CITATION.cff`;
  the reference to the removed example's paper is gone.

### Docs
- README: a status paragraph, "Try it on an AspenTech example" in place of the published model,
  the external programs the scripts can start, the new paths and plugin commands.
- `docs/publishing.md` rewritten as the checklist for GitHub, Zenodo and Anthropic's plugin
  directory (the GitLab section is unchanged). `docs/install.md`, `docs/agents.md`,
  `docs/live-tests.md`, `CONTRIBUTING.md` and `NOTICE.md`: paths, the plugin name, the migration.

### Tests
- A synthetic case (`tests/samples.py`, `tests/test_solvrec_case.py`) in place of the Joule files:
  the coverage of every reader module is at or above its value with the Joule tests.
- `tests/test_examples_local.py`: up to 40 `.bkp` of AspenTech's official examples, read in place
  where an examples folder exists; skipped elsewhere, so CI is not affected.
- `tests/test_directory_preflight.py`: the plugin directory's checks (P1-P16) as offline tests.

### CI
- The `-h` loops, the description-length step and `skills-ref` use the plugin folder's paths; the
  Agent Plugins schema check reads `plugins/proc-sim-agent/plugin.json`; Claude Code 2.1.322
  validates the marketplace and the plugin folder; the scrub step checks `evals/cases` only.

## [0.3.0] - 2026-11-04

One portable Agent Skill for Claude Code and GitHub Copilot on Windows, with automation.

### Migration
- **Layout:** the skill moved from `plugins/aspen-plus/skills/aspen-plus/` to `skills/aspen-plus/`,
  the evals to `evals/`. Claude Code plugin users: run `/plugin marketplace update proc-sim-agent`,
  then reinstall `aspen-plus@proc-sim-agent` (uninstall and install again if `/plugin` still shows
  0.2.0). Users of a copied skill: `py -3 tools\install_skill.py --target claude --force`.
- **Templates:** `templates/BUILD.md` is replaced by `build-guide.md`, `status.md`, `data-card.md`,
  `expected.csv` and `fortran-calculator.txt`. Existing BUILD.md files in model folders keep
  working; new builds use the build guide and STATUS.md.
- **JSON output:** `sim-scan --json` has `warnings` per folder and `freshness` per model, notes
  name the case once, and file entries no longer carry `mtime`. `his --json`: `error_summary` is
  that of the last run (it can be null when only an earlier run had one) and the output has
  `freshness`.
- Folder arguments (`his <folder>`, `rep <folder>`, ...) pick the file with the newest run stamp
  inside, no longer the newest file time.

### Agent Skill
- `SKILL.md` in the Agent Skills format: only `name`, `description` (780 characters, automation
  triggers added), `license`, `compatibility` and `metadata`; no agent-specific variables, tool
  names or shell syntax; paths relative to the skill folder; commands for PowerShell and Git Bash.
- `plugin.json` (Agent Plugins) at the root; the Claude Code marketplace entry points at the same
  `skills/` tree. One version, 0.3.0, in every manifest.
- `tools/install_skill.py`: copies the skill for Claude Code (`--target claude`), Copilot CLI
  (`--target copilot`), the `.agents` folder, or a project (`--project`); `--dry-run`, `--force`,
  `--uninstall`; warns about duplicate copies; never touches the data folder.
- Privacy text: the scripts upload nothing; the agent sends what it reads to its model provider
  under the user's account terms; nothing from the user's models, results or notes is committed or
  published.

### Run files
- Freshness from the run stamps inside the files (`.his`, `.bkp`, `.sum`, `.rep`, `.cpm`), never
  file times: `sim-scan` lists files from an older run at the top; `his`, `rep`, `cpm`, `bkp` and
  `check` print a `WARNING:` line first (or one line saying the stamps agree). A `.bkp` saved
  without results after the run gets a note.
- A `.his` with several runs: digests describe the last run and say how many the file holds.
- `check --expect <csv|json>`: the run-review table `| Item | Expected | Model | Verdict |` from
  metric expressions, `temp()`, `pres()`, `vfrac()`, `block(B, RESULT)` and `balance(MASS)`.
- `inp-diff`: paragraph-level differences between two inputs (`.inp` or `.his`).
- Windows: UTF-8 output on any console, long paths, files that Aspen Plus holds open (shared read,
  one retry, then a clear message), sync-conflict copies and engine working files never read as
  the model.

### Automation (new)
- `com-check [--start]`, `com-get`, `com-tree`, `com-run`, `com-sweep`, `com-edit`: Aspen Plus
  automation through pywin32, always on copies; frozen gates refused; one server per command,
  always quit; timeouts; result and read-only nodes refused; a log per run
  (`automation-log.json`). `references/automation.md`.

### Build mode v2
- `references/build-mode.md` rewritten: frame the job, data card, what Aspen can represent,
  expected values from a check model before every run, versions and gates, per-step instructions,
  gate acceptance, the run review (file contract), STATUS.md, modelling rules.
- `fortran-check`: lint of a calculator kept as a `.txt` file and a gfortran compile when gfortran
  is installed.
- `messages.md`: run lessons from V15 build sessions; `calculators.md`: Fortran as a file, the
  I-N rule, apparent acids and bases to feeds in true-component runs.
- Editing models without automation: an "Editable?" column in `file-types.md` (the skill never
  hand-edits `.apw`, `.appdf`, `.apmbd` or `.bkp`) and two documented routes in
  `input-language.md` (an input file with graphics; a section saved as `.bkp` and imported).

### Evals and CI
- `evals/cases/<id>/` (12 cases, agent-neutral), `evals/triggers.json` (20 prompts),
  `evals/run.py --agent claude|copilot` with command templates in `evals/agents.toml`,
  `evals/MANUAL.md` for VS Code agent mode.
- CI on ubuntu and windows (Python 3.12, and 3.8 on ubuntu-22.04): every `fw` command's `-h` in
  bash and PowerShell, an install into a temporary Windows profile, skills-ref at a pinned commit,
  the plugin and marketplace manifests, the scrub check.
- Docs: `docs/install.md` (Windows), `docs/agents.md`, `docs/live-tests.md`.

### Tests
- 104 tests in 0.2.0, about 290 now: freshness, check --expect, inp-diff, fortran-check,
  automation against a fake Aspen Plus server, the installer, Windows hardening, portability,
  the evals runner. Shared helpers, search without SQLite FTS5 and PDFs (from the previous
  Unreleased section) are included.

## [0.2.0] - 2026-10-06

Build models, not only answer questions.

### aspen-plus plugin
- **Build mode** (`references/build-mode.md`): Claude plans a new model with the user in stages
  (properties, feeds, one unit at a time, recycles, specs, studies, baseline), each with pass
  criteria set before the run, checks every run with numbers, and keeps a `BUILD.md` plan and
  log in the model folder (template in `templates/`).
- **Input files** (`references/input-language.md`): Claude can write a model as an Aspen Plus
  input file (`.inp`) that the user opens with File > Open. New commands: `inp-check` (lints an
  .inp before it is opened: units, components, connectivity, feed and block specifications,
  reaction balances, chemistry use, true/apparent approach, design-spec and sensitivity
  statements, Fortran, databank release), `inp-find` (how a block or paragraph is written,
  taken from the user's own runs), `comp-find` (the databank alias of a component, as the example
  models use it), `his --inp` (the input of any run as an .inp). Three starting
  files in `templates/`: flash with calculator and sensitivity, column with specifications,
  electrolyte absorber.
- **Example library index** (`references/examples.md`): `examples-index`, `examples-search`
  (words plus filters on block type, property method, component, features, folder),
  `examples-show` (structure, raw input sections, chemistry translated to input language),
  `examples-list`. Reads `.bkp` and `.apwz` (the .bkp inside), hierarchy blocks, hidden objects,
  PDF guides; `setup --auto` finds the Aspen Plus examples folder. All 275 V15 examples index in
  under a minute.
- **Stream checks** (`check`): block mass and element balances, electroneutrality, apparent vs
  true basis, and KPI expressions (`--metric "capture=1-flow(GAS-OUT, CO2)/flow(GAS-IN, CO2)"`)
  from a `.rep` or a stream table copied from the results grid (also when its line breaks were
  lost in a chat box).
- `.bkp` reader: objects hidden with Hide/Reveal are cut out correctly (they were shifting the
  input tree in some files) and reported; hierarchy property methods; user sequences.
- New evaluation cases: build mode, electrolyte input file, example lookup.

## [0.1.0] - 2026-10-03

First public version.

### aspen-plus plugin
- Local help index: reads Aspen Plus MadCap WebHelp (V15: about 10,500 topics), resumable
  SQLite FTS5 index with ranked search, topic reader (Markdown, links, equations), table of
  contents, F1 ids. The help version is read from the help itself.
- Library index of PDFs, Word files and notes with page-level search and duplicate detection.
- Parsers: `.his` digest (input echo, messages with IDs, convergence history, block results,
  calculator Fortran with lint, iteration-0 detection, history diff), `.rep` (status, convergence,
  balances, block results, stream tables, CSV export), `.cpm` (progress, loops, messages, error
  summary), `.bkp` structure summary, and a simulation-folder scan.
- References: answer style, run messages and fixes, calculator/design-spec/Fortran rules,
  workflows, V12-V15 GUI paths, file types and privacy, help map.
- Example: Joule 2024 formic acid process model with a reproducible check against the paper's SI.
- Tools: `scrub_aspen_files.py` for sharing model files.
- Licences: code and documentation MIT; example model and run files CC BY 4.0.
