# Changelog

All notable changes are listed here. Versions follow [Semantic Versioning](https://semver.org);
bump `version` in `plugins/<plugin>/.claude-plugin/plugin.json` (the only place it is set) with
every release, or installed copies will not update.

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
