#!/usr/bin/env python3
"""Install the aspen-plus skill by copying it (no symlinks) to where an agent looks for skills.

    py -3 tools\\install_skill.py --target claude                 # Claude Code
    py -3 tools\\install_skill.py --target copilot                # GitHub Copilot CLI
    py -3 tools\\install_skill.py --project "D:\\Sims" --project-kind claude   # one project, both agents
    py -3 tools\\install_skill.py --target claude --uninstall

User folders (checked in November 2026: Claude Code docs, `copilot skill list` of Copilot CLI 1.0.105):

  --target claude    ~/.claude/skills/aspen-plus     Claude Code
  --target copilot   ~/.copilot/skills/aspen-plus    GitHub Copilot CLI
  --target agents    ~/.agents/skills/aspen-plus     Copilot CLI, Codex, Gemini CLI

Project folders (--project DIR, --project-kind): github -> DIR/.github/skills/aspen-plus (Copilot),
claude -> DIR/.claude/skills/aspen-plus (Claude Code and Copilot), agents -> DIR/.agents/skills/aspen-plus
(Copilot, Codex, Gemini CLI).

~ is %USERPROFILE% on Windows. The data folder ~/.proc-sim-agent (indexes, config) is never
touched. Standard library only, Python 3.8+.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

NAME = "aspen-plus"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills" / NAME
USER_FOLDERS = {"claude": (".claude", "skills"), "copilot": (".copilot", "skills"), "agents": (".agents", "skills")}
PROJECT_FOLDERS = {"github": (".github", "skills"), "claude": (".claude", "skills"), "agents": (".agents", "skills")}
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".pytest_cache", ".DS_Store", "Thumbs.db")


def destination(a) -> Path:
    if a.project:
        return Path(a.project).expanduser().resolve().joinpath(*PROJECT_FOLDERS[a.project_kind], NAME)
    return Path.home().joinpath(*USER_FOLDERS[a.target], NAME)


def seen_by(project) -> dict:
    """The folders each agent reads skills from (user folders, and the project's when given)."""
    home = Path.home()
    user = {k: home.joinpath(*v, NAME) for k, v in USER_FOLDERS.items()}
    gemini = home / ".gemini" / "skills" / NAME
    out = {"Claude Code": [user["claude"]], "GitHub Copilot": [user["copilot"], user["agents"]],
           "Codex": [user["agents"]], "Gemini CLI": [gemini, user["agents"]]}
    if project:
        p = Path(project).expanduser().resolve()
        proj = {k: p.joinpath(*v, NAME) for k, v in PROJECT_FOLDERS.items()}
        out["Claude Code"].append(proj["claude"])
        out["GitHub Copilot"] += [proj["github"], proj["claude"], proj["agents"]]
        out["Codex"].append(proj["agents"])
        out["Gemini CLI"].append(proj["agents"])
    return out


def claude_plugin_installed() -> bool:
    f = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    try:
        return f"{NAME}@" in json.dumps(json.loads(f.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return False


def is_our_skill(folder: Path) -> bool:
    md = folder / "SKILL.md"
    try:
        head = md.read_text(encoding="utf-8")[:400]
    except OSError:
        return False
    return f"\nname: {NAME}\n" in head.replace("\r\n", "\n")


def duplicate_warnings(project, dest: Path, installing: bool) -> list:
    msgs = []
    for agent, folders in seen_by(project).items():
        copies = {f for f in folders if (f == dest and installing) or (f != dest and is_our_skill(f))}
        if agent == "Claude Code" and claude_plugin_installed():
            copies.add(Path("plugin aspen-plus@proc-sim-agent"))
        if len(copies) > 1:
            msgs.append(f"{agent} will see {len(copies)} copies of {NAME}: "
                        + ", ".join(str(c) for c in sorted(copies, key=str))
                        + ". Keep one (remove the others with --uninstall).")
    return msgs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Copy the aspen-plus skill to an agent's skills folder.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--target", choices=sorted(USER_FOLDERS), default="claude",
                    help="user skills folder (default: claude)")
    ap.add_argument("--project", help="install into this project folder instead of the user folder")
    ap.add_argument("--project-kind", choices=sorted(PROJECT_FOLDERS), default="github",
                    help="which project skills folder (default: github)")
    ap.add_argument("--dry-run", action="store_true", help="say what would happen, change nothing")
    ap.add_argument("--uninstall", action="store_true", help="remove the installed copy")
    ap.add_argument("--force", action="store_true", help="replace an existing copy")
    ap.add_argument("--source", default=str(SOURCE), help=argparse.SUPPRESS)  # tests
    a = ap.parse_args(argv)
    src, dest = Path(a.source), destination(a)
    data = Path.home() / ".proc-sim-agent"
    if dest == data or data in dest.parents:
        print(f"refusing to write into {data}", file=sys.stderr)
        return 2

    if a.uninstall:
        if not dest.exists():
            print(f"nothing installed at {dest}")
            return 0
        if not is_our_skill(dest):
            print(f"{dest} does not hold the {NAME} skill; not removing it", file=sys.stderr)
            return 1
        print(f"{'would remove' if a.dry_run else 'removing'} {dest}")
        if not a.dry_run:
            shutil.rmtree(dest)
        return 0

    if not (src / "SKILL.md").is_file():
        print(f"no skill at {src}", file=sys.stderr)
        return 2
    if dest.exists() and not a.force:
        print(f"{dest} already exists; pass --force to replace it (or --uninstall)", file=sys.stderr)
        return 1
    action = "replace" if dest.exists() else "copy"
    print(f"{'would ' + action if a.dry_run else action.capitalize() + ':'} {src} -> {dest}")
    if not a.dry_run:
        if dest.exists():
            if not is_our_skill(dest):
                print(f"{dest} does not hold the {NAME} skill; not replacing it", file=sys.stderr)
                return 1
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest, symlinks=False, ignore=IGNORE)
    for msg in duplicate_warnings(a.project, dest, installing=True):
        print("warning: " + msg)
    if not a.dry_run:
        print("Start a new agent session (or reload skills) to load it. Then ask: "
              "\"Set up proc-sim-agent for my Aspen Plus help.\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
