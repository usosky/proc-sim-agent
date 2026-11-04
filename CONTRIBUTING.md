# Contributing

Thank you for helping. Useful contributions, roughly in order of value:

1. **A message you solved**: add it to `skills/aspen-plus/references/messages.md`
   with Aspen's wording, the phase and severity, the usual cause and a fix that worked.
2. **A correction**: a click path that differs in your version, a rule that is wrong or incomplete.
3. **A parser fix**: a .his/.rep/.cpm/.bkp file the tools misread. Add a minimal, anonymised
   excerpt as a test fixture.
4. **An evaluation case** in `evals/` from a real question.
5. **A new product plugin** (HYSYS, Aspen Adsorption, ...), following the `aspen-plus` layout.

## Ground rules

- **No vendor content.** Never commit help topics, manuals, databank data, screenshots of
  licensed software or search indexes built from them. Short quotes of program messages are fine.
- **No private data.** Remove licence lines, user and computer names, paths, client and project
  names: run `python tools/scrub_aspen_files.py --check <files>` on anything you add.
- **Standard library only** in `scripts/` (Python 3.8+), so the tools run on any engineering
  laptop. PDF support may use `pypdf` or `pymupdf` when installed.
- Keep `SKILL.md` under 500 lines; put detail in `references/`.
- Write for engineers: short sentences, exact names, units on every number.

## Development

```bash
pip install pytest pypdf
python -m pytest -q
claude plugin validate --strict .
python tools/scrub_aspen_files.py --check examples
```

To try a change in Claude Code without reinstalling: `claude --plugin-dir .` (the repository root is the plugin).

## Pull requests

- One topic per pull request, with a line in `CHANGELOG.md`.
- Bump the plugin version (`plugin.json` only) when behaviour changes.
- CI must pass (tests on Windows and Linux, manifest validation, privacy check).

By contributing you agree that your contribution is licensed under the MIT License.
