# Merged branch cleanup

The user requested branch cleanup while v0.4.12 was building. The GitHub
connector supports ref updates but has no ref-deletion tool, so a dedicated
maintenance workflow performs the authorized cleanup through GitHub Actions.

The workflow fetches all heads and selects only ancestors of main. It retains
main, the current release, branches checked out in the four local worktrees, its
own maintenance branch and every open pull request's head. It uploads the plan,
including the complete candidate names and SHAs, before deletion. Open pull
requests are checked again immediately before applying the plan.

Deletion uses one atomic push with an explicit expected SHA for each branch.
A concurrent new commit rejects the entire deletion instead of deleting new
work or leaving a partial cleanup. Tags are untouched. The workflow runs only
on manual dispatch or pushes to maintenance/cleanup-merged.

Four offline checks against local bare Git repositories passed in 0.281 seconds:
merged-only selection with retained main/work/PR heads, atomic rejection after
a concurrent commit, a newly opened PR, and an empty plan with no push.

```sh
python3 .github/tests/test_branch_cleanup.py
git diff --check
```

This document describes the cleanup mechanism and local verification; the Actions
artifact and run result record the actual remote deletion count.
