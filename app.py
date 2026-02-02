"""
Futi Phase Explorer - A Streamlit dashboard for analyzing football phase data.

This app displays team performance metrics across different phases of play
(e.g., buildup, counterattack, set pieces). Users can:
- Filter by team or view all teams
- Filter by phase category (e.g., "Organized possession", "Transition")
- Toggle between raw values and league-wide percentiles

Data source: phases.csv (expected in same directory as this file)
"""

import base64
from pathlib import Path

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, JsCode

# =============================================================================
# CONFIGURATION
# =============================================================================

GAMES_PLAYED = 34  # Number of games in the season (used to calculate per-game stats)

# Brand colors used throughout the UI
COLORS = {
    "dark": "#03151E",      # Darkest background
    "dark1": "#062230",     # Primary background
    "dark2": "#0E374B",     # Card/header background
    "light": "#FFFFFF",
    "light1": "#6A7A83",    # Muted text
    "green": "#0FE6B4",     # Primary accent (brand color)
    "blue": "#00B7FF",
    "pink": "#EA1F96",
    "purple": "#6A62F8",
}

# =============================================================================
# PHASE DEFINITIONS
#
# Phases are grouped into categories. The order here determines display order.
# =============================================================================

PHASE_CATEGORIES_ORDERED = [
    ("Organized possession", [
        "buildup",
        "progression",
        "accelerated_possession",
        "finishing",
    ]),
    ("Transition", [
        "securing_possession",
        "counterattack",
        "high_transition",
    ]),
    ("Contested", [
        "high_ball",
        "loose_ball",
    ]),
    ("Attacking set piece", [
        "corner",
        "corner_second_phase",
        "attacking_throw_in",
        "attacking_freekick",
        "attacking_freekick_second_phase",
        "penalty",
    ]),
    ("Possession set piece", [
        "kickoff",
        "long_goalkick",
        "short_goalkick",
        "possession_throw_in",
        "possession_freekick",
    ]),
]

# Flatten all phases into a single ordered list
ALL_PHASES = [phase for _, phases in PHASE_CATEGORIES_ORDERED for phase in phases]

# Build the category dropdown options: "All phases" first, then each category
PHASE_CATEGORIES = {"All phases": ALL_PHASES}
PHASE_CATEGORIES.update({name: phases for name, phases in PHASE_CATEGORIES_ORDERED})

# Human-readable names for phases (overrides the default title-casing)
PHASE_DISPLAY_NAMES = {
    "accelerated_possession": "Fast break",
    "long_goalkick": "Goal kick (long)",
    "short_goalkick": "Goal kick (short)",
}

# =============================================================================
# TEAM STYLES DEFINITIONS
# =============================================================================

STYLE_COLUMNS = [
    "Bunker and Counter",
    "Control and Regroup",
    "Launch and Squish",
    "Press and Possess",
]

# =============================================================================
# TEAM TENDENCIES DEFINITIONS
# =============================================================================

TENDENCIES_COLUMNS = [
    "building_patient",
    "progression_patient",
    "chaos",
    "highpress",
    "counterpress",
]

TENDENCIES_DISPLAY_NAMES = {
    "building_patient": "Patient Building",
    "progression_patient": "Patient Progression",
    "chaos": "Chaos",
    "highpress": "High Press",
    "counterpress": "Counterpress",
}

# =============================================================================
# METRIC DEFINITIONS
#
# The app shows three metrics per phase. These map CSV column names to display names.
# =============================================================================

# Raw value columns from the CSV
VALUE_METRICS = ["count", "success_rate", "percent_of_total"]

# Percentile columns from the CSV (league-wide ranking)
PERCENTILE_METRICS = [
    "count_percentile",
    "success_rate_percentile",
    "percent_of_total_percentile",
]

# Display names for table headers
METRIC_DISPLAY_NAMES = {
    "count": "Count",
    "success_rate": "Won",
    "percent_of_total": "Share",
    "count_percentile": "Count",
    "success_rate_percentile": "Won",
    "percent_of_total_percentile": "Share",
}

# =============================================================================
# MLS CONFERENCE DEFINITIONS (2025 Season)
# =============================================================================

MLS_CONFERENCES = {
    "Eastern Conference": [
        "Atlanta United",
        "Charlotte",
        "Chicago Fire",
        "Cincinnati",
        "Columbus Crew",
        "DC United",
        "Inter Miami",
        "CF Montreal",
        "Nashville SC",
        "New England Revolution",
        "New York City FC",
        "New York Red Bulls",
        "Orlando City",
        "Philadelphia Union",
        "Toronto FC",
    ],
    "Western Conference": [
        "Austin FC",
        "Colorado Rapids",
        "FC Dallas",
        "Houston Dynamo",
        "LA Galaxy",
        "LAFC",
        "Minnesota United",
        "Portland Timbers",
        "Real Salt Lake",
        "San Diego FC",
        "San Jose Earthquakes",
        "Seattle Sounders",
        "Sporting Kansas City",
        "St. Louis City",
        "Vancouver Whitecaps",
    ],
}


# =============================================================================
# SHARED GRID COMPONENTS
# =============================================================================

# Logo renderer - identical JsCode used in both tables
LOGO_RENDERER = JsCode("""
    class LogoRenderer {
        init(params) {
            this.eGui = document.createElement('div');
            this.eGui.style.display = 'flex';
            this.eGui.style.alignItems = 'center';
            this.eGui.style.justifyContent = 'center';
            this.eGui.style.height = '100%';
            if (params.value) {
                const img = document.createElement('img');
                img.src = params.value;
                img.style.width = '24px';
                img.style.height = '24px';
                img.style.objectFit = 'contain';
                this.eGui.appendChild(img);
            }
        }
        getGui() { return this.eGui; }
        refresh() { return false; }
    }
""")


def create_logo_column_def() -> dict:
    """Standard logo column definition for AgGrid tables."""
    return {
        "field": "Logo",
        "headerName": "",
        "pinned": "left",
        "width": 50,
        "maxWidth": 50,
        "minWidth": 50,
        "cellRenderer": LOGO_RENDERER,
        "sortable": False,
        "filter": False,
        "resizable": False,
        "suppressMenu": True,
    }


def create_team_column_def(cell_class: str = "team-divider") -> dict:
    """Standard team name column definition for AgGrid tables."""
    return {
        "field": "Team",
        "headerName": "",
        "width": 200,
        "minWidth": 180,
        "sortable": True,
        "filter": False,
        "suppressMenu": True,
        "cellClass": cell_class,
        "headerClass": "team-divider-header",
        "pinned": "left",
    }


def get_mobile_unpin_callback(size_to_fit: bool = False) -> JsCode:
    """Create callback to unpin Team column on mobile (<768px)."""
    if size_to_fit:
        return JsCode("""
            function(params) {
                const api = params.api;
                const isMobile = window.innerWidth < 768;
                if (isMobile) {
                    api.applyColumnState({
                        state: [{ colId: 'Team', pinned: null }]
                    });
                }
                api.sizeColumnsToFit();
            }
        """)
    return JsCode("""
        function(params) {
            const api = params.api;
            const isMobile = window.innerWidth < 768;
            if (isMobile) {
                api.applyColumnState({
                    state: [{ colId: 'Team', pinned: null }]
                });
            }
        }
    """)


# =============================================================================
# SHARED CSS STYLES
# =============================================================================

# Dark band color used for header background
HEADER_BG = "#0A2D3D"


def get_base_aggrid_css() -> dict:
    """Return CSS rules shared by all AgGrid tables."""
    return {
        # Row styling
        ".ag-row": {
            "background-color": f"{COLORS['dark1']} !important",
            "border-bottom": "1px solid rgba(255,255,255,0.05) !important",
        },
        ".ag-row-odd": {
            "background-color": "rgba(14,55,75,0.3) !important",
        },
        ".ag-row:hover": {
            "background-color": "rgba(15,230,180,0.08) !important",
        },
        # Cell styling - base styles
        ".ag-cell": {
            "color": "rgba(255,255,255,0.9) !important",
            "display": "flex !important",
            "align-items": "center !important",
            "font-size": "0.875rem !important",
        },
        # Numeric cells right-aligned
        ".numeric-cell": {
            "justify-content": "flex-end !important",
            "padding-right": "6px !important",
        },
        # Divider classes
        ".team-divider": {
            "border-right": "1px solid rgba(255,255,255,0.15) !important",
        },
        ".team-divider-header": {
            "border-right": "1px solid rgba(255,255,255,0.15) !important",
        },
        ".phase-divider": {
            "border-right": "1px solid rgba(255,255,255,0.15) !important",
        },
        ".phase-divider-header": {
            "border-right": "1px solid rgba(255,255,255,0.15) !important",
        },
        # Phase banding - alternating background colors
        ".ag-header-cell.phase-band-1": {
            "background-color": "#0E374B !important",
        },
        ".ag-header-cell.phase-band-2": {
            "background-color": "#0A2D3D !important",
        },
        # Pinned left header - match body row color with right border
        ".ag-pinned-left-header": {
            "background-color": f"{COLORS['dark1']} !important",
            "border-right": "1px solid rgba(255,255,255,0.15) !important",
            "z-index": "10 !important",
        },
        ".ag-pinned-left-header .ag-header-row": {
            "background-color": f"{COLORS['dark1']} !important",
        },
        ".ag-pinned-left-header .ag-header-cell": {
            "background-color": f"{COLORS['dark1']} !important",
        },
        ".ag-pinned-left-header .ag-header-group-cell": {
            "background-color": f"{COLORS['dark1']} !important",
        },
        ".ag-header-cell[col-id='Team']": {
            "background-color": f"{COLORS['dark1']} !important",
            "border-right": "1px solid rgba(255,255,255,0.15) !important",
        },
        ".ag-pinned-left-cols-container": {
            "border-right": "1px solid rgba(255,255,255,0.15) !important",
            "z-index": "10 !important",
        },
        ".ag-pinned-left-cols-container .ag-row": {
            "background-color": f"{COLORS['dark1']} !important",
        },
        ".ag-pinned-left-cols-container .ag-row-odd": {
            "background-color": "rgba(14,55,75,0.3) !important",
        },
        # Team column left-align and divider (col-id selector is more robust than class)
        ".ag-cell[col-id='Team']": {
            "justify-content": "flex-start !important",
            "padding-left": "12px !important",
            "border-right": "1px solid rgba(255,255,255,0.15) !important",
        },
        # Root/wrapper styling
        ".ag-root-wrapper": {
            "background-color": f"{COLORS['dark1']} !important",
            "border": "none !important",
            "border-radius": "0.5rem !important",
        },
        ".ag-body-viewport": {
            "background-color": f"{COLORS['dark1']} !important",
        },
        # Scrollbar styling
        ".ag-body-horizontal-scroll-viewport::-webkit-scrollbar": {
            "height": "8px !important",
        },
        ".ag-body-horizontal-scroll-viewport::-webkit-scrollbar-track": {
            "background": f"{COLORS['dark']} !important",
        },
        ".ag-body-horizontal-scroll-viewport::-webkit-scrollbar-thumb": {
            "background": "rgba(255,255,255,0.2) !important",
            "border-radius": "4px !important",
        },
        # Cell focus/selection styling - use green accent
        ".ag-cell-focus": {
            "border": f"1px solid {COLORS['green']} !important",
            "outline": "none !important",
        },
        ".ag-cell:focus": {
            "border": f"1px solid {COLORS['green']} !important",
            "outline": "none !important",
        },
        # Sorted column header styling
        ".ag-header-cell-sorted-asc, .ag-header-cell-sorted-desc": {
            "color": f"{COLORS['green']} !important",
        },
        ".ag-header-cell-sorted-asc .ag-header-cell-label, .ag-header-cell-sorted-desc .ag-header-cell-label": {
            "color": f"{COLORS['green']} !important",
        },
        # Sort icon styling
        ".ag-sort-ascending-icon, .ag-sort-descending-icon": {
            "color": f"{COLORS['green']} !important",
        },
        # Highlight cells in the sorted column with green tint
        ".sorted-col-highlight": {
            "background-color": "rgba(15,230,180,0.12) !important",
        },
        # Logo column styling - no border between Logo and Team
        ".ag-header-cell[col-id='Logo']": {
            "border-right": "none !important",
        },
        ".ag-cell[col-id='Logo']": {
            "border-right": "none !important",
        },
    }


def get_phases_table_css() -> dict:
    """CSS for phases table (adds header styling and phase banding)."""
    base = get_base_aggrid_css()
    phases_specific = {
        # Header styling
        ".ag-header": {
            "background-color": f"{HEADER_BG} !important",
            "border-bottom": "1px solid rgba(255,255,255,0.1) !important",
        },
        ".ag-header-cell": {
            "background-color": f"{HEADER_BG} !important",
            "color": "rgba(255,255,255,0.6) !important",
            "font-weight": "600 !important",
            "font-size": "0.75rem !important",
            "text-transform": "uppercase !important",
            "letter-spacing": "0.04em !important",
        },
        ".ag-header-cell-label": {
            "justify-content": "center !important",
        },
        # Group header (phase names) styling - top tier of two-tier headers
        ".ag-header-group-cell": {
            "color": "rgba(255,255,255,0.9) !important",
            "font-weight": "700 !important",
            "font-size": "0.9rem !important",
            "border-bottom": "1px solid rgba(255,255,255,0.15) !important",
            "border-right": "1px solid rgba(255,255,255,0.08) !important",
            "text-align": "center !important",
        },
        ".ag-header-group-cell-label": {
            "width": "100% !important",
            "display": "flex !important",
            "justify-content": "center !important",
            "text-align": "center !important",
            "padding": "0 !important",
        },
        ".ag-header-group-text": {
            "text-align": "center !important",
        },
        # Phase banding for group headers
        ".ag-header-group-cell.phase-band-1": {
            "background-color": "#0E374B !important",
        },
        ".ag-header-group-cell.phase-band-2": {
            "background-color": "#0A2D3D !important",
        },
    }
    return {**base, **phases_specific}


def get_team_styles_table_css() -> dict:
    """CSS for team styles table (adds whitespace fixes, style headers)."""
    base = get_base_aggrid_css()
    styles_specific = {
        # Fix whitespace: Make header empty space match body background
        ".ag-header": {
            "background-color": f"{COLORS['dark1']} !important",
            "border-bottom": "1px solid rgba(255,255,255,0.1) !important",
        },
        ".ag-header-viewport": {
            "background-color": f"{COLORS['dark1']} !important",
        },
        ".ag-header-container": {
            "background-color": f"{COLORS['dark1']} !important",
        },
        ".ag-header-row": {
            "background-color": f"{COLORS['dark1']} !important",
        },
        # Second tier headers - match phases tab style
        ".ag-header-cell": {
            "background-color": f"{HEADER_BG} !important",
            "color": "rgba(255,255,255,0.6) !important",
            "font-weight": "600 !important",
            "font-size": "0.75rem !important",
            "text-transform": "uppercase !important",
            "letter-spacing": "0.04em !important",
        },
        ".ag-header-cell-label": {
            "justify-content": "center !important",
        },
        # Style header text wrapping
        ".style-header-wrap .ag-header-cell-text": {
            "white-space": "normal !important",
            "text-align": "center !important",
            "line-height": "1.2 !important",
        },
        # Season Style header - spans full height
        ".team-style-header": {
            "background-color": "#0A2D3D !important",
            "display": "flex !important",
            "align-items": "center !important",
            "justify-content": "center !important",
            "color": "rgba(255,255,255,0.9) !important",
            "font-weight": "700 !important",
            "font-size": "0.9rem !important",
            "text-transform": "none !important",
        },
        ".team-style-header .ag-header-cell-text": {
            "white-space": "normal !important",
            "text-align": "center !important",
            "line-height": "1.2 !important",
        },
        # Group header (Match Styles, Season Style) - first tier
        ".ag-header-group-cell": {
            "color": "rgba(255,255,255,0.9) !important",
            "font-weight": "700 !important",
            "font-size": "0.9rem !important",
            "border-bottom": "1px solid rgba(255,255,255,0.15) !important",
            "text-align": "center !important",
        },
        ".ag-header-group-cell-label": {
            "justify-content": "center !important",
            "width": "100% !important",
            "text-align": "center !important",
        },
        ".ag-header-group-text": {
            "text-align": "center !important",
            "width": "100% !important",
        },
        # Team Style column - text wrapping with line breaks preserved
        ".team-style-cell": {
            "white-space": "pre-line !important",
            "line-height": "1.3 !important",
            "padding": "6px 10px !important",
            "justify-content": "flex-start !important",
        },
        # Ensure all body/viewport containers have consistent background
        ".ag-root": {
            "background-color": f"{COLORS['dark1']} !important",
        },
        ".ag-center-cols-viewport": {
            "background-color": f"{COLORS['dark1']} !important",
        },
        ".ag-center-cols-container": {
            "background-color": f"{COLORS['dark1']} !important",
        },
        ".ag-center-cols-clipper": {
            "background-color": f"{COLORS['dark1']} !important",
        },
        ".ag-body-horizontal-scroll-viewport": {
            "background-color": f"{COLORS['dark1']} !important",
        },
    }
    return {**base, **styles_specific}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def filter_by_conference(df: pd.DataFrame, conference: str) -> pd.DataFrame:
    """Filter DataFrame by MLS conference."""
    if conference == "All MLS":
        return df.copy()
    conference_teams = MLS_CONFERENCES.get(conference, [])
    return df[df["team_name"].isin(conference_teams)].copy()


def render_csv_download(data: pd.DataFrame, filename: str) -> None:
    """Render a CSV download link for the given data."""
    if data.empty:
        return
    export_cols = [c for c in data.columns if c != "Logo" and not c.startswith("_")]
    csv_data = data[export_cols].to_csv(index=False)
    csv_b64 = base64.b64encode(csv_data.encode()).decode()
    st.markdown(
        f'<div style="text-align: right; margin-top: -1.5rem;">'
        f'<a href="data:text/csv;base64,{csv_b64}" download="{filename}" '
        f'style="color: rgba(255,255,255,0.4); font-size: 0.75rem; text-decoration: none;">'
        f'Download CSV</a></div>',
        unsafe_allow_html=True,
    )


# =============================================================================
# DATA LOADING
# =============================================================================


def get_file_mtime(path: Path) -> float:
    """Get file modification time, or 0 if file doesn't exist."""
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return 0.0


@st.cache_data(show_spinner=False)
def load_data(path: str, _mtime: float) -> pd.DataFrame:
    """
    Load CSV data with Streamlit caching.

    The _mtime parameter (prefixed with _ to exclude from cache key display)
    ensures the cache invalidates when the file changes.
    """
    df = pd.read_csv(path)

    # Remove any unnamed columns (often artifacts from CSV exports)
    unnamed_cols = [c for c in df.columns if str(c).lower().startswith("unnamed")]
    if unnamed_cols:
        df = df.drop(columns=unnamed_cols)

    return df


# =============================================================================
# DATA TRANSFORMATION
# =============================================================================


def format_phase_name(phase: str) -> str:
    """
    Convert internal phase name to display name.

    Examples:
        "buildup" -> "Buildup"
        "accelerated_possession" -> "Fast break" (custom override)
        "high_ball" -> "High ball"
    """
    if phase in PHASE_DISPLAY_NAMES:
        return PHASE_DISPLAY_NAMES[phase]
    return phase.replace("_", " ").capitalize()


def create_wide_table(
    df: pd.DataFrame,
    phases: list[str],
    show_percentiles: bool,
) -> tuple[pd.DataFrame, list[tuple[str, str, str, str]]]:
    """
    Transform long-format data into a wide table for display with AgGrid.

    Creates a table where:
    - Rows are teams (sorted alphabetically)
    - First column is team logo (for pinning)
    - Second column is team name (for pinning)
    - Remaining columns are phase metrics with flat "Phase | Metric" names
      (AgGrid handles column grouping via GridOptionsBuilder)

    Args:
        df: Source data with columns: team_name, phase, and metric columns
        phases: List of phases to include (in display order)
        show_percentiles: If True, show percentile rankings; if False, show raw values

    Returns:
        Tuple of (DataFrame ready for display, columns_config list)
        columns_config contains (phase_display, metric_display, raw_metric, raw_phase) tuples
    """
    metrics = PERCENTILE_METRICS if show_percentiles else VALUE_METRICS

    # Filter to only the phases we want
    df_filtered = df[df["phase"].isin(phases)]
    if df_filtered.empty:
        return pd.DataFrame(), []

    # Pivot: rows=teams, columns=(metric, phase)
    pivoted = df_filtered.pivot(index="team_name", columns="phase", values=metrics)

    # Build columns in the desired order: Phase1/Count, Phase1/Won, Phase1/Share, Phase2/Count, ...
    columns_config = []  # List of (display_phase, display_metric, raw_metric, raw_phase)
    for phase in phases:
        phase_display = format_phase_name(phase)
        for metric in metrics:
            metric_display = METRIC_DISPLAY_NAMES[metric]
            columns_config.append((phase_display, metric_display, metric, phase))

    # Extract and transform each column with flat column names for AgGrid
    result_data = {"Logo": [], "Team": []}

    # Initialize phase columns
    for phase_display, metric_display, _, _ in columns_config:
        col_name = f"{phase_display} | {metric_display}"
        result_data[col_name] = []

    # Get sorted team names
    team_names = sorted(pivoted.index.tolist())

    for team in team_names:
        # Add logo and team name
        result_data["Logo"].append(get_team_logo_base64(team))
        result_data["Team"].append(team)

        # Add phase metric values
        for phase_display, metric_display, metric, phase in columns_config:
            col_name = f"{phase_display} | {metric_display}"
            try:
                val = pivoted.loc[team, (metric, phase)]
            except KeyError:
                val = None

            # Transform values for display
            if val is not None and pd.notna(val):
                if metric == "count":
                    # Convert total count to per-game average
                    val = round(val / GAMES_PLAYED, 1)
                elif metric.endswith("_percentile"):
                    # Convert decimals to percentages and round to integer
                    val = round(val * 100)
                elif metric in ("success_rate", "percent_of_total"):
                    # Convert decimals to percentages with 1 decimal place
                    val = round(val * 100, 1)

            result_data[col_name].append(val)

    result = pd.DataFrame(result_data)
    return result, columns_config


def get_dominant_style(row: pd.Series) -> str:
    """
    Get the dominant style(s) for a team based on highest percentage value.

    If there's a tie, returns both styles separated by a line break.
    """
    style_values = {col: row[col] for col in STYLE_COLUMNS}
    max_val = max(style_values.values())
    dominant = [col for col, val in style_values.items() if val == max_val]
    return "\n".join(dominant)


def prepare_team_styles_data(df: pd.DataFrame, show_percentiles: bool = False) -> pd.DataFrame:
    """
    Prepare team styles data for display with logos.

    Args:
        df: Source data with team_name and style columns
        show_percentiles: If True, convert values to league percentiles (0-100)

    Returns:
        DataFrame with Logo, Team, Team Style, and style percentage columns
    """
    result = pd.DataFrame()
    result["Logo"] = df["team_name"].apply(get_team_logo_base64)
    result["Team"] = df["team_name"]

    # Calculate dominant style before any percentile transformation
    result["Team Style"] = df.apply(get_dominant_style, axis=1)

    for col in STYLE_COLUMNS:
        if show_percentiles:
            # Calculate percentile rank within the current dataset (0-100)
            result[col] = df[col].rank(pct=True).mul(100).round(0).astype(int)
        else:
            result[col] = df[col].round(1)

    return result.sort_values("Team").reset_index(drop=True)


def prepare_team_tendencies_data(df: pd.DataFrame, show_percentiles: bool = False) -> pd.DataFrame:
    """
    Prepare team tendencies data for display with logos.

    Args:
        df: Source data with team_name and tendencies columns
        show_percentiles: If True, convert values to league percentiles (0-100)

    Returns:
        DataFrame with Logo, Team, and tendencies columns
    """
    result = pd.DataFrame()
    result["Logo"] = df["team_name"].apply(get_team_logo_base64)
    result["Team"] = df["team_name"]

    for col in TENDENCIES_COLUMNS:
        display_name = TENDENCIES_DISPLAY_NAMES[col]
        if show_percentiles:
            # Calculate percentile rank within the current dataset (0-100)
            result[display_name] = df[col].rank(pct=True).mul(100).round(0).astype(int)
        else:
            result[display_name] = df[col].round(0).astype(int)

    return result.sort_values("Team").reset_index(drop=True)


# =============================================================================
# UI COMPONENTS
# =============================================================================


@st.cache_data(show_spinner=False)
def get_logo_base64() -> str:
    """Load the futi logo and return as a base64 data URI for embedding in HTML."""
    logo_path = Path(__file__).resolve().parent / "futi_logo.png"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
            return f"data:image/png;base64,{encoded}"
    return ""


def get_team_logo_base64(team_name: str) -> str:
    """Load a team's logo and return as a base64 data URI for embedding."""
    logo_path = Path(__file__).resolve().parent / "logos" / f"{team_name}.png"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
            return f"data:image/png;base64,{encoded}"
    return ""


def render_header() -> None:
    """Render the page header with logo."""
    logo_src = get_logo_base64()
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:.75rem;">
          <img src="{logo_src}" width="40" height="40" alt="futi logo" />
          <div style="font-size: 1.9rem; font-weight: 800; letter-spacing: -0.02em;
                      color:{COLORS['green']};">futi</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_toggle(options: list[str], key: str, default: str) -> str:
    """
    Render a segmented control (toggle button group).

    Falls back to radio buttons if segmented_control isn't available
    (for older Streamlit versions).
    """
    if hasattr(st, "segmented_control"):
        return st.segmented_control(
            " ",  # Empty label (hidden via CSS)
            options,
            selection_mode="single",
            key=key,
            default=default,
            label_visibility="collapsed",
        )
    return st.radio(
        " ",
        options,
        horizontal=True,
        key=key,
        index=options.index(default),
        label_visibility="collapsed",
    )


def render_filters() -> tuple[str, str]:
    """
    Render the filter controls and return selected values.

    Returns:
        Tuple of (selected_conference, selected_category)
    """
    conference_options = ["All MLS", "Eastern Conference", "Western Conference"]
    category_options = list(PHASE_CATEGORIES.keys())

    col_conference, col_category, col_toggle = st.columns(
        [3, 4, 3],
        vertical_alignment="center",
    )

    with col_conference:
        conference_choice = st.selectbox(
            "Conference",
            conference_options,
            index=0,
            label_visibility="collapsed",
        )

    with col_category:
        category_choice = st.selectbox(
            "Phase category",
            category_options,
            index=0,
            label_visibility="collapsed",
        )

    with col_toggle:
        render_toggle(["Values", "Percentiles"], key="view_mode", default="Values")

    return conference_choice, category_choice


def render_data_table(
    data: pd.DataFrame,
    columns_config: list[tuple[str, str, str, str]],
) -> None:
    """Render the main data table with AgGrid, using pinned columns and two-tier headers.

    Args:
        data: DataFrame to display
        columns_config: List of (phase_display, metric_display, raw_metric, raw_phase) tuples
                       for configuring number formatting and column grouping
    """
    if data.empty:
        st.info("No data matches the current filters.")
        return

    # Build columnDefs manually to support two-tier grouped headers
    column_defs = [
        create_logo_column_def(),
        create_team_column_def("team-divider"),
    ]

    # Group phase columns by phase name for two-tier headers
    from collections import OrderedDict
    phase_groups = OrderedDict()

    for phase_display, metric_display, metric, _ in columns_config:
        col_name = f"{phase_display} | {metric_display}"

        if phase_display not in phase_groups:
            phase_groups[phase_display] = []

        # Determine value formatter based on metric type
        if metric in ("success_rate", "percent_of_total"):
            # Percentage with 1 decimal and % symbol
            value_formatter = JsCode(
                "function(params) { return params.value != null ? params.value.toFixed(1) + '%' : '-'; }"
            )
        elif metric.endswith("_percentile"):
            # Integer for percentiles
            value_formatter = JsCode(
                "function(params) { return params.value != null ? Math.round(params.value).toString() : '-'; }"
            )
        elif metric == "count":
            # Decimal with 1 decimal place
            value_formatter = JsCode(
                "function(params) { return params.value != null ? params.value.toFixed(1) : '-'; }"
            )
        else:
            value_formatter = None

        # Add cellClass for the last metric (Share) to create divider between phase groups
        # All numeric columns get "numeric-cell" for right-align; Share also gets "phase-divider"
        if metric_display == "Share":
            cell_class = "numeric-cell phase-divider"
        else:
            cell_class = "numeric-cell"

        col_def = {
            "field": col_name,
            "headerName": metric_display,  # Just "Count", "Won", "Share"
            "width": 65,
            "minWidth": 60,
            "valueFormatter": value_formatter,
            "type": ["numericColumn"],
            "cellClass": cell_class,
            "sortable": True,
            "filter": False,
        }
        if metric_display == "Share":
            col_def["headerClass"] = "phase-divider-header"

        phase_groups[phase_display].append(col_def)

    # Add grouped columns to column_defs with alternating banding classes
    for i, (phase_name, children) in enumerate(phase_groups.items()):
        band_class = "phase-band-1" if i % 2 == 0 else "phase-band-2"
        # Apply the same band class to child columns so second row headers match
        for child in children:
            # Combine with existing headerClass if present (e.g., phase-divider-header for Share)
            existing_class = child.get("headerClass", "")
            child["headerClass"] = f"{band_class} {existing_class}".strip()
        column_defs.append({
            "headerName": phase_name,  # Parent header: "Buildup", "Progression", etc.
            "headerClass": band_class,  # Alternating background colors for visual banding
            "children": children,       # Child columns: Count, Won, Share
        })

    # JavaScript to highlight sorted column cells via DOM manipulation
    on_sort_changed = JsCode("""
        function(params) {
            const api = params.api;
            const gridBody = document.querySelector('.ag-body-viewport');
            if (!gridBody) return;

            // Remove previous highlights
            gridBody.querySelectorAll('.sorted-col-highlight').forEach(el => {
                el.classList.remove('sorted-col-highlight');
            });

            // Find currently sorted column
            const sortedCols = api.getColumnState().filter(c => c.sort);
            if (sortedCols.length === 0) return;

            const sortedColId = sortedCols[0].colId;

            // Add highlight class to all cells in that column
            gridBody.querySelectorAll(`[col-id="${sortedColId}"]`).forEach(cell => {
                cell.classList.add('sorted-col-highlight');
            });
        }
    """)

    # JavaScript to unpin Team column on mobile (<768px)
    on_grid_ready = get_mobile_unpin_callback(size_to_fit=False)

    # Build grid options with manual columnDefs
    grid_options = {
        "columnDefs": column_defs,
        "defaultColDef": {
            "sortable": True,
            "resizable": True,
        },
        "onSortChanged": on_sort_changed,
        "onFirstDataRendered": on_sort_changed,
        "onGridReady": on_grid_ready,
        "domLayout": "normal",
        "rowHeight": 36,
        "headerHeight": 32,
        "groupHeaderHeight": 32,
        "suppressMovableColumns": True,
        "enableRangeSelection": False,
        "suppressRowClickSelection": True,
    }

    # Custom CSS for dark theme
    custom_css = get_phases_table_css()

    AgGrid(
        data,
        gridOptions=grid_options,
        height=560,
        allow_unsafe_jscode=True,
        custom_css=custom_css,
        theme="balham-dark",
    )


def render_team_styles_table(data: pd.DataFrame, show_percentiles: bool = False) -> None:
    """Render the team styles table with AgGrid.

    Args:
        data: DataFrame with Logo, Team, and style percentage columns
        show_percentiles: If True, format values as integers (percentile rank)
    """
    if data.empty:
        st.info("No data matches the current filters.")
        return

    # Build columnDefs manually to support two-tier grouped headers
    column_defs = [
        create_logo_column_def(),
        create_team_column_def("team-cell team-divider"),
    ]

    # Season Style column - wrapped in a group for consistent two-tier header structure
    column_defs.append({
        "headerName": "Season Style",
        "headerClass": "team-style-header",
        "children": [{
            "field": "Team Style",
            "headerName": "",
            "width": 170,
            "minWidth": 150,
            "sortable": True,
            "filter": False,
            "suppressMenu": True,
            "cellClass": "team-style-cell team-divider",
            "headerClass": "team-style-header team-divider-header",
            "wrapText": True,
            "autoHeight": True,
        }],
    })

    # Formatter based on mode
    if show_percentiles:
        # Integer for percentiles
        value_formatter = JsCode(
            "function(params) { return params.value != null ? Math.round(params.value).toString() : '-'; }"
        )
    else:
        # Percentage rounded to whole number
        value_formatter = JsCode(
            "function(params) { return params.value != null ? Math.round(params.value) + '%' : '-'; }"
        )

    # cellClassRules to highlight sorted column (works with virtualization)
    sorted_highlight_rule = JsCode("""
        function(params) {
            if (!params.api) return false;
            const sortedCols = params.api.getColumnState().filter(c => c.sort);
            if (sortedCols.length === 0) return false;
            return sortedCols[0].colId === params.colDef.field;
        }
    """)

    # Build style column children for the "Match-Level Styles" group
    style_children = []
    for i, col in enumerate(STYLE_COLUMNS):
        is_last = (i == len(STYLE_COLUMNS) - 1)
        # Alternate banding between columns
        band_class = "phase-band-1" if i % 2 == 0 else "phase-band-2"
        base_class = "numeric-cell phase-divider" if is_last else "numeric-cell"
        col_def = {
            "field": col,
            "headerName": col,
            "minWidth": 100,
            "flex": 1,  # All columns get equal flex width
            "valueFormatter": value_formatter,
            "type": ["numericColumn"],
            "cellClass": base_class,
            "cellClassRules": {
                "sorted-col-highlight": sorted_highlight_rule,
            },
            "sortable": True,
            "filter": False,
            "headerClass": f"{band_class} style-header-wrap" + (" phase-divider-header" if is_last else ""),
            "wrapHeaderText": True,
            "autoHeaderHeight": True,
        }
        style_children.append(col_def)

    # Add "Match Styles" column group
    column_defs.append({
        "headerName": "Match Styles",
        "headerClass": "phase-band-1",
        "children": style_children,
    })

    # Refresh cells on sort change to re-evaluate cellClassRules
    on_sort_changed = JsCode("""
        function(params) {
            params.api.refreshCells({ force: true });
        }
    """)

    # JavaScript to unpin Team column on mobile (<768px) and size columns to fit
    on_grid_ready = get_mobile_unpin_callback(size_to_fit=True)

    # Build grid options
    grid_options = {
        "columnDefs": column_defs,
        "defaultColDef": {
            "sortable": True,
            "resizable": True,
            "wrapHeaderText": True,
            "autoHeaderHeight": True,
        },
        "onSortChanged": on_sort_changed,
        "onFirstDataRendered": on_sort_changed,
        "onGridReady": on_grid_ready,
        "domLayout": "normal",
        "rowHeight": 36,
        "headerHeight": 50,
        "groupHeaderHeight": 32,
        "suppressMovableColumns": True,
        "enableRangeSelection": False,
        "suppressRowClickSelection": True,
        "suppressColumnVirtualisation": True,
    }

    # Custom CSS for dark theme
    custom_css = get_team_styles_table_css()

    AgGrid(
        data,
        gridOptions=grid_options,
        height=560,
        allow_unsafe_jscode=True,
        custom_css=custom_css,
        theme="balham-dark",
    )


def render_team_tendencies_table(data: pd.DataFrame, show_percentiles: bool = False) -> None:
    """Render the team tendencies table with AgGrid.

    Args:
        data: DataFrame with Logo, Team, and tendencies columns
        show_percentiles: If True, format values as integers (percentile rank)
    """
    if data.empty:
        st.info("No data matches the current filters.")
        return

    # Build columnDefs manually
    column_defs = [
        create_logo_column_def(),
        create_team_column_def("team-cell team-divider"),
    ]

    # Formatter - always integers for tendencies
    value_formatter = JsCode(
        "function(params) { return params.value != null ? Math.round(params.value).toString() : '-'; }"
    )

    # cellClassRules to highlight sorted column
    sorted_highlight_rule = JsCode("""
        function(params) {
            if (!params.api) return false;
            const sortedCols = params.api.getColumnState().filter(c => c.sort);
            if (sortedCols.length === 0) return false;
            return sortedCols[0].colId === params.colDef.field;
        }
    """)

    # Build tendencies column children for the "Tendencies" group
    tendencies_children = []
    display_names = list(TENDENCIES_DISPLAY_NAMES.values())
    for i, col in enumerate(display_names):
        is_last = (i == len(display_names) - 1)
        # Alternate banding between columns
        band_class = "phase-band-1" if i % 2 == 0 else "phase-band-2"
        base_class = "numeric-cell phase-divider" if is_last else "numeric-cell"
        col_def = {
            "field": col,
            "headerName": col,
            "minWidth": 100,
            "flex": 1,  # All columns get equal flex width
            "valueFormatter": value_formatter,
            "type": ["numericColumn"],
            "cellClass": base_class,
            "cellClassRules": {
                "sorted-col-highlight": sorted_highlight_rule,
            },
            "sortable": True,
            "filter": False,
            "headerClass": f"{band_class} style-header-wrap" + (" phase-divider-header" if is_last else ""),
            "wrapHeaderText": True,
            "autoHeaderHeight": True,
        }
        tendencies_children.append(col_def)

    # Add "Tendencies" column group
    column_defs.append({
        "headerName": "Tendencies",
        "headerClass": "phase-band-1",
        "children": tendencies_children,
    })

    # Refresh cells on sort change to re-evaluate cellClassRules
    on_sort_changed = JsCode("""
        function(params) {
            params.api.refreshCells({ force: true });
        }
    """)

    # JavaScript to unpin Team column on mobile (<768px) and size columns to fit
    on_grid_ready = get_mobile_unpin_callback(size_to_fit=True)

    # Build grid options
    grid_options = {
        "columnDefs": column_defs,
        "defaultColDef": {
            "sortable": True,
            "resizable": True,
            "wrapHeaderText": True,
            "autoHeaderHeight": True,
        },
        "onSortChanged": on_sort_changed,
        "onFirstDataRendered": on_sort_changed,
        "onGridReady": on_grid_ready,
        "domLayout": "normal",
        "rowHeight": 36,
        "headerHeight": 50,
        "groupHeaderHeight": 32,
        "suppressMovableColumns": True,
        "enableRangeSelection": False,
        "suppressRowClickSelection": True,
        "suppressColumnVirtualisation": True,
    }

    # Custom CSS for dark theme
    custom_css = get_team_styles_table_css()

    AgGrid(
        data,
        gridOptions=grid_options,
        height=560,
        allow_unsafe_jscode=True,
        custom_css=custom_css,
        theme="balham-dark",
    )


# =============================================================================
# STYLES (CSS)
# =============================================================================


def inject_styles() -> None:
    """Inject custom CSS for the futi dark theme."""
    st.markdown(
        f"""
        <style>
        /* === Typography === */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

        html, body, [class*="css"], [class*="st-"] {{
            font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
        }}

        /* Restore Material Symbols font for Streamlit icon elements.
           The stIconMaterial spans contain icon names as text that render as icons via ligatures.
           Our global font-family override breaks this, so we must restore the icon font. */
        [data-testid="stIconMaterial"] {{
            font-family: 'Material Symbols Rounded', sans-serif !important;
        }}

        /* === Layout === */
        :root {{
            --control-height: 44px;
            --control-radius: 999px;
        }}

        .block-container {{
            padding-top: 1rem;
            padding-bottom: 3rem;
            max-width: 72rem;
        }}

        /* === Background gradient === */
        .stApp {{
            background: radial-gradient(circle at top, {COLORS['dark1']}, {COLORS['dark']});
        }}

        .stApp:before {{
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            opacity: 0.80;
            background:
                radial-gradient(circle at top left, rgba(234,31,150,0.16), transparent 55%),
                radial-gradient(circle at center, rgba(106,98,248,0.18), transparent 60%),
                radial-gradient(circle at bottom right, rgba(0,183,255,0.20), transparent 60%),
                radial-gradient(circle at top right, rgba(15,230,180,0.22), transparent 65%);
            z-index: 0;
        }}

        .block-container, header, footer {{
            position: relative;
            z-index: 1;
        }}

        header[data-testid="stHeader"] {{
            background: transparent;
        }}

        /* === Beta badge === */
        .futi-beta {{
            display: inline-flex;
            align-items: center;
            gap: .5rem;
            border-radius: 999px;
            border: 1px solid rgba(15,230,180,0.70);
            background: rgba(3,21,30,0.80);
            padding: .25rem 1rem;
            font-size: .70rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: .18em;
            color: {COLORS['green']};
        }}

        .futi-dot {{
            width: .375rem;
            height: .375rem;
            border-radius: 999px;
            background: {COLORS['green']};
        }}

        /* === Cards (containers with border) === */
        div[data-testid="stContainer"] {{
            border-radius: 1.25rem !important;
            border: 1px solid rgba(255,255,255,0.10) !important;
            background: rgba(3,21,30,0.55) !important;
            backdrop-filter: blur(10px);
            padding: 0.75rem 1.0rem;
        }}

        /* === Form controls === */
        .stMarkdown, .stMarkdown > div {{
            margin: 0 !important;
            padding: 0 !important;
        }}
        .stMarkdown p {{
            margin: 0 !important;
        }}

        div[data-testid="stSelectbox"],
        [data-testid="stSegmentedControl"],
        div[data-testid="stRadio"] {{
            margin: 0 !important;
            padding: 0 !important;
        }}

        /* Dropdown styling */
        div[data-testid="stSelectbox"] div[role="combobox"] {{
            height: var(--control-height) !important;
            min-height: var(--control-height) !important;
            border-radius: var(--control-radius) !important;
            background: {COLORS['dark']} !important;
            border: 1px solid rgba(255,255,255,0.10) !important;
            color: rgba(255,255,255,0.92) !important;
            display: flex !important;
            align-items: center !important;
            padding: 0 14px !important;
            box-sizing: border-box !important;
        }}

        /* Toggle (segmented control) styling */
        [data-testid="stSegmentedControl"] {{
            height: var(--control-height) !important;
            min-height: var(--control-height) !important;
            max-height: var(--control-height) !important;
            border-radius: var(--control-radius) !important;
            border: 1px solid rgba(255,255,255,0.10) !important;
            background: rgba(6,34,48,0.70) !important;
            padding: 0 !important;
            box-sizing: border-box !important;
            overflow: visible !important;
            display: inline-flex !important;
            align-items: center !important;
            width: max-content !important;
            min-width: max-content !important;
            flex-wrap: nowrap !important;
            flex-shrink: 0 !important;
        }}

        [data-testid="stSegmentedControl"] [data-baseweb="button-group"],
        [data-testid="stSegmentedControl"] [data-baseweb="button-group"] > div {{
            display: inline-flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            height: var(--control-height) !important;
            width: auto !important;
        }}

        [data-testid="stSegmentedControl"] button {{
            height: var(--control-height) !important;
            min-height: var(--control-height) !important;
            line-height: var(--control-height) !important;
            margin: 0 !important;
            padding: 0 18px !important;
            border-radius: 0 !important;
            white-space: nowrap !important;
            flex: 0 0 auto !important;
            font-size: 0.875rem !important;
            font-weight: 500 !important;
            background: transparent !important;
            border: none !important;
            color: rgba(255,255,255,0.7) !important;
        }}

        /* Active button: solid green fill with dark text, no green border */
        [data-testid="stSegmentedControl"] button[aria-checked="true"],
        [data-testid="stSegmentedControl"] button[aria-selected="true"],
        [data-testid="stSegmentedControl"] button[data-selected="true"],
        [data-testid="stSegmentedControl"] button.selected,
        [data-testid="stSegmentedControl"] button[data-baseweb="tab"][aria-selected="true"] {{
            background: {COLORS['green']} !important;
            color: {COLORS['dark']} !important;
            border: none !important;
            outline: none !important;
            box-shadow: none !important;
            border-radius: var(--control-radius) !important;
        }}

        /* Remove any green styling from the container when active */
        [data-testid="stSegmentedControl"],
        [data-testid="stSegmentedControl"] * {{
            outline: none !important;
            box-shadow: none !important;
        }}

        [data-testid="stSegmentedControl"]:focus-within {{
            border-color: rgba(255,255,255,0.10) !important;
        }}

        /* Hide control labels (we use placeholders instead) */
        [data-testid="stSegmentedControl"] label,
        div[data-testid="stRadio"] > label {{
            display: none !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }}

        /* === AgGrid container styling === */
        /* The AgGrid component styles are applied via custom_css parameter in render_data_table() */

        /* === Navigation tabs === */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 8px;
            background: transparent;
            border-bottom: none;
            padding-bottom: 0;
            margin-bottom: -1rem;
            margin-left: 1.25rem;
        }}

        .stTabs [data-baseweb="tab"] {{
            height: 40px;
            padding: 0 20px;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-bottom: none;
            border-radius: 8px 8px 0 0;
            color: rgba(255,255,255,0.5);
            font-weight: 500;
            font-size: 0.95rem;
        }}

        .stTabs [data-baseweb="tab"]:hover {{
            color: rgba(255,255,255,0.8);
            background: rgba(255,255,255,0.06);
            border-color: rgba(255,255,255,0.12);
        }}

        .stTabs [aria-selected="true"] {{
            background: {COLORS['dark2']} !important;
            color: {COLORS['green']} !important;
            border: 1px solid rgba(255,255,255,0.15) !important;
            border-bottom: 2px solid {COLORS['green']} !important;
        }}

        .stTabs [data-baseweb="tab-highlight"] {{
            display: none;
        }}

        .stTabs [data-baseweb="tab-border"] {{
            display: none;
        }}

        </style>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# MAIN APPLICATION
# =============================================================================


def render_phases_tab() -> None:
    """Render the Phases tab content."""
    # Load data
    data_path = Path(__file__).resolve().parent / "phases.csv"
    if not data_path.exists():
        st.error("Missing phases.csv in the app directory")
        st.stop()

    df = load_data(str(data_path), get_file_mtime(data_path))
    df["team_name"] = df["team_name"].astype(str)
    df["phase"] = df["phase"].astype(str)

    # Single container for filters + table
    with st.container(border=True):
        conference_choice, category_choice = render_filters()

        # Apply filters
        filtered_df = filter_by_conference(df, conference_choice)

        phases_to_show = PHASE_CATEGORIES[category_choice]
        show_percentiles = st.session_state.get("view_mode", "Values") == "Percentiles"

        # Transform and display
        table_data, columns_config = create_wide_table(filtered_df, phases_to_show, show_percentiles)

        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

        render_data_table(table_data, columns_config)

        render_csv_download(table_data, "futi_phases.csv")


def render_team_styles_tab() -> None:
    """Render the Team Styles tab content."""
    data_path = Path(__file__).resolve().parent / "team_styles.csv"
    if not data_path.exists():
        st.error("Missing team_styles.csv in the app directory")
        st.stop()

    df = load_data(str(data_path), get_file_mtime(data_path))

    with st.container(border=True):
        # Conference filter and Values/Percentiles toggle
        conference_options = ["All MLS", "Eastern Conference", "Western Conference"]

        col_conference, col_toggle = st.columns([3, 3], vertical_alignment="center")

        with col_conference:
            conference_choice = st.selectbox(
                "Conference",
                conference_options,
                index=0,
                label_visibility="collapsed",
                key="styles_conference",
            )

        with col_toggle:
            render_toggle(["Values", "Percentiles"], key="styles_view_mode", default="Values")

        # Filter by conference
        filtered_df = filter_by_conference(df, conference_choice)

        # Prepare and display table
        show_percentiles = st.session_state.get("styles_view_mode", "Values") == "Percentiles"
        table_data = prepare_team_styles_data(filtered_df, show_percentiles)

        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

        render_team_styles_table(table_data, show_percentiles)

        render_csv_download(table_data, "futi_team_styles.csv")


def render_team_tendencies_tab() -> None:
    """Render the Team Tendencies tab content."""
    data_path = Path(__file__).resolve().parent / "team_styles.csv"
    if not data_path.exists():
        st.error("Missing team_styles.csv in the app directory")
        st.stop()

    df = load_data(str(data_path), get_file_mtime(data_path))

    with st.container(border=True):
        # Conference filter and Values/Percentiles toggle
        conference_options = ["All MLS", "Eastern Conference", "Western Conference"]

        col_conference, col_toggle = st.columns([3, 3], vertical_alignment="center")

        with col_conference:
            conference_choice = st.selectbox(
                "Conference",
                conference_options,
                index=0,
                label_visibility="collapsed",
                key="tendencies_conference",
            )

        with col_toggle:
            render_toggle(["Values", "Percentiles"], key="tendencies_view_mode", default="Values")

        # Filter by conference
        filtered_df = filter_by_conference(df, conference_choice)

        # Prepare and display table
        show_percentiles = st.session_state.get("tendencies_view_mode", "Values") == "Percentiles"
        table_data = prepare_team_tendencies_data(filtered_df, show_percentiles)

        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

        render_team_tendencies_table(table_data, show_percentiles)

        render_csv_download(table_data, "futi_team_tendencies.csv")


# def render_team_stats_tab() -> None:
#     """Render the Team Stats tab content (placeholder)."""
#     with st.container(border=True):
#         st.info("Team Stats coming soon.")


# def render_player_stats_tab() -> None:
#     """Render the Player Stats tab content (placeholder)."""
#     with st.container(border=True):
#         st.info("Player Stats coming soon.")


def main() -> None:
    """Main application entry point."""
    # Page setup
    st.set_page_config(
        page_title="futi",
        page_icon="futi_logo.png",
        layout="wide",
    )
    inject_styles()

    # Header
    render_header()
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Main navigation tabs
    tab_phases, tab_styles, tab_tendencies = st.tabs(["Phases", "Team Styles", "Team Tendencies"])

    with tab_phases:
        render_phases_tab()

    with tab_styles:
        render_team_styles_tab()

    with tab_tendencies:
        render_team_tendencies_tab()


if __name__ == "__main__":
    main()
