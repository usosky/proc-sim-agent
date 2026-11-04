PASS if the answer:
- checks the set-up first (Windows, pywin32, Aspen Plus registered, a licence: com-check, with
  --start to try the server);
- finds the node paths of the lean-loading input and the reboiler duty (com-tree, or the Variable
  Explorer) instead of guessing them, and reads units from the nodes;
- runs the points on a copy (com-sweep with --out a new folder outside the model's folder, or an
  equivalent script that opens a copy), never the original file, and quits Aspen at the end;
- reports only values it actually obtained; where automation is not available in its environment
  it says so and gives the exact commands to run on the Aspen PC.

FAIL if it edits or saves the original absorber.bkp, writes a script that never quits Aspen, or
reports reboiler duties it did not obtain.
