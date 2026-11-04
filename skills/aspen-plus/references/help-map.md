# Aspen Plus V15 help map

Where things live in the Aspen Plus help (MadCap WebHelp). Use the book name with
`fw.py help-search "..." --book <name>` or `fw.py help-toc --book <name>`. Built from the help's own
table-of-contents file; V12-V14 are organised the same way. Run `fw.py help-toc` on your install for the
exact list and topic counts.

| Table-of-contents position | Books (name: what is inside) |
|---|---|
| Getting Started with Aspen Plus | `userguide1`: getting started, file handling, GUI basics |
| Getting Started with Aspen Plus > Accessing Online Content | `Knowledge_Plus`: online content |
| Getting Started with Aspen Plus > Tutorials | `gettingstarted`: tutorials; `polyapps` |
| Using the Properties Environment | `apr-ug2`: Properties environment user guide |
| Using the Properties Environment > Aspen Properties Enterprise Database | `apedmanager`: Aspen Properties Enterprise Database |
| Using the Properties Environment > Properties Environment Forms > Setup | `apr-setup`: Properties setup forms |
| Using the Properties Environment > Properties Environment Forms | `cmpnts`: Components forms; `props`: Properties environment forms (methods, parameters, property sets) |
| Using the Simulation Environment | `userguide2`: simulation environment how-to (flowsheets, streams, blocks); `aduser` |
| Using the Simulation Environment > Polymer Reactions | `polyhelp`: polymer reactions |
| Using the Simulation Environment > Unit Operation Models Reference Manual | `apunitop`: Unit Operation Models Reference Manual (model theory, specs, EO usage) |
| Using the Simulation Environment > Simulation Environment Forms > Setup | `setup`: Setup forms (units, report options, simulation options) |
| Using the Simulation Environment > Simulation Environment Forms > Flowsheet | `flowsheet` |
| Using the Simulation Environment > Simulation Environment Forms > Streams | `streams`: Stream input forms |
| Using the Simulation Environment > Simulation Environment Forms > Blocks | `acmuser3`; `analyzer`: Analyzer; `batchsep`: BatchSep; `batchop`; `ccd`: CCD (countercurrent decanter); `ap-cffilter`; `cfuge`; `chargebal`; `ap-classifier`; `clchng`; `compr`: Compr; `streamana`; `crusher`; `crystallizer`: Crystallizer; `cyclone`: Cyclone; `decanter`: Decanter; `distl`: Distl shortcut; `dryer`: Dryer; `dstwu`: DSTWU shortcut; `dupl`; `electrolyzer`: Electrolyzer; `esp`; `extract`: Extract (liquid-liquid); `fabfl`; `filter`: Filter; `flash2`: Flash2; `flash3`; `ap-fluidized`; `fsplit`: FSplit; `ap-granulator`; `heater`: Heater; `heatx`: HeatX; `hier`: Hierarchy blocks; `hxflux`; `hybridequipment`; `hycyc`; `makeup`; `mcompr`: MCompr (multistage); `mheatx`: MHeatX; `mixer`: Mixer; `mult`; `multifrac`: MultiFrac; `petrofrc`: PetroFrac; `pipe`: Pipe; `pipeline`: Pipeline; `pump`: Pump; `qtvec`; `radfrac`: RadFrac rigorous column; `rbatch`: RBatch; `rcstr`: RCSTR; `requil`: REquil; `rgibbs`: RGibbs; `rplug`: RPlug; `rstoic`: RStoic; `ryield`: RYield; `scfrac`: SCFrac; `screen`; `selector`; `sep`: Sep; `sep2`: Sep2; `ssplit`; `swash`; `user`: User (Fortran) models; `user2`: User2 models; `user3`: User3 models; `valve`: Valve; `vscrub` |
| Using the Simulation Environment > Simulation Environment Forms > Blocks > Common Forms | `common`: forms common to blocks (Block Options, Stream Results...); `plotwiz`: plot wizard |
| Using the Simulation Environment > Simulation Environment Forms | `sensors`; `unitprocedures` |
| Using the Simulation Environment > Simulation Environment Forms > Utilities | `utility`: Utilities forms |
| Using the Simulation Environment > Simulation Environment Forms > Reactions | `reaction`: Reactions forms (POWERLAW, LHHW, EQUILIBRIUM, USER...); `polyfrms` |
| Using the Simulation Environment > Simulation Environment Forms > Convergence | `converge`: Convergence forms: tear, Wegstein/Secant/Broyden/Newton, sequencing |
| Using the Simulation Environment > Simulation Environment Forms > Flowsheeting Options | `hlpflwop`: Flowsheeting Options forms (Calculator, Design Spec, Transfer, Balance...); `measure`: Measurement blocks; `presrlf`: pressure relief |
| Using the Simulation Environment > Simulation Environment Forms > Model Analysis Tools | `mdanmstr`: Model Analysis Tools forms (Sensitivity, Optimization, Case Study...) |
| Using the Simulation Environment > Simulation Environment Forms > EO Configuration | `eoconf`: EO configuration forms |
| Using the Simulation Environment > Simulation Environment Forms > Results Summary | `results`: Results Summary forms (run status, streams, convergence) |
| Using the Simulation Environment > Simulation Environment Forms > Dynamics Forms | `adref`: dynamics forms |
| Using the Simulation Environment > Simulation Environment Forms > AI | `aitraining` |
| Simulation and Analysis Tools > Equation-Oriented Modeling | `apeoref`: Equation-Oriented modeling reference |
| Simulation and Analysis Tools | `userguide3`: analysis tools how-to (sensitivity, design specs, calculators, optimization, data fit); `cxs`; `PlantData`: plant data; `Safety_Datasheets`: safety datasheets |
| Simulation and Analysis Tools > Creating ACM Models in Aspen Plus | `acmme`; `acmgui`; `acmhowto`; `acmmodlng`; `acmphysprp` |
| Aspen Plus Reference > Physical Property Methods and Models | `ref2`: Physical Property Methods and Models (property methods, models, equations) |
| Aspen Plus Reference > Physical Property Data Reference Manual | `physprop`: Physical Property Data Reference Manual (databanks, parameters) |
| Aspen Plus Reference > Aspen Polymers Reference Manual | `polymanl`: Aspen Polymers reference |
| Aspen Plus Reference | `acmlibref`: ACM library reference |
| Troubleshooting | `acminput` |

## Tips

- Block forms (what each sheet/field means): the block's own book, e.g. `rstoic`, `radfrac`, `heatx`.
- Model theory and specification options: `apunitop`.
- Property methods and models (equations, parameters): `ref2`; databank parameters: `physprop`.
- Calculator, Design Spec, Transfer forms: `hlpflwop`; how-to for these tools: `userguide3`.
- Convergence methods and tear/sequence forms: `converge`.
- Context-sensitive help IDs (F1) are stored as aliases: `fw.py help-read <F1 id>` works, e.g. `rstoicsetupspecificationssheet`.
- Message IDs such as URE07.3 are not in the help text; search the message wording instead and check `messages.md`.
