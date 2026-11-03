# Local collaboration instructions

## Repository and working directory

- The canonical working directory for AI Instruments is `C:\Ai Projects\Codex\Ai Instruments`.
- The shared repository is `https://github.com/GanjaDrugDealer/ai-instruments.git`; `origin` points there.
- Use this checkout explicitly, even when the chat starts in a synced ChatGPT project mirror. Do not edit synced `sources/` files.

## Branches and collaboration

- This checkout belongs to ToHuFalse. Work on `to-hu-false/instruments` or a feature branch under `to-hu-false/`.
- Never push changes directly to `main` or to Artem's branches. Do not force push.
- Before changes, check the current branch, working tree and remote. Fetch updates before integrating upstream work; preserve local changes and resolve conflicts without discarding anyone's work.
- Integrate useful upstream changes from `origin/main` deliberately into our branch. Do not automatically merge or deploy everything from upstream.
- Keep changes focused so Artem can cherry-pick commits or review a pull request.
- After completing an authorized task, inspect the diff, check for secrets, commit only its files and push our current branch. Verify that the remote branch matches the local commit. Creating or merging a pull request requires a user request.

## Local setup

- Never commit credentials, `token.json`, `.env`, or personal account data.
- The repository contains Artem's reference rules and templates. Adapt personal paths and account names before using them; do not blindly install global rules.
- Install Codex skills with `scripts/install-codex.ps1`. It preserves existing global rules and backs up conflicting skills.
- Use Moscow time for user-facing dates and schedules.
