# Changelog

All notable changes are listed here. Versions follow [Semantic Versioning](https://semver.org);
bump `version` in `plugins/<plugin>/.claude-plugin/plugin.json` (the only place it is set) with
every release, or installed copies will not update.

## [Unreleased]

### Tests
- Shared helpers: number formatting, ANSI/UTF-8 files with CRLF line ends, safe names,
  sizes, natural sort, and the config file (defaults, atomic save, damaged file).
- Search without SQLite FTS5 for the help and library indexes, query terms, and help topic
  lookups by path, F1 id, topic id and part of the title.
- PDFs in the library: metadata title, search by page, page ranges, encrypted files.

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
