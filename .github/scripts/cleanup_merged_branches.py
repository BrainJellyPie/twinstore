"""Plan or apply deletion of merged remote branches with exact-head leases."""

import argparse
import json
from pathlib import Path
import subprocess


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def plan(keep, open_prs):
    git("fetch", "origin", "+refs/heads/*:refs/remotes/origin/*", "--prune")
    base = git("rev-parse", "refs/remotes/origin/main")
    protected = {"main", *keep, *open_prs}
    candidates, retained = [], []
    for line in git("for-each-ref", "--format=%(refname) %(objectname)", "refs/remotes/origin/").splitlines():
        ref, sha = line.split()
        name = ref.removeprefix("refs/remotes/origin/")
        if name == "HEAD":
            continue
        entry = {"name": name, "sha": sha}
        result = subprocess.run(["git", "merge-base", "--is-ancestor", sha, base])
        if result.returncode not in (0, 1):
            raise RuntimeError(f"Cannot establish ancestry for {name}")
        (retained if name in protected or result.returncode else candidates).append(entry)
    return {"base": base, "candidates": candidates, "retained": retained}


def apply(audit, open_prs):
    candidates = audit["candidates"]
    if any(b["name"] == "main" or b["name"] in open_prs for b in candidates):
        raise RuntimeError("A candidate is main or now has an open pull request; re-plan cleanup")
    for branch in candidates:
        subprocess.run(["git", "merge-base", "--is-ancestor", branch["sha"], audit["base"]], check=True)
    if candidates:
        git("push", "--atomic", "origin",
            *[f"--force-with-lease=refs/heads/{b['name']}:{b['sha']}" for b in candidates],
            *[f":refs/heads/{b['name']}" for b in candidates])
    print(f"Deleted {len(candidates)} merged branches; retained {len(audit['retained'])}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["plan", "apply"])
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--open-prs", type=Path, required=True)
    parser.add_argument("--keep", action="append", default=[])
    args = parser.parse_args()
    open_prs = set(args.open_prs.read_text().splitlines())
    if args.mode == "plan":
        audit = plan(args.keep, open_prs)
        args.audit.write_text(json.dumps(audit, indent=2) + "\n")
        print(f"Planned {len(audit['candidates'])} merged branches; retained {len(audit['retained'])}.")
    else:
        apply(json.loads(args.audit.read_text()), open_prs)
