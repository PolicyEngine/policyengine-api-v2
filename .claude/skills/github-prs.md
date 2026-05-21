# GitHub PR Workflow

Use this guidance before opening, replacing, or marking ready any pull request.

## Required Flow

1. Open a GitHub issue for the work unless the user explicitly says not to.
2. Create or update a feature branch based on `origin/main`.
3. Run formatting and the most relevant tests for the changed surface.
4. Push the branch.
5. Open a same-repository draft PR.
6. Put `Fixes #ISSUE_NUMBER` as the first line of the PR description.
7. Add `Summary` and `Testing` sections below the `Fixes #...` line.

## Suggested Commands

```bash
git fetch origin main
git rebase origin/main
git push -u origin "$(git branch --show-current)"
gh issue create --repo PolicyEngine/policyengine-api-v2
gh pr create --draft --repo PolicyEngine/policyengine-api-v2 \
  --head "$(git branch --show-current)" --base main
```

If a check was not run, note that explicitly in the PR body.
