# The example library: learning from models that already work

Aspen Plus installs a few hundred example models (carbon capture with amines, electrolytes,
hydrogen, fertilizers, solids, polymers, batch ...), most with a PDF guide. They answer "how did
AspenTech set this up?": property method and chemistry for a system, block choices, convergence,
calculators, specs. proc-sim-agent indexes them on the user's computer; nothing is copied out.

In the commands below, `fw` stands for `python scripts/fw.py`, run from the skill folder (see SKILL.md).

## Setup (once)

```text
fw setup --examples "<folder>"     # setup --auto finds ...\Aspen Plus V15.0\GUI\Examples
fw examples-index                  # under a minute for ~275 models; repeat if it says INCOMPLETE
fw docs-index                      # optional: makes the PDF guides searchable with docs-search
```
In the GUI the same folder opens with **File > Open > Open Local Example** (or **Resources >
Examples**). Any folder of `.bkp`/`.apwz` files can be added the same way: a team's model
library, old projects, or the *Electrolyte Inserts* and *Data Package* folders listed under
Aspen Plus Favorites (ready-made electrolyte chemistry for many systems).

When no example index exists yet: run `fw status`; try `fw setup --auto` (it registers the
installed examples folder if it finds one) or ask the user for the folder, then index it. Until
the index exists, do not name examples or describe their settings from memory: say you have not
read them, give the GUI route (**File > Open > Open Local Example**, then the topic folder, e.g.
*Carbon Capture*), and offer to index the folder.

## Finding a model

```text
fw examples-search "CO2 capture MEA"                      # words: process, chemicals, topic
fw examples-search --block RADFRAC --has electrolyte       # filters, combinable with words
fw examples-search "brine" --method ELECNRTL --component NA+
fw examples-search --has sensitivity --folder "Carbon Capture"
fw examples-list                                          # topic folders and what they use
```
Filters: `--block` (unit-operation keyword: RADFRAC, RSTOIC, HEATX, RPLUG ...), `--method`
(property method), `--component` (ID or databank name), `--has` (calculator, design-spec,
sensitivity, optimization, tear, convergence, hierarchy, electrolyte, chemistry, henry, solids,
reactions, fortran, user-fortran, excel, acm, properties-only, results, user-sequence),
`--folder`. Results show the release, property method, block counts, features and the guide.

## Reading one

```text
fw examples-show <id>                          # components, method, chemistry, blocks, files, guide
fw examples-show <id> --section "CHEMISTRY"    # raw input records of matching sections
fw examples-show <id> --section "BLOCK RADFRAC ABSORBER"
fw examples-show <id> --chemistry-inp          # its CHEMISTRY as input language (STOIC, K-STOIC, DISS, SALT)
fw docs-search "<words>"                # the PDF guide, once docs-indexed
fw docs-read "<guide>" --pages 1-4
fw bkp "<path of the .bkp>"                     # full structure (also works on the copy in the folder)
```
Section names are those of the input tree: `PROPERTIES MAIN`, `CHEMISTRY <id>`,
`BLOCK <MODEL> <id>`, `CALCULATOR <id>`, `DESIGN-SPEC <id>`, `REACTIONS <id>`, `CONVERGENCE ...`.
Records use named fields (`FEEDS FEED-SID=F FEED-STAGE=60`); input-language.md says how they map
to an input file.

## Using what you find

- Take settings, not models: the property method and its options, chemistry and its constants
  (`--chemistry-inp`, then map component IDs to the user's), Henry components, the block model and
  its key specifications, convergence choices, how a calculator is written.
- Say where it came from: "AspenTech example *ENRTL-RK_Rate_Based_MEA_Model* (V15, Carbon
  Capture/Amines ENRTL-RK) uses ...".
- Tell the user to open the example itself (File > Open > Open Local Example) when they want to
  see the forms; Aspen does not save into the Examples folder, so they save a copy elsewhere.
- Examples are licensed AspenTech content: quote short settings only; do not copy example files,
  guides or the index into anything that leaves the user's computer.
- An example's result is not validation of the user's model: their system, basis and data
  differ. Use the guide's validation section to see what AspenTech compared against.

## Hidden objects and other notes

- `Hidden objects` in examples-show: objects stored with Hide/Reveal (Object Manager). They are
  not part of the calculation; Reveal them in the GUI to look at them.
- Properties-only runs (data regression, property estimation, PROP runs) have no blocks; search
  them with `--has properties-only`.
- Models saved without results (`results` missing from the features) must be run before their
  stream tables can be read.
