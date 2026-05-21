# Gladiator Idle — Community Scripts Library

This folder serves the **Squad Scripts** community library through GitHub
Pages. The single source of truth is one file:

> `docs/scripts-library.json`

The game fetches it from
`https://lifestarse.github.io/gladiator-idle-manager/scripts-library.json`
once every 24 hours (cache lives at `~/.gladiator_scripts_library_cache.json`),
and shows it under **Squad Scripts → Online** in the editor.

## How to submit a script

1. Open your script in the editor, **⚙ → Export**, copy the JSON blob.
2. Fork [`lifestarse/gladiator-idle-manager`](https://github.com/lifestarse/gladiator-idle-manager).
3. Edit `docs/scripts-library.json` and add a new entry to `"scripts"`:

```json
{
  "id": "<unique-kebab-case>",
  "title": "Short, action-oriented",
  "description": "What it does, in one sentence",
  "author": "<your-github-handle>",
  "tags": ["farm", "on_tick", "...you choose..."],
  "stars": 0,
  "program": <PASTE_YOUR_EXPORTED_PROGRAM_HERE>
}
```

The `program` block is what `Export` gave you — paste it verbatim.

4. Open a Pull Request. Title format: `script: <title>`. Brief PR
   description: what trigger it uses (on_battle_end / on_tick / on_demand),
   what game state it expects (e.g. "needs ≥3 fighters, tier 1+").

5. Once merged, the entry shows up in everyone's game within 24 hours
   (or instantly if they tap **Reload** on the Online screen).

## Review criteria — what gets merged

- **Works**: program builds via `Program.from_dict` and `Interpreter.run`
  without errors on a fresh save (CI will run this check).
- **Unique enough**: doesn't duplicate something already in the library —
  if it's a small variant, fold it into the original's description.
- **Honest description**: no hidden side effects ("safe farm" that
  actually trains everyone to L99 is mis-advertised).
- **Reasonable `ops_per_sec`** if it's an on_demand while-loop: 0 means
  UI freeze, which we usually don't want users to opt into without
  knowing. 10000 is a friendly default.
- **No abuse**: a script that just `hire`s 50 fighters then deletes all
  gold isn't a "script", it's a prank. Will be rejected.

The script engine itself is sandboxed (only known AST nodes, no
`eval`/`exec`/network/file I/O), so the worst a malicious script can do
is waste the user's gold — annoying, not dangerous. Still, we keep the
library curated so users don't have to defend against junk.

## Manifest format

```json
{
  "version": 1,
  "updated": "YYYY-MM-DD",
  "source": "https://github.com/lifestarse/gladiator-idle-manager",
  "scripts": [
    { "id": "...", "title": "...", "description": "...",
      "author": "...", "tags": [...], "stars": 0,
      "program": {...} }
  ]
}
```

- `version`: bump if the field shapes change. The client falls back to
  bundled templates if it sees a version it doesn't know yet.
- `stars`: maintained manually for now (no in-game voting at Tier 1).
  Will be replaced by Firestore counts when/if we move to Tier 2.

## Local development

To rebuild the manifest from the in-tree templates:

```bash
python -c "
import json, os
os.environ['KIVY_NO_ARGS']='1'
from game.scripting.templates import TEMPLATES
from game.localization import t, set_language
set_language('en')
out = {'version': 1, 'updated': '...', 'source': '...', 'scripts': [
    {'id': x.id, 'title': t(x.name_key), 'description': t(x.desc_key),
     'author': 'lifestarse', 'tags': ['bundled'], 'stars': 0,
     'program': x.factory().to_dict()} for x in TEMPLATES
]}
json.dump(out, open('docs/scripts-library.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=2)
"
```

This is the same code that produced the initial commit.
