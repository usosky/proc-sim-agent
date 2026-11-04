# proc-sim-agent

[![validate](https://github.com/usosky/proc-sim-agent/actions/workflows/validate.yml/badge.svg)](https://github.com/usosky/proc-sim-agent/actions/workflows/validate.yml)
[![Licence: MIT](https://img.shields.io/badge/licence-MIT-blue)](LICENSE)

<p>
  <img src="assets/auspire-logo.png" alt="AuSpire" height="44">
  &nbsp;&nbsp;&nbsp;
  <img src="assets/eu-cofunded.png" alt="Co-funded by the European Union" height="44">
</p>

**Claude Code plugins for chemical process simulation.** The first plugin, `aspen-plus`, makes
Claude work like a senior process engineer next to you: it builds models with you stage by stage
(and can write them as Aspen Plus input files you open directly), shows how AspenTech's own
example models set up a similar process, gives exact click paths checked against *your* installed
Aspen Plus help, and checks every result with numbers. It reads your run files (.his, .rep, .cpm,
.bkp) to troubleshoot runs, review models and compare versions, and it searches your own library
of papers and notes.

proc-sim-agent ships no AspenTech content. On first use it indexes the help that came with your Aspen
Plus installation, on your computer; your models, results and library never leave it.

## What it does

| You ask | proc-sim-agent does |
|---|---|
| "How do I set a calculator to run before a block?" | searches your local help, reads the relevant topics, answers with numbered steps, click paths and why |
| "My run fails with *SPEC ... CONVERGENCE BLOCK $OLVER02 WILL BE DELETED*" | explains the root cause and the fix (a curated table of real Aspen messages and their fixes) |
| "Look at my model folder" | lists versions, run status, missing exports, leftover engine files and sync-conflict copies; flags a `.his`, `.rep` or `.bkp` that comes from an older run than the files next to it (from the run stamps inside the files, not file times) |
| "Here is run v0.04: did it pass?" | checks that `.bkp`, `.his` and `.rep` come from the same run, then compares the results with your expected values and tolerances: *Item / Expected / Model / Verdict* (`check --expect`) |
| "What changed between 4.1 and 4.2?" | diffs the input language of two runs (line by line, or by paragraph with `inp-diff`) and compares key results |
| "Check my calculator code" | extracts the inline Fortran and lints it (column 72, tabs, undefined names, assigned imports, unused imports) |
| "Compare the reboiler duty with Table S15 of the paper" | reads the report, converts units, builds the comparison table |
| "What does my library say about formic acid / NRTL binaries?" | full-text search of your PDFs and notes, with document and page |
| "Let's build a model of this process from scratch" | plans the build in stages with pass criteria, keeps a BUILD.md log, checks each run (balances, KPIs) before the next step |
| "Write it as an input file" | writes the model as an `.inp`, checks it (`inp-check`), you open it with File > Open and run |
| "Run this case for five feed temperatures" | on Windows with pywin32, runs copies of the model through Aspen's automation interface: one run per point, a CSV with the status of each; reads values with units, adds blocks and streams; your file is never changed |
| "How does AspenTech model MEA capture?" | searches the example library on your computer by process, block, property method, component; shows the chemistry and block setup |
| "Here is my stream table - what is the recovery?" | mass, element and charge balances, apparent vs true basis, and your KPIs computed from the pasted table or the .rep |

## Install (Claude Code)

```text
/plugin marketplace add usosky/proc-sim-agent
/plugin install aspen-plus@proc-sim-agent
```

Requirements: Claude Code, Python 3.8 or newer (`python` or `py -3` on Windows), Aspen Plus
V12-V15 installed (for its help files). Optional: `pip install pypdf` to index PDFs.

## First run

Ask Claude *"Set up proc-sim-agent for my Aspen Plus help"*, or run the commands yourself
(`fw.py` lives in `skills/aspen-plus/scripts/`):

```bash
python fw.py setup --auto        # finds C:\ProgramData\AspenTech\Aspen Plus V15.0\HtmlHelp (or similar)
python fw.py help-index          # repeat until it prints "complete" (each run ~100 s, resumable)
python fw.py setup --library "D:\Papers\Process"   # optional: your PDFs and notes
python fw.py docs-index          # repeat until "complete"
python fw.py setup --sims "D:\Simulations"         # optional: your model folders
python fw.py setup --examples "C:\Program Files\AspenTech\Aspen Plus V15.0\GUI\Examples"
python fw.py examples-index      # optional: the example library (under a minute)
python fw.py status
```

Indexes are stored in `%USERPROFILE%\.proc-sim-agent` (set `PROC_SIM_AGENT_HOME` to move them).
Details: [docs/install.md](docs/install.md).

## Try it on a published model

[`examples/joule-formic-acid`](examples/joule-formic-acid) holds the Aspen Plus model of the
CO2-hydrogenated formic acid process published in *Joule* 8, 693-713 (2024), with its history,
report and Control Panel files, and a script that reproduces the paper's SI energy table from the
report (8 of 9 items within 0.6 %; the one difference is explained).

## How it works

```text
your Aspen help (MadCap WebHelp) --index--> SQLite FTS5 --+
Aspen example models (.bkp/.apwz) --index--> SQLite FTS5 --+
your PDFs / notes ------------------index--> SQLite FTS5 --+--> fw.py --> Claude + references/*.md
your .his .rep .cpm .bkp -----------parsers----------------+          |
                                                                      +--> .inp files you open in Aspen
```

- `skills/aspen-plus/SKILL.md`: when and how Claude uses the tool, the answer style, privacy rules.
- `skills/aspen-plus/references/`: curated knowledge (messages and fixes, calculator and Fortran
  rules, workflows, build mode, input language, example library, GUI paths, file types, help map).
- `skills/aspen-plus/templates/`: a BUILD.md plan template and starting input files.
- `skills/aspen-plus/scripts/fw.py`: standard-library Python, no network access.

## Commands

Run `python skills/aspen-plus/scripts/fw.py <command> -h` for the options of each.

| Command | Purpose |
|---|---|
| `setup`, `status` | register help, library and simulation folders; show index state |
| `help-index`, `help-search`, `help-read`, `help-toc` | build and query the local help index |
| `docs-index`, `docs-search`, `docs-read`, `docs-list` | your PDFs and notes |
| `sim-scan` | model folders: versions, run status, files from an older run, missing exports |
| `his`, `his-diff` | run digest with message IDs, convergence, block results, Fortran lint; input diff |
| `inp-diff` | which input paragraphs (blocks, streams, calculators) were added, removed or changed |
| `rep`, `cpm`, `bkp` | report, Control Panel and backup readers |
| `examples-index`, `examples-search`, `examples-show`, `examples-list` | the Aspen Plus example library (or any folder of models) |
| `inp-check`, `inp-find`, `comp-find`, `his --inp` | write and check input files: lint, syntax from your own runs, databank aliases from the examples, a run's input as .inp |
| `check` | mass, element and charge balances, apparent/true basis, KPI expressions from a .rep or a pasted stream table; `--expect` gives the run-review table |
| `com-check`, `com-get`, `com-tree`, `com-run`, `com-sweep`, `com-edit` | Aspen Plus automation (COM) on copies: check the set-up, read values and the data tree, run, sweep, edit the flowsheet |

## Privacy

- Nothing is uploaded by the tools; indexes stay in your user folder.
- The run-file digests leave out the licence holder, Windows user and computer names and run
  folders; `.def` and `.scr` files are never read. Paths of your own files are shown, so Claude can
  open them.
- `tools/scrub_aspen_files.py` makes shareable copies of model files (see [NOTICE.md](NOTICE.md)).

## Roadmap

Driving Aspen Plus directly (automation from Python or MATLAB: set inputs, run, read results),
Aspen HYSYS and Aspen Adsorption plugins (the indexer already reads their help), more curated
messages, evaluation cases from real support questions. Contributions welcome:
[CONTRIBUTING.md](CONTRIBUTING.md).

## Cite

See [CITATION.cff](CITATION.cff). Archived on Zenodo (DOI added at the first release).

## Author

**Denis Usosky** ([ORCID 0000-0002-6245-5110](https://orcid.org/0000-0002-6245-5110)). Developed within
the AuSpire project (Marie Sklodowska-Curie Actions, Grant Agreement No 101177949).

## License

Code and documentation: MIT, see [LICENSE](LICENSE). Model and run files in
[`examples/joule-formic-acid`](examples/joule-formic-acid): CC BY 4.0, cite the paper
([LICENSE.md](examples/joule-formic-acid/LICENSE.md)). Logos in `assets/` are not covered by these
licences. Aspen Plus, Aspen HYSYS and Aspen Adsorption are trademarks of
Aspen Technology, Inc.; this project is not affiliated with or endorsed by AspenTech
([NOTICE.md](NOTICE.md)).

## Acknowledgment

Co-funded by the European Union under the Marie Sklodowska-Curie Grant Agreement No 101177949
(AuSpire). Views and opinions expressed are however
those of the author(s) only and do not necessarily reflect those of the European Union or the
Research Executive Agency. Neither the European Union nor the granting authority can be held
responsible for them.
