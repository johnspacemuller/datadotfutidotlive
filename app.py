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
) -> pd.DataFrame:
    """
    Transform long-format data into a wide table for display.

    Creates a table where:
    - Rows are teams (sorted alphabetically)
    - Columns are grouped by phase, with sub-columns for each metric
    - Values are formatted appropriately (percentages, decimals, etc.)

    Args:
        df: Source data with columns: team_name, phase, and metric columns
        phases: List of phases to include (in display order)
        show_percentiles: If True, show percentile rankings; if False, show raw values

    Returns:
        A styled DataFrame ready for display, or empty DataFrame if no data
    """
    metrics = PERCENTILE_METRICS if show_percentiles else VALUE_METRICS

    # Filter to only the phases we want
    df_filtered = df[df["phase"].isin(phases)]
    if df_filtered.empty:
        return pd.DataFrame()

    # Pivot: rows=teams, columns=(metric, phase)
    pivoted = df_filtered.pivot(index="team_name", columns="phase", values=metrics)

    # Build columns in the desired order: Phase1/Count, Phase1/Won, Phase1/Share, Phase2/Count, ...
    columns_config = []  # List of (display_phase, display_metric, raw_metric, raw_phase)
    for phase in phases:
        phase_display = format_phase_name(phase)
        for metric in metrics:
            metric_display = METRIC_DISPLAY_NAMES[metric]
            columns_config.append((phase_display, metric_display, metric, phase))

    # Extract and transform each column
    result_data = {}
    for phase_display, metric_display, metric, phase in columns_config:
        try:
            col = pivoted[(metric, phase)]
        except KeyError:
            # Phase might not exist for all teams
            col = pd.Series([None] * len(pivoted), index=pivoted.index)

        # Transform values for display
        if metric == "count":
            # Convert total count to per-game average
            col = (col / GAMES_PLAYED).round(1)
        elif metric in ("success_rate", "percent_of_total") or metric.endswith("_percentile"):
            # Convert decimals to percentages (0.65 -> 65)
            col = col * 100

        result_data[(phase_display, metric_display)] = col

    # Assemble final DataFrame with MultiIndex columns
    result = pd.DataFrame(result_data)
    result.columns = pd.MultiIndex.from_tuples(result.columns)
    result.index.name = "Team"
    result = result.sort_index()

    # Apply display formatting
    def fmt_percent(x):
        return "-" if pd.isna(x) else f"{x:.1f}%"

    def fmt_integer(x):
        return "-" if pd.isna(x) else f"{int(x)}"

    def fmt_decimal(x):
        return "-" if pd.isna(x) else f"{x:.1f}"

    format_dict = {}
    for phase_display, metric_display, metric, _ in columns_config:
        key = (phase_display, metric_display)
        if metric in ("success_rate", "percent_of_total"):
            format_dict[key] = fmt_percent
        elif metric.endswith("_percentile"):
            format_dict[key] = fmt_integer
        elif metric == "count":
            format_dict[key] = fmt_decimal

    return result.style.format(format_dict, na_rep="-")


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


def render_filters(teams: list[str]) -> tuple[str, str]:
    """
    Render the filter controls and return selected values.

    Returns:
        Tuple of (selected_team, selected_category)
    """
    team_options = ["All teams"] + teams
    category_options = list(PHASE_CATEGORIES.keys())

    col_team, col_category, col_toggle = st.columns(
        [3, 4, 3],
        vertical_alignment="center",
    )

    with col_team:
        team_choice = st.selectbox(
            "Team",
            team_options,
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
        # Right-align the toggle
        st.markdown(
            "<div style='display:flex; justify-content:flex-end;'>",
            unsafe_allow_html=True,
        )
        render_toggle(["Values", "Percentiles"], key="view_mode", default="Values")
        st.markdown("</div>", unsafe_allow_html=True)

    return team_choice, category_choice


def render_data_table(data) -> None:
    """Render the main data table, or a message if empty."""
    # Handle both DataFrame and Styler objects
    is_empty = data.empty if isinstance(data, pd.DataFrame) else data.data.empty

    if is_empty:
        st.info("No data matches the current filters.")
    else:
        st.dataframe(data, use_container_width=True, height=560)


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

        /* === Data table === */
        div[data-testid="stDataFrame"] [role="columnheader"] {{
            background: {COLORS['dark2']} !important;
            color: rgba(255,255,255,0.70) !important;
        }}

        div[data-testid="stDataFrame"] [role="gridcell"],
        div[data-testid="stDataFrame"] [role="columnheader"] {{
            min-width: 85px !important;
        }}

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
            background: transparent;
            border: none;
            border-radius: 8px 8px 0 0;
            color: rgba(255,255,255,0.6);
            font-weight: 500;
            font-size: 0.95rem;
        }}

        .stTabs [data-baseweb="tab"]:hover {{
            color: rgba(255,255,255,0.85);
            background: rgba(255,255,255,0.05);
        }}

        .stTabs [aria-selected="true"] {{
            background: {COLORS['dark2']} !important;
            color: {COLORS['green']} !important;
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

    # Filter controls
    teams = sorted(df["team_name"].unique().tolist())

    # Single container for filters + table
    with st.container(border=True):
        team_choice, category_choice = render_filters(teams)

        # Apply filters
        filtered_df = df.copy()
        if team_choice != "All teams":
            filtered_df = filtered_df[filtered_df["team_name"] == team_choice]

        phases_to_show = PHASE_CATEGORIES[category_choice]
        show_percentiles = st.session_state.get("view_mode", "Values") == "Percentiles"

        # Transform and display
        table_data = create_wide_table(filtered_df, phases_to_show, show_percentiles)

        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

        render_data_table(table_data)


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

    # Main navigation tabs (Team Stats and Player Stats commented out for now)
    # tab_phases, tab_team_stats, tab_player_stats = st.tabs([
    #     "Phases",
    #     "Team Stats",
    #     "Player Stats",
    # ])
    tab_phases, = st.tabs(["Phases"])

    with tab_phases:
        render_phases_tab()

    # with tab_team_stats:
    #     render_team_stats_tab()

    # with tab_player_stats:
    #     render_player_stats_tab()


if __name__ == "__main__":
    main()
