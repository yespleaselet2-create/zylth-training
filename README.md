# ZYLTH Training Data

Instruction-tuning dataset distilled from building + shipping a complete
Discord community stack: discord.py bot (100+ commands), tickets, automod,
economy/RPG, VPS deploys, Flask dashboard.

## Format

`dataset.jsonl` — one JSON object per line:

```json
{"instruction": "How do I ...?", "input": "", "output": "..."}
```

Standard Alpaca-style. `input` is always empty; everything lives in
`instruction`. Tested with: every line parses as JSON, no empty outputs.

## Contents

- **59 curated topics × 6 phrasings** — expert answers on discord.py patterns,
  moderation, deploys, debugging real incidents from this build.
- **AST code pairs** — real functions extracted from the bot source
  (docstring/task → implementation).
- **Safety pair** — self-bots/user-token automation refused (ToS).

Regenerate: `python generate_data.py --bot-dir ../discord-bot --out dataset.jsonl`

## Stats

See `stats.json` (currently 403 pairs, 0 skipped by the secret scanner).

## Hygiene

The generator rejects any pair matching secret patterns (tokens, emails,
snowflake IDs). No credentials in this repo — ever. Verify:
`grep -rE 'ghp_|DISCORD_TOKEN=' .` should print nothing.
