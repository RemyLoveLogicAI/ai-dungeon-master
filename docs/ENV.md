# Environment variables

<!-- AUTO-GENERATED: regenerated from source; edit code, not this file -->

The repository ships no `.env.example` template; this table is generated from
the `os.environ` reads in the source. All variables are optional.

| Variable | Required | Read by | Default |
| --- | --- | --- | --- |
| `AI_DM_AUDIO_DIR` | No | `audio_synth.default_audio_dir` | `$XDG_CACHE_HOME/ai-dungeon-master/audio_output` or `~/.cache/ai-dungeon-master/audio_output` |
| `AI_DM_LOG_DIR` | No | `combat_log.default_log_dir` | `$XDG_CACHE_HOME/ai-dungeon-master/logs` or `~/.cache/ai-dungeon-master/logs` |
| `AI_DM_CAMPAIGN_DB` | No | `game_server` module load | `<repo>/data/campaigns.db` |
| `XDG_CACHE_HOME` | No | `audio_synth` and `combat_log` (shared fallback root) | `~/.cache` |
| `UPDATE_FIXTURES` | No | `test_vr_server.py` only (test fixture regeneration) | unset |

Notes:

- `AI_DM_AUDIO_DIR` overrides `audio_synth.default_audio_dir()`, but which
  entry points honor it differs: standalone `tui_runner` and `vr_server.py`
  generate SFX into `default_audio_dir()` at startup; `combat_runner` uses
  `<cwd>/audio_output` unless its `audio_dir` parameter is passed (it never
  reads this variable); `engine/dm_tui.py` generates no WAVs at all;
  `engine/api_server.py` ignores it and generates SFX once at import into
  `<repo>/audio_output`.
- `AI_DM_LOG_DIR` overrides `combat_log.default_log_dir()`. That directory is
  used by `tui_runner` as the `--resume` fallback when `--log` is not given;
  it does NOT affect `save_log`/`load_log` paths, which resolve relative to
  the caller's working directory.
- `AI_DM_CAMPAIGN_DB` selects the SQLite path for `game_server.py` only —
  read once at module load (`game_server.py:46`) and injected into
  `CampaignService` via `CampaignStore`. `engine/api_server.py` opens its own
  `CampaignStore` at the fixed `<repo>/data/campaigns.db` and ignores the
  variable; `campaign_service.py` receives a store and opens none itself;
  `campaign_mcp.py` never touches `CampaignStore` — it is a stdio JSON-RPC
  adapter that calls `game_server` :8766 over HTTP via `CampaignClient`.
- `XDG_CACHE_HOME` is the standard Linux cache-root override both
  `default_audio_dir` and `default_log_dir` honor before falling back to
  `~/.cache`.
- `UPDATE_FIXTURES=1` is test-only: `test_vr_server.py` uses it to rewrite
  recorded fixture responses; it is not a runtime setting.
