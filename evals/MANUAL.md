# Running the cases by hand (VS Code agent mode)

VS Code's Copilot agent mode has no command-line interface, so these runs are by hand. Record the
results in `evals/results/<date>/vscode-copilot/summary.md` with the table below.

1. Make a workspace for the case and install the skill into it:

   ```text
   py -3 tools\install_skill.py --project "C:\Temp\psa-eval\<case>" --project-kind github
   ```

   Copy the case's `fixtures\` folder contents (if any) into the same workspace.
2. Open the workspace folder in VS Code, open Copilot Chat and choose **Agent** mode. Start a new
   chat for every case.
3. Paste the text of `cases\<case>\prompt.md` below its front matter. Let the agent run commands
   when it asks (they run `scripts\fw.py` inside the workspace).
4. When it has answered, record:
   - whether the skill was used (the chat lists the instructions or skills it read);
   - each check of `cases\<case>\checks.json` (does the answer match the pattern, was the file
     written);
   - PASS or FAIL against `cases\<case>\rubric.md`, with one sentence why.
5. Triggers: for each prompt in `triggers.json`, a new chat in a workspace with the skill
   installed; record whether the skill was used.

| Case | Skill used | Checks | Rubric | Note |
|---|---|---|---|---|
| run-review | yes | 3/3 | PASS | |

Note also which folders VS Code read the skill from (`.github\skills`, `.claude\skills`, or a
personal folder): this is open in docs/live-tests.md (L0).
