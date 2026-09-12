---
name: commit-and-push
description: Commit selected repository changes and push them to the configured remote branch while preserving unrelated or intentionally untracked files. Use when the user asks to check in, commit, push, or move changes to remote.
metadata:
  short-description: Commit and push repo changes safely
---

# Commit And Push

Use this when the user wants repository changes committed and pushed to a remote branch. The goal is to make the intended changes durable without accidentally adding unrelated local work.

## Core Workflow

1. Inspect the repository state first:
   - `git status --short --branch`
   - `git diff --name-only`
   - `git diff --cached --name-only`
   - `git remote -v` when the remote target is not already clear.
2. Determine the user's intended scope from their words and the status output.
   - If they say `tracked`, `modified`, or `leave untracked`, use `git add -u`.
   - If they say `all files`, `everything`, or name a path that contains untracked files, include untracked files in that path with `git add <path>`.
   - Do not add temp/build/cache paths unless the user explicitly names them or they are clearly part of the requested artifact.
3. Before committing, show yourself the staged set with `git diff --cached --name-only` and confirm it matches the requested scope.
4. Commit with a concise message that reflects the actual change.
5. Put the commit on the requested branch. If the user says `main` and you are on another branch, prefer a clean fast-forward path:
   - Commit on the current branch if needed.
   - Switch to `main`.
   - Fast-forward merge the committed branch with `git merge --ff-only <branch>`.
6. Push the requested branch to the configured remote, usually `git push origin <branch>`.
7. Verify after pushing:
   - `git status --short --branch`
   - `git rev-parse HEAD`
   - `git rev-parse origin/<branch>`
   - Report whether local and remote match, and list any remaining untracked files if relevant.

## Guardrails

- Preserve unrelated dirty work. Never reset, checkout, clean, or delete files unless the user explicitly asks for that operation.
- Treat untracked files carefully. A prior instruction to leave untracked files alone means do not add them, even if they look useful.
- If the user later clarifies that specific untracked files should be included, add only those paths and make a follow-up commit.
- If branch switching or pushing fails because Git cannot write lock files or SSH cannot access the remote from the sandbox, retry the same Git operation with the required permission rather than changing the workflow.
- If the remote rejects the push because it is behind, stop and inspect before pulling, rebasing, merging, or force pushing.

## Final Response

Keep the closeout short and evidence-based. Include:

- commit hash and message
- branch and remote pushed
- confirmation that local and remote hashes match
- any remaining untracked files that were intentionally left behind
