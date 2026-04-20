# futi — MLS analytics dashboard

Single-file Streamlit app (`app.py`) with AgGrid tables. Push to `main` auto-deploys via Streamlit Cloud.

## Commands

```
.venv/bin/streamlit run app.py    # local dev (port 8501)
```

## Stack

Python 3.11, Streamlit 1.52.2, pandas >=2.0, streamlit-aggrid 1.2.1, plotly >=5.0. **Streamlit and streamlit-aggrid are pinned** in `requirements.txt` — do not unpin or bump without testing on Streamlit Cloud. Newer Streamlit versions break AgGrid rendering (all AgGrid tabs go blank while Plotly tabs still work). Uses `st.segmented_control()` with radio button fallback for older Streamlit.

## How the app is structured

Everything is in `app.py`. Most tabs follow the same 4-layer pattern:
1. **Constants** at top — `*_COLUMNS` list + `*_DISPLAY_NAMES` dict
2. **`prepare_*_data()`** — adds Logo/Team columns, renames columns, transforms values
3. **`render_*_table()`** — builds AgGrid `column_defs` with grouped two-tier headers
4. **`render_*_tab()`** — loads CSV via `load_data()`, renders filters + table + `render_csv_download()`

**Exception: Team Ratings tab** uses Plotly charts (not AgGrid). Has two views:
- **Compare Teams**: multi-team lines with hover-to-highlight + click-to-lock (client-side JS via `components.html`). White glow trace behind highlighted line. Team crests at line endpoints via `fig.add_layout_image()`. Team picker is a `st.popover` with checkboxes.
- **Team History**: single-team with Overall/Attack/Defense lines.

Wired together in `main()` via `st.tabs()`.

## Team name is the join key — and it's fragile

Team names (e.g., "Inter Miami", "LAFC") must match **exactly** across:
- Every CSV's `team_name` column
- `MLS_CONFERENCES` dict (conference filtering)
- `logos/{team_name}.png` filenames

No validation exists. Mismatches fail silently (missing logos) or mid-render (KeyError). When adding a team, update all three.

## Gotchas

- **`GAMES_PLAYED = 34`** is hardcoded. Used in phases (count → per-game) and team_xg (Totals/Per Game toggle). Must update if season length changes.
- **Percentiles are relative to the current view**, not league-wide. Filtering by conference recalculates percentiles within that subset.
- **Session state keys are per-tab** with inconsistent naming: `view_mode`, `styles_view_mode`, `tendencies_view_mode`, `xg_view_mode`, `history_view_mode`, `history_rating_type`, `hist_cb_{team}`. Using the wrong key silently defaults.
- **Logo caching** — `@st.cache_data` on logo loading. Changed logo files won't appear until cache clears (usually on script edit).
- **No column validation** — `load_data()` doesn't check schema. Missing CSV columns produce Pandas KeyError mid-render.
- **CSS needs `!important`** everywhere to override AgGrid's balham-dark theme.
- **Pinned dependencies** — `streamlit` and `streamlit-aggrid` are pinned in `requirements.txt`. Unpinning or bumping Streamlit causes AgGrid tabs to render blank on Streamlit Cloud (the component JS silently fails to load). Always test on Cloud after any version change.

## AgGrid patterns

- Pinned left: `create_logo_column_def()` + `create_team_column_def()`
- Grouped headers: `columnDefs` with `"children": [...]`
- Sort highlighting: `cellClassRules` → `sorted-col-highlight` class, `onSortChanged` calls `refreshCells({ force: true })`
- Column banding: alternating `phase-band-1` / `phase-band-2` on `headerClass`
- Group dividers: last child gets `phase-divider` (cell) + `phase-divider-header` (header)
- Mobile: `get_mobile_unpin_callback()` unpins Team column at <768px on `onGridReady`
- CSS: team-level tabs use `get_team_styles_table_css()`, phases tab uses `get_phases_table_css()`

## Data files

| File | Format | Notes |
|------|--------|-------|
| `phases.csv` / `phases_against.csv` | Long (team_name, phase, metrics) | Pivoted to wide for display |
| `team_styles.csv` | Wide (team_name + style columns) | Has unnamed index column (auto-dropped) |
| `team_tendencies.csv` | Wide + `season_name` column | Only multi-season CSV |
| `team_xg.csv` | Wide (team_name + xG metrics + points) | `points` = actual 2025 season points |
| `team_ratings.csv` | Long (team_name, rating_date, *_pct) | Monthly ratings 2016–2025, powers Team Ratings tab |
| `team_rating_diagnostics.csv` | Wide (full model output) | Source data with extra columns; reformatted to team_ratings.csv |
| `logos/` | PNGs named `{team_name}.png` | 30 teams |
| `drafts/` | Gitignored | Unreleased data (player_ratings.csv) |

## Hidden/WIP features

Player Ratings tab: code is fully intact in `app.py` (constants, prep, render, tab function). Hidden behind `?dev=true` query param. Data lives in `drafts/player_ratings.csv`. To show publicly: remove the `show_player_ratings` gate in `main()`.
