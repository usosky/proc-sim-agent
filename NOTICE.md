# Notices

## Trademarks and affiliation

Aspen Plus, Aspen HYSYS, Aspen Adsorption, aspenONE and AspenTech are trademarks of Aspen
Technology, Inc. Claude and Claude Code are trademarks of Anthropic, PBC. GitHub Copilot and
Visual Studio Code are trademarks of GitHub, Inc. and Microsoft Corporation. proc-sim-agent is an
independent open-source project. It is not affiliated with, sponsored or endorsed by Aspen
Technology, Inc., Anthropic, PBC, GitHub, Inc. or Microsoft Corporation. Product names are used
only to say which software the tools work with.

## Third-party code

None is included. The automation module (`skills/aspen-plus/scripts/fwlib/com.py`) was written
for this project from the facts in the Aspen Plus help ("Using Aspen Plus Via Automation
(Happ)"); community automation projects were read for ideas only and no code was copied from
them. AspenTech's type library (`happ.tlb`) is not included: the constants the commands need are
read at run time from the Aspen Plus installed on the user's computer. The skill follows the
Agent Skills format (agentskills.io); CI checks it with `skills-ref` from
github.com/agentskills/agentskills, which is downloaded there and not redistributed.

## No vendor content

This repository contains no AspenTech help topics, manuals, databanks, example models,
executables or indexes of them. The tools build their search indexes on the user's computer, from
the help files and example models installed with the user's own licensed copy, and keep them
there. The input files in `skills/aspen-plus/templates/` were written for this
project (MIT); the equilibrium constants in the electrolyte template are the published values that
Aspen Plus also uses for these reactions. `references/help-map.md` lists only the names of
the help's books and their table-of-contents headings, to help users narrow a search.

Message texts quoted in `references/messages.md` are short excerpts of program output, used to
identify messages and explain them.

The eval fixtures in `evals/cases/*/fixtures/` and the test data in `tests/samples.py` are
synthetic: written for this project in the layout of Aspen Plus files, with invented values.

## Funding

proc-sim-agent is developed by Denis Usosky within the AuSpire project, co-funded by the European
Union under the Marie Sklodowska-Curie Grant Agreement No 101177949 (full acknowledgment in
README.md). The AuSpire logo and the EU emblem in `assets/` are not covered by the repository's
licences.

## Example files

`examples/joule-formic-acid/` contains an Aspen Plus model and run files from the authors of
Kim C. et al., Joule 8, 693-713 (2024), https://doi.org/10.1016/j.joule.2024.01.003, shared
for teaching and verification under CC BY 4.0 (see `examples/joule-formic-acid/LICENSE.md`).
Please cite the paper when you use them. They were cleaned with
`tools/scrub_aspen_files.py` (licence holder, local paths, user and computer names). Opening them
requires your own Aspen Plus licence (V12.1 or later).

## Your files

Run files contain information about your installation: the licence holder (.his, .rep), folder
paths (.his, .rep, .bkp), and the Windows user and computer name (.bkp run status, .def, .scr).
Run `python tools/scrub_aspen_files.py <files> --out <folder>` before sharing model files, then
open the copy in Aspen Plus once to confirm it still loads.
