# Contributing

Thank you for helping. Useful contributions, roughly in order of value:

1. **A message you solved**: add it to `skills/aspen-plus/references/messages.md`
   with Aspen's wording, the phase and severity, the usual cause and a fix that worked.
2. **A correction**: a click path that differs in your version, a rule that is wrong or incomplete.
3. **A parser fix**: a .his/.rep/.cpm/.bkp file the tools misread. Add a minimal synthetic
   excerpt (made-up names and values in the same layout) as a test fixture, never your own file.
4. **An evaluation case** in `evals/cases/<id>/` (`prompt.md`, `rubric.md`, optional `checks.json`
   and synthetic `fixtures/`) from a real question; see `evals/README.md`.
5. **A new product skill** (HYSYS, Aspen Adsorption, ...), following the `skills/aspen-plus` layout.

## Ground rules

- **No vendor content.** Never commit help topics, manuals, databank data, screenshots of
  licensed software or search indexes built from them. Short quotes of program messages are fine.
- **No private data.** Remove licence lines, user and computer names, paths, client and project
  names: run `python tools/scrub_aspen_files.py --check <files>` on anything you add.
- **Standard library only** in `scripts/` (Python 3.8+), so the tools run on any engineering
  laptop. PDF support may use `pypdf` or `pymupdf` when installed; the `com-*` commands import
  pywin32 only when they run.
- **Portable skill**: `SKILL.md` keeps to the Agent Skills keys, under 500 lines and about 5,000
  tokens, with no agent-specific variables or tool names; commands must work in PowerShell and Git
  Bash (`tests/test_portability.py` checks this). Put detail in `references/`.
- Write for engineers: short sentences, exact names, units on every number.

## Development

```text
python -m pip install pytest pypdf
python -m pytest -q
claude plugin validate --strict .
python tools/scrub_aspen_files.py --check examples evals/cases
python evals/run.py --agent claude --cases <id>
```

To try a change without reinstalling: `py -3 tools\install_skill.py --project "<test folder>"
--project-kind claude` and open an agent there, or `claude --plugin-dir .` in Claude Code.

## Pull requests

- One topic per pull request, with a line in `CHANGELOG.md`.
- Bump the version when behaviour changes: `plugin.json`, the marketplace entry, SKILL.md
  `metadata.version`, `fwlib.__version__`, `CITATION.cff` and `.zenodo.json` (`tests/test_repo.py`
  checks that they agree).
- CI must pass (tests on Windows and Linux, manifest validation, privacy check).

By contributing you agree that your contribution is licensed under the MIT License.
