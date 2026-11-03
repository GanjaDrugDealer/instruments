# Local collaboration instructions

- This checkout belongs to ToHuFalse. Work on `to-hu-false/instruments` or a feature branch under `to-hu-false/`.
- Never push changes directly to `main` or to Artem's branches. Do not force push.
- Keep changes focused so Artem can cherry-pick commits or review a pull request.
- Never commit credentials, `token.json`, `.env`, or personal account data.
- The repository contains Artem's reference rules and templates. Adapt personal paths and account names before using them; do not blindly install global rules.
- Install Codex skills with `scripts/install-codex.ps1`. It preserves existing global rules and backs up conflicting skills.
- Use Moscow time for user-facing dates and schedules.
