# futi

A Streamlit dashboard for analyzing MLS team performance across different phases of play.

## Features

- View team performance metrics across 19 phases of play
- Filter by team or phase category (Organized possession, Transition, Contested, Set pieces)
- Toggle between raw values and league-wide percentiles
- Per-game statistics (counts divided by 34 games)

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Data

- `phases.csv` - Team phase performance data
- `teams.csv` - Team metadata
- `players.csv` - Player data (for future use)

## Deployment

This app is configured for deployment on [Streamlit Community Cloud](https://streamlit.io/cloud).

1. Push this repo to GitHub
2. Connect the repo to Streamlit Community Cloud
3. Set the main file path to `app.py`
