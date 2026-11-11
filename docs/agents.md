# Agents: where they find the skill, what differs, test status

The skill follows the Agent Skills format (agentskills.io): a folder `aspen-plus` with `SKILL.md`
(only the keys `name`, `description`, `license`, `compatibility`, `metadata`), `references/`,
`templates/` and `scripts/`. Nothing in it is specific to one agent: no agent variables or tool
names, paths relative to the skill folder, commands that run in PowerShell and Git Bash.

## Where agents look for skills

Checked in November 2026. Folders change between releases: check again after an upgrade.

| Agent | Project folder | User folder (Windows) | How it was checked |
|---|---|---|---|
| Claude Code (2.1.288; plugin route 2.1.322) | `.claude\skills` | `%USERPROFILE%\.claude\skills` | project folder: the eval runs load the skill from `<workspace>\.claude\skills`; user folder: Claude Code documentation; plugin route: `claude plugin validate --strict` of the marketplace and the plugin folder, and an install of `proc-sim-agent@proc-sim-agent` from a local clone and from the GitHub branch |
| GitHub Copilot CLI (1.0.105) | `.github\skills`, `.claude\skills`, `.agents\skills` | `%USERPROFILE%\.copilot\skills`, `%USERPROFILE%\.agents\skills` | `copilot skill list` with test skills in each folder |
| VS Code agent mode (Copilot) | `.github\skills`, `.claude\skills`, `.agents\skills` | not checked | documentation search; live test L0 |
| Codex | `.agents\skills` | `%USERPROFILE%\.agents\skills` | not tested |
| Gemini CLI | `.gemini\skills`, `.agents\skills` | `%USERPROFILE%\.gemini\skills`, `%USERPROFILE%\.agents\skills` | not tested |

As a plugin (`plugins/proc-sim-agent`), Claude Code installs only the plugin folder and lists the
skill as `proc-sim-agent:aspen-plus` (checked with 2.1.322). Use either the plugin or a copied
skill, not both.

Copilot CLI 1.0.105 does **not** read `%USERPROFILE%\.claude\skills`, so one user-level copy does not
serve both Claude Code and Copilot CLI: install with `--target claude` and `--target copilot`, or put
one copy in a project's `.claude\skills`, which both read (`install_skill.py --project <folder>
--project-kind claude`).

## What differs between agents

| | Claude Code | GitHub Copilot |
|---|---|---|
| Loads the skill | when the request matches the description; shows a Skill tool call | when the request matches the description |
| Runs `scripts\fw.py` | Bash tool (Git Bash on Windows) | terminal (PowerShell on Windows) |
| Plugin route | yes: `/plugin install proc-sim-agent --marketplace usosky/proc-sim-agent`; the skill is then listed as `proc-sim-agent:aspen-plus` | no (copy the skill) |
| Non-interactive runs for evals | `claude -p` (prompt on standard input, `--output-format stream-json`) | `copilot -p "<prompt>" -s --no-ask-user` |
| Description budget | the description is shown in full | descriptions of all skills share a budget: ours is at most 800 characters |

## Test status (v0.3.1)

| Check | Claude Code | GitHub Copilot |
|---|---|---|
| Skill format (portability test; skills-ref in CI) | passes | passes (same skill) |
| Install folders | documented route checked | CLI folders checked with `copilot skill list`; VS Code pending (L0) |
| Eval suite (`evals/run.py`) | run in November 2026 on Linux: all cases and triggers with 2.1.288; `run-review` and `stale-files` with 2.1.322 after the move to `plugins/proc-sim-agent` (2 of 2 pass); see `evals/results/` | for the owner: `python evals/run.py --agent copilot`, or evals/MANUAL.md in VS Code |
| On Windows with Aspen Plus | live tests L0-L6, T0-T5, E1 in docs/live-tests.md (owner) | the same |
| File readers in a Linux sandbox with the user's folders connected (Claude desktop app) | `status` and `bkp` ran on 10 Nov 2026 with Python 3.10 on an AspenTech example; automation is not available there (not Windows) | - |

Other Agent Skills hosts (Codex, Gemini CLI, Cursor) should work with `--target agents` or their
own folders, but are untested.
