"""AspenTech's official examples, read in place on a computer where Aspen Plus is installed.

Runs only where an examples folder exists: PSA_ASPEN_EXAMPLES, else the folder that `setup --auto`
finds. Skipped everywhere else, so CI is not affected. The files are read where they are; nothing
is copied, written or kept."""
import pytest

from conftest import examples_folder
from fwlib import bkp, freshness

SAMPLE = 40
PRIVATE = ("desktop-", "\\users\\", "administrator")    # computer, user-folder and account names


def spread(files: list, n: int) -> list:
    """Up to n items spread evenly over the list (sorted by size: small, medium and large models)."""
    if len(files) <= n:
        return list(files)
    return [files[round(i * (len(files) - 1) / (n - 1))] for i in range(n)]


def test_spread():
    assert spread(list(range(5)), 40) == [0, 1, 2, 3, 4]
    picked = spread(list(range(215)), 40)
    assert len(set(picked)) == 40 and picked[0] == 0 and picked[-1] == 214


def test_official_examples_read_in_place():
    folder = examples_folder()
    files = sorted(folder.rglob("*.bkp"), key=lambda f: f.stat().st_size)
    if not files:
        pytest.skip(f"no .bkp files under {folder}")
    problems = []
    for f in spread(files, SAMPLE):
        name = str(f.relative_to(folder))
        try:
            d = bkp.parse(f)
            md = bkp.render_markdown(d)
        except Exception as e:  # every exception is a finding here
            problems.append(f"{name}: {type(e).__name__}: {e}")
            continue
        low = md.lower()
        problems += [f"{name}: the digest contains {s!r}" for s in PRIVATE if s in low]
        if d["run"].get("has_results") and freshness.stamp(f)["time"] is None:
            problems.append(f"{name}: a results section but no run time")
    assert not problems, "\n".join(problems)
