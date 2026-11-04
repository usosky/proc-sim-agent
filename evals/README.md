# Evals

Agent-neutral test cases for the aspen-plus skill, and a runner for the agents' command-line
interfaces.

| Path | Holds |
|---|---|
| `cases/<id>/prompt.md` | the user's request (front matter: description, tags) |
| `cases/<id>/rubric.md` | PASS and FAIL criteria for an LLM grader |
| `cases/<id>/checks.json` | optional checks on the answer: `regex`, `not_regex`, `file_exists`, `file_contains`, `skill_loaded` |
| `cases/<id>/fixtures/` | optional files copied into the workspace (all synthetic, made with `tests/samples.py`) |
| `triggers.json` | 20 prompts: 10 that should load the skill and 10 near misses |
| `agents.toml` | the command templates for each agent and for the grader (flags checked against each CLI's `--help`) |
| `run.py` | the runner |
| `MANUAL.md` | running the cases by hand in VS Code agent mode |
| `results/<date>/<agent>/` | transcripts and outputs (not committed); `summary.md` and `summary.json` may be committed |

Run from the repository root, in PowerShell or Git Bash, signed in to the agent's CLI:

```text
python evals/run.py --agent claude --dry-run
python evals/run.py --agent claude --repeat 3
python evals/run.py --agent copilot --cases run-review,stale-files
python evals/run.py --agent copilot --triggers --no-cases
```

Each run gets a new temporary workspace: the fixtures are copied in and the skill is installed
with `tools/install_skill.py --project <workspace> --project-kind claude` (Claude Code and Copilot
both read `<workspace>/.claude/skills`). The proc-sim-agent data folder is empty unless
`--use-my-index` is given (then help and example searches use your indexes).

A run passes when the agent exits normally, every check passes and the rubric grader says PASS
(`--grader none` grades with the checks only). The skill counts as loaded when the agent's
transcript shows it (`skill_pattern` in `agents.toml`) or, for an agent whose output does not show
skills, when the transcript runs `scripts/fw.py`. Trigger results give precision and recall.

On Windows the npm-installed CLIs are `.cmd` files; arguments with quotes or `%` can be mangled on
the way. The Claude template passes the prompt on standard input for that reason.
