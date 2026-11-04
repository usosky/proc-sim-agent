#!/usr/bin/env python3
"""Run the eval cases against an agent's non-interactive CLI and grade the answers.

    python evals/run.py --agent claude --cases run-review,stale-files --repeat 3
    python evals/run.py --agent copilot --triggers --no-cases
    python evals/run.py --agent claude --dry-run

Each run gets a temporary workspace: the case's fixtures are copied in and the skill is installed
with `tools/install_skill.py --project <workspace>`. The agent runs there with the command template
from evals/agents.toml. The answer is graded with the case's checks.json and its rubric.md (an LLM
grader, the [grader] command; --grader none skips it). Transcripts and outputs go to
evals/results/<date>/<agent>/ (not committed); summary.md and summary.json there may be committed.

Standard library only (Python 3.8+). The agents need their own sign-in; nothing here stores keys.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INSTALL = ROOT / "tools" / "install_skill.py"
CASES = HERE / "cases"
SKIP_DIRS = {".claude", ".github", ".agents", ".psa-home"}


# ---------------------------------------------------------------------------
# configuration (a small TOML reader for Python < 3.11)
# ---------------------------------------------------------------------------
def _toml_value(text: str):
    text = text.strip()
    if text.startswith("["):
        items, buf, quote, depth = [], "", "", 0
        for ch in text[1:]:
            if quote:
                buf += ch
                if ch == quote and not buf.endswith("\\" + quote):
                    quote = ""
                continue
            if ch in "\"'":
                quote = ch
                buf += ch
            elif ch == "[":
                depth += 1
                buf += ch
            elif ch == "]" and depth:
                depth -= 1
                buf += ch
            elif ch == "]":
                break
            elif ch == ",":
                if buf.strip():
                    items.append(_toml_value(buf))
                buf = ""
            else:
                buf += ch
        if buf.strip():
            items.append(_toml_value(buf))
        return items
    if text.startswith('"'):
        return json.loads(text)
    if text.startswith("'"):
        return text[1:-1]
    if text in ("true", "false"):
        return text == "true"
    try:
        return int(text)
    except ValueError:
        return float(text)


def _strip_comment(line: str) -> str:
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            return line[:i]
    return line


def load_toml(path: Path) -> dict:
    try:
        import tomllib                      # Python 3.11+
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except ImportError:
        pass
    data: dict = {}
    table = data
    pending = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = _strip_comment(raw).rstrip()
        if pending:
            pending += " " + line.strip()
            if pending.count("[") <= pending.count("]"):
                key, val = pending.split("=", 1)
                table[key.strip()] = _toml_value(val)
                pending = ""
            continue
        if not line.strip():
            continue
        m = re.match(r"^\s*\[([^\]]+)\]\s*$", line)
        if m:
            table = data
            for part in m.group(1).split("."):
                table = table.setdefault(part.strip(), {})
            continue
        key, val = line.split("=", 1)
        if val.strip().startswith("[") and val.count("[") > val.count("]"):
            pending = line.strip()
            continue
        table[key.strip()] = _toml_value(val)
    return data


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------
def _front_matter(text: str):
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", text, re.S)
    if not m:
        return {}, text.strip()
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2).strip()


def load_cases(wanted=None) -> list:
    out = []
    for d in sorted(p for p in CASES.iterdir() if (p / "prompt.md").is_file()):
        if wanted and d.name not in wanted:
            continue
        meta, prompt = _front_matter((d / "prompt.md").read_text(encoding="utf-8"))
        checks = json.loads((d / "checks.json").read_text(encoding="utf-8")) if (d / "checks.json").is_file() else []
        out.append({"id": d.name, "meta": meta, "prompt": prompt,
                    "rubric": (d / "rubric.md").read_text(encoding="utf-8").strip(),
                    "checks": checks, "fixtures": d / "fixtures" if (d / "fixtures").is_dir() else None})
    missing = set(wanted or ()) - {c["id"] for c in out}
    if missing:
        raise SystemExit(f"no such case: {', '.join(sorted(missing))}")
    return out


# ---------------------------------------------------------------------------
# running an agent
# ---------------------------------------------------------------------------
def _resolve(cmd: list) -> list:
    exe = shutil.which(cmd[0]) or cmd[0]          # finds claude.cmd / copilot.cmd on Windows
    return [exe] + cmd[1:]


def build_command(cfg: dict, prompt: str, workspace: str, model: str = "") -> list:
    cmd = [str(x).replace("{workspace}", workspace).replace("{prompt}", prompt) for x in cfg["command"]]
    if model and cfg.get("model_flag"):
        cmd += [cfg["model_flag"], model]
    return cmd


def run_cli(cfg: dict, prompt: str, workspace: str, env: dict, timeout: float, model: str = "") -> dict:
    cmd = build_command(cfg, prompt, workspace, model)
    stdin = prompt if cfg.get("prompt_via", "arg") == "stdin" else None
    t0 = time.monotonic()
    try:
        p = subprocess.run(_resolve(cmd), input=stdin, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=workspace, env=env, timeout=timeout)
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        partial = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        rc, out, err = "timeout", partial, f"timed out after {timeout} s"
    except OSError as e:
        rc, out, err = "not started", "", str(e)
    return {"command": cmd, "returncode": rc, "stdout": out, "stderr": err, "seconds": round(time.monotonic() - t0, 1)}


def answer_of(cfg: dict, stdout: str) -> str:
    if cfg.get("answer") == "claude-stream-json":
        result, texts = None, []
        for line in stdout.splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("type") == "result" and isinstance(ev.get("result"), str):
                result = ev["result"]
            elif ev.get("type") == "assistant":
                for block in ev.get("message", {}).get("content", []) or []:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))
        return result if result is not None else "\n".join(texts)
    return stdout.strip()


def skill_loaded(cfg: dict, run: dict, answer: str):
    """(True/False, how): the agent's own signal when configured, else whether it ran fw.py."""
    text = run["stdout"] + "\n" + run["stderr"]
    if cfg.get("skill_pattern"):
        return bool(re.search(cfg["skill_pattern"], text, re.S)), "pattern"
    return bool(re.search(r"scripts[/\\]fw\.py|\bfw\.py\b", text + "\n" + answer)), "ran fw.py"


def make_workspace(case: dict, install_kind: str, use_my_index: bool) -> (Path, dict):
    ws = Path(tempfile.mkdtemp(prefix=f"psa-eval-{case['id']}-"))
    if case.get("fixtures"):
        for f in case["fixtures"].rglob("*"):
            if f.is_file():
                dest = ws / f.relative_to(case["fixtures"])
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(f), str(dest))
    r = subprocess.run([sys.executable, str(INSTALL), "--project", str(ws), "--project-kind", install_kind],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if r.returncode != 0:
        raise SystemExit(f"could not install the skill into {ws}:\n{r.stdout}\n{r.stderr}")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if not use_my_index:
        env["PROC_SIM_AGENT_HOME"] = str(ws / ".psa-home")
    return ws, env


def snapshot(ws: Path) -> dict:
    out = {}
    for f in ws.rglob("*"):
        rel = f.relative_to(ws)
        if f.is_file() and not (set(rel.parts) & SKIP_DIRS):
            out[rel.as_posix()] = f.stat().st_size, f.read_bytes()[:200000]
    return out


# ---------------------------------------------------------------------------
# grading
# ---------------------------------------------------------------------------
def _flags(s: str) -> int:
    return (re.I if "i" in (s or "") else 0) | (re.S if "s" in (s or "") else 0) | (re.M if "m" in (s or "") else 0)


def run_checks(checks: list, answer: str, ws: Path, loaded) -> list:
    out = []
    for c in checks:
        t = c.get("type")
        if t in ("regex", "not_regex"):
            hit = re.search(c["pattern"], answer, _flags(c.get("flags")))
            ok = bool(hit) if t == "regex" else not hit
            out.append({"check": f"{t} {c['pattern']}", "ok": ok})
        elif t in ("file_exists", "file_contains"):
            f = ws / c["path"]
            if not f.is_file():
                out.append({"check": f"{t} {c['path']}", "ok": False, "detail": "file not written"})
                continue
            if t == "file_exists":
                out.append({"check": f"file_exists {c['path']}", "ok": True})
            else:
                text = f.read_bytes().decode("utf-8", errors="replace")
                out.append({"check": f"file_contains {c['path']} {c['pattern']}",
                            "ok": bool(re.search(c["pattern"], text, _flags(c.get("flags"))))})
        elif t == "skill_loaded":
            out.append({"check": "skill_loaded", "ok": bool(loaded[0]), "detail": loaded[1]})
        else:
            out.append({"check": f"unknown check type {t!r}", "ok": False})
    return out


GRADER_PROMPT = """You grade an answer an AI assistant gave to an Aspen Plus user. Judge it only against the rubric.

## The user's request

{prompt}

## Rubric

{rubric}

## The assistant's answer

{answer}

## Files the assistant wrote

{files}

Reply with "VERDICT: PASS" or "VERDICT: FAIL" on the first line, then two or three sentences naming
the rubric points that were met and missed.
"""


def grade(grader: dict, case: dict, answer: str, files: dict, env: dict, timeout: float) -> dict:
    listing = "\n\n".join(f"### {name}\n```\n{data[1].decode('utf-8', errors='replace')[:4000]}\n```"
                          for name, data in files.items()) or "(none)"
    prompt = GRADER_PROMPT.format(prompt=case["prompt"], rubric=case["rubric"], answer=answer[:20000] or "(empty)",
                                  files=listing)
    tmp = tempfile.mkdtemp(prefix="psa-grade-")
    try:
        r = run_cli(grader, prompt, tmp, env, timeout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    m = re.search(r"VERDICT:\s*(PASS|FAIL)", r["stdout"])
    return {"verdict": m.group(1) if m else "ERROR", "reason": r["stdout"].strip()[:2000] or r["stderr"][:500]}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def run_case(case, n, agent_cfg, grader, args, outdir: Path) -> dict:
    ws, env = make_workspace(case, agent_cfg.get("install", "claude"), args.use_my_index)
    try:
        before = snapshot(ws)
        r = run_cli(agent_cfg, case["prompt"], str(ws), env, args.timeout, args.model)
        answer = answer_of(agent_cfg, r["stdout"])
        loaded = skill_loaded(agent_cfg, r, answer)
        after = snapshot(ws)
        new = {k: v for k, v in after.items() if before.get(k) != v}
        checks = run_checks(case["checks"], answer, ws, loaded)
        rub = grade(grader, case, answer, new, env, args.timeout) if grader else {"verdict": "not graded"}
    finally:
        shutil.rmtree(str(ws), ignore_errors=True)
    d = outdir / case["id"] / str(n)
    (d / "files").mkdir(parents=True, exist_ok=True)
    (d / "transcript.txt").write_text(f"$ {' '.join(r['command'])}\nexit: {r['returncode']}\n\n{r['stdout']}\n"
                                      f"--- stderr ---\n{r['stderr']}", encoding="utf-8")
    (d / "answer.md").write_text(answer, encoding="utf-8")
    for name, data in new.items():
        dest = d / "files" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data[1])
    ok_checks = all(c["ok"] for c in checks)
    passed = ok_checks and rub["verdict"] in ("PASS", "not graded") and r["returncode"] == 0
    res = {"case": case["id"], "run": n, "returncode": r["returncode"], "seconds": r["seconds"],
           "skill_loaded": loaded[0], "skill_signal": loaded[1], "checks": checks, "rubric": rub, "pass": passed}
    (d / "result.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    return res


def run_triggers(agent_cfg, args, outdir: Path) -> dict:
    data = json.loads((HERE / "triggers.json").read_text(encoding="utf-8"))
    rows = []
    for t in data["prompts"]:
        case = {"id": "trigger-" + t["id"], "fixtures": None}
        ws, env = make_workspace(case, agent_cfg.get("install", "claude"), args.use_my_index)
        try:
            r = run_cli(agent_cfg, t["prompt"], str(ws), env, args.timeout, args.model)
        finally:
            shutil.rmtree(str(ws), ignore_errors=True)
        answer = answer_of(agent_cfg, r["stdout"])
        loaded, how = skill_loaded(agent_cfg, r, answer)
        rows.append({"id": t["id"], "should": t["should_trigger"], "loaded": loaded, "signal": how,
                     "returncode": r["returncode"]})
        d = outdir / "triggers"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{t['id']}.txt").write_text(f"{r['stdout']}\n--- stderr ---\n{r['stderr']}", encoding="utf-8")
    tp = sum(1 for x in rows if x["should"] and x["loaded"])
    fp = sum(1 for x in rows if not x["should"] and x["loaded"])
    fn = sum(1 for x in rows if x["should"] and not x["loaded"])
    return {"rows": rows, "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None}


def _ratio(a, b):
    return f"{a}/{b}" if b else "-"


def summary_md(agent, version, args, results, trig) -> str:
    L = [f"# Eval results: {agent}, {date.today().isoformat()}", "",
         f"Agent: {version or agent}; grader: {args.grader}; repeats: {args.repeat}; data folder: "
         + ("the user's index" if args.use_my_index else "empty, per run"), ""]
    if results:
        L += ["| Case | Runs | Pass | Checks pass | Rubric pass | Skill loaded |", "|---|---|---|---|---|---|"]
        for cid in sorted({r["case"] for r in results}):
            rs = [r for r in results if r["case"] == cid]
            L.append(f"| {cid} | {len(rs)} | {_ratio(sum(r['pass'] for r in rs), len(rs))} | "
                     f"{_ratio(sum(all(c['ok'] for c in r['checks']) for r in rs), len(rs))} | "
                     f"{_ratio(sum(r['rubric']['verdict'] == 'PASS' for r in rs), len(rs))} | "
                     f"{_ratio(sum(bool(r['skill_loaded']) for r in rs), len(rs))} |")
        total = sum(r["pass"] for r in results)
        L += ["", f"Overall: {total}/{len(results)} runs pass ({100 * total / len(results):.0f} %)."]
    if trig:
        L += ["", "## Triggers", "", "| Prompt | Should load | Loaded |", "|---|---|---|"]
        L += [f"| {x['id']} | {'yes' if x['should'] else 'no'} | {'yes' if x['loaded'] else 'no'} |" for x in trig["rows"]]
        p, r = trig["precision"], trig["recall"]
        how = sorted({x["signal"] for x in trig["rows"]})
        L += ["", f"Precision {p:.2f}" if p is not None else "Precision -",
              f"Recall {r:.2f}" if r is not None else "Recall -", f"(skill detected by: {', '.join(how)})"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", required=True, help="a table under [agents] in agents.toml: claude, copilot")
    ap.add_argument("--cases", help="comma-separated case ids (default: all)")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--triggers", action="store_true", help="also run evals/triggers.json")
    ap.add_argument("--no-cases", action="store_true", help="run only the triggers")
    ap.add_argument("--grader", default="grader", help="'grader' (the [grader] table) or 'none'")
    ap.add_argument("--model", default="", help="model name passed to the agent")
    ap.add_argument("--timeout", type=float, default=900, help="seconds per run")
    ap.add_argument("--use-my-index", action="store_true",
                    help="let the agent use your proc-sim-agent data folder (help and example indexes)")
    ap.add_argument("--config", default=str(HERE / "agents.toml"))
    ap.add_argument("--out", default=str(HERE / "results"))
    ap.add_argument("--dry-run", action="store_true", help="print the commands, run nothing")
    args = ap.parse_args(argv)

    cfg = load_toml(Path(args.config))
    agent_cfg = cfg.get("agents", {}).get(args.agent)
    if not agent_cfg:
        raise SystemExit(f"no [agents.{args.agent}] in {args.config}")
    grader = None if args.grader == "none" else cfg.get(args.grader)
    if args.grader != "none" and not grader:
        raise SystemExit(f"no [{args.grader}] table in {args.config} (or pass --grader none)")
    cases = [] if args.no_cases else load_cases(args.cases.split(",") if args.cases else None)
    if args.dry_run:
        for c in cases:
            print(f"{c['id']}: {' '.join(build_command(agent_cfg, '<prompt>', '<workspace>', args.model))}"
                  + (" < prompt" if agent_cfg.get("prompt_via") == "stdin" else ""))
        return 0
    version = ""
    if agent_cfg.get("version"):
        try:
            v = subprocess.run(_resolve(list(agent_cfg["version"])), capture_output=True, text=True, timeout=60)
            version = (v.stdout or v.stderr).strip().splitlines()[0] if (v.stdout or v.stderr) else ""
        except (OSError, subprocess.SubprocessError, IndexError):
            version = ""
    outdir = Path(args.out) / date.today().isoformat() / args.agent
    n = 2
    while (outdir / "summary.json").exists():          # never overwrite an earlier run of the day
        outdir = Path(args.out) / f"{date.today().isoformat()}-{n}" / args.agent
        n += 1
    outdir.mkdir(parents=True, exist_ok=True)
    results = []
    for c in cases:
        for n in range(1, args.repeat + 1):
            res = run_case(c, n, agent_cfg, grader, args, outdir)
            results.append(res)
            print(f"{c['id']} #{n}: {'PASS' if res['pass'] else 'FAIL'} (checks "
                  f"{sum(x['ok'] for x in res['checks'])}/{len(res['checks'])}, rubric {res['rubric']['verdict']}, "
                  f"skill {'yes' if res['skill_loaded'] else 'no'}, {res['seconds']} s)")
    trig = run_triggers(agent_cfg, args, outdir) if args.triggers else None
    summary = {"agent": args.agent, "version": version, "date": date.today().isoformat(), "results": results,
               "triggers": trig}
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md = summary_md(args.agent, version, args, results, trig)
    (outdir / "summary.md").write_text(md, encoding="utf-8")
    print("\n" + md + f"\nwrote {outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
