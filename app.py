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
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
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
# PLAYER RATINGS DEFINITIONS
# =============================================================================

RATINGS_COLUMNS = [
    "overall_rating",
    "shooting_rating",
    "dribbling_rating",
    "receptions_rating",
    "creation_rating",
    "linkup_rating",
    "ballwinning_rating",
]

RATINGS_DISPLAY_NAMES = {
    "overall_rating": "Overall",
    "shooting_rating": "Shooting",
    "dribbling_rating": "Dribbling",
    "receptions_rating": "Receptions",
    "creation_rating": "Creation",
    "linkup_rating": "Linkup",
    "ballwinning_rating": "Ball Winning",
}

# Mapping from display name to the _aa (values) column in the CSV
RATINGS_VALUES_COLUMNS = {
    "Overall": "vaep_p90_aa",
    "Shooting": "shooting_aa",
    "Dribbling": "dribbling_aa",
    "Receptions": "receptions_aa",
    "Creation": "creation_aa",
    "Linkup": "linkup_aa",
    "Ball Winning": "ballwinning_aa",
}

ROLE_DISPLAY_NAMES = {
    "All": "All Positions",
    "CB": "Center Back",
    "FB": "Full Back",
    "MF": "Midfielder",
    "W": "Winger",
    "ST": "Striker",
}

# =============================================================================
# TEAM TENDENCIES DEFINITIONS
# =============================================================================

TENDENCIES_COLUMNS = [
    "building_patient",
    "build_wide",
    "progression_patient",
    "attack_central",
    "hightempo",
    "counterpress",
    "highpress",
    "chaos",
]

TENDENCIES_DISPLAY_NAMES = {
    "building_patient": "Patient Buildup",
    "build_wide": "Central Buildup",
    "progression_patient": "Patient Progression",
    "attack_central": "Central Attack",
    "hightempo": "Direct Transitions",
    "counterpress": "Counterpress",
    "highpress": "High Press",
    "chaos": "Chaos",
}

# =============================================================================
# EXPECTED GOALS DEFINITIONS
# =============================================================================

XG_COLUMNS = ["shots", "sot", "xg", "npxg"]
XG_AGAINST_COLUMNS = ["shots_against", "sot_against", "xg_against", "npxg_against"]
XG_SUMMARY_COLUMNS = ["xpoints", "xgd", "npxgd"]

XG_DISPLAY_NAMES = {
    "shots": "Shots",
    "sot": "SOT",
    "xg": "xG",
    "npxg": "npxG",
    "shots_against": "Shots",
    "sot_against": "SOT",
    "xg_against": "xGA",
    "npxg_against": "npxGA",
    "xpoints": "xPts",
    "xgd": "xGD",
    "npxgd": "npxGD",
}

RATING_COLUMNS = ["overall_pct", "attack_pct", "defense_pct"]
RATING_DISPLAY_NAMES = {
    "overall_pct": "Overall",
    "attack_pct": "Attack",
    "defense_pct": "Defense",
}

# Team hex colors adjusted for visibility on dark backgrounds
TEAM_COLORS = {
    "Atlanta United": "#80000A",
    "Austin FC": "#00B140",
    "CF Montreal": "#0033A1",
    "Charlotte": "#1A85C8",
    "Chicago Fire": "#FF0000",
    "Cincinnati": "#FC4C02",
    "Colorado Rapids": "#862633",
    "Columbus Crew": "#FEDD00",
    "DC United": "#EF3E42",
    "FC Dallas": "#E81F3E",
    "Houston Dynamo": "#F68712",
    "Inter Miami": "#F7B5CD",
    "LA Galaxy": "#FFD200",
    "LAFC": "#C39E6D",
    "Minnesota United": "#9BCEE2",
    "Nashville SC": "#ECE83A",
    "New England Revolution": "#C63323",
    "New York City FC": "#6CACE4",
    "New York Red Bulls": "#ED1E36",
    "Orlando City": "#633492",
    "Philadelphia Union": "#B1872D",
    "Portland Timbers": "#00482B",
    "Real Salt Lake": "#B30838",
    "San Diego FC": "#00685E",
    "San Jose Earthquakes": "#0067B1",
    "Seattle Sounders": "#5D9741",
    "Sporting Kansas City": "#93B1D7",
    "St. Louis City": "#D62F43",
    "Toronto FC": "#E31937",
    "Vancouver Whitecaps": "#5E87A0",
}

# Rating type colors for single-team view
RATING_TYPE_COLORS = {
    "Overall": COLORS["green"],
    "Attack": COLORS["pink"],
    "Defense": COLORS["blue"],
}

# Maps display names to CSV column names for rating types
RATING_TYPE_COLUMNS = {
    "Overall": "overall_pct",
    "Attack": "attack_pct",
    "Defense": "defense_pct",
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
        # Season Style header - dark background matching pinned area
        ".team-style-header": {
            "background-color": f"{COLORS['dark1']} !important",
            "display": "flex !important",
            "align-items": "center !important",
            "justify-content": "center !important",
            "color": "rgba(255,255,255,0.9) !important",
            "font-weight": "700 !important",
            "font-size": "0.9rem !important",
            "text-transform": "none !important",
        },
        # Dark subheader for Season Style (empty second-tier row)
        ".styles-dark-subheader": {
            "background-color": f"{COLORS['dark1']} !important",
            "border-bottom": "none !important",
        },
        # Remove horizontal line between first and second level headers
        ".no-subheader-border": {
            "border-bottom": "none !important",
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


def get_player_ratings_table_css() -> dict:
    """CSS for player ratings table (player-level data, no logo column)."""
    base = get_base_aggrid_css()
    ratings_specific = {
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
        # Second tier headers
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
        # Group header
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
        # Player column - left-aligned text (mirrors Team column behavior)
        ".ag-cell[col-id='Player']": {
            "justify-content": "flex-start !important",
            "padding-left": "12px !important",
            "border-right": "1px solid rgba(255,255,255,0.15) !important",
        },
        ".ag-header-cell[col-id='Player']": {
            "background-color": f"{COLORS['dark1']} !important",
            "border-right": "1px solid rgba(255,255,255,0.15) !important",
        },
        # Pinned left group header row - keep dark
        ".ag-pinned-left-header .ag-header-group-cell": {
            "background-color": f"{COLORS['dark1']} !important",
            "border-right": "none !important",
        },
        ".ag-header-cell[col-id='Logo']": {
            "background-color": f"{COLORS['dark1']} !important",
            "border-right": "none !important",
        },
        # Overall rating column - bold green in Ratings mode
        ".overall-rating-cell": {
            "font-weight": "700 !important",
            "color": f"{COLORS['green']} !important",
        },
        # Overall subheader - green background with dark text
        ".overall-header": {
            "background-color": f"{COLORS['green']} !important",
            "color": f"{COLORS['dark']} !important",
        },
        ".overall-header .ag-header-cell-label": {
            "color": f"{COLORS['dark']} !important",
        },
        # Dark subheader for Role/Minutes (empty second-tier row)
        ".ratings-dark-subheader": {
            "background-color": f"{COLORS['dark1']} !important",
            "border-bottom": "none !important",
        },
        # Remove horizontal line between first and second level headers
        ".no-subheader-border": {
            "border-bottom": "none !important",
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
    return {**base, **ratings_specific}


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


def prepare_team_xg_data(df: pd.DataFrame, per_game: bool = False) -> pd.DataFrame:
    """
    Prepare expected goals data for display with logos.

    Args:
        df: Source data with team_name and xG columns
        per_game: If True, divide all values by GAMES_PLAYED

    Returns:
        DataFrame with Logo, Team, and renamed xG columns
    """
    result = pd.DataFrame()
    result["Logo"] = df["team_name"].apply(get_team_logo_base64)
    result["Team"] = df["team_name"]

    # Merge latest team ratings
    ratings_path = Path(__file__).resolve().parent / "team_ratings.csv"
    if ratings_path.exists():
        ratings_df = pd.read_csv(str(ratings_path))
        ratings_df["rating_date"] = pd.to_datetime(ratings_df["rating_date"])
        latest_ratings = ratings_df.loc[ratings_df.groupby("team_name")["rating_date"].idxmax()]
        df = df.merge(latest_ratings[["team_name"] + RATING_COLUMNS], on="team_name", how="left")
        for col in RATING_COLUMNS:
            field = f"Rating | {RATING_DISPLAY_NAMES[col]}"
            result[field] = df[col].astype("Int64")

    result["Pts"] = df["points"].astype(int)

    decimals = 2 if per_game else 1
    divisor = GAMES_PLAYED if per_game else 1
    int_cols = {"shots", "sot", "shots_against", "sot_against"}

    all_cols = XG_SUMMARY_COLUMNS + XG_COLUMNS + XG_AGAINST_COLUMNS
    for col in all_cols:
        display_name = XG_DISPLAY_NAMES[col]
        # Prefix with group to avoid duplicate column names
        if col in XG_AGAINST_COLUMNS:
            field = f"Defense | {display_name}"
        elif col in XG_SUMMARY_COLUMNS:
            field = f"Total | {display_name}"
        else:
            field = f"Attack | {display_name}"
        val = df[col] / divisor
        if col in int_cols and not per_game:
            result[field] = val.round(0).astype(int)
        else:
            result[field] = val.round(decimals)

    return result.sort_values("Team").reset_index(drop=True)


def prepare_player_ratings_data(df: pd.DataFrame, show_values: bool = False) -> pd.DataFrame:
    """
    Prepare player ratings data for display.

    Args:
        df: Source data with player_name, team_name, role, minutes_played, and rating columns
        show_values: If True, show _aa per-90 values instead of ratings

    Returns:
        DataFrame with Logo, Player, Role, Minutes, and rating columns ready for AgGrid
    """
    result = pd.DataFrame()
    result["Logo"] = df["team_name"].apply(
        lambda x: get_team_logo_base64(x) if pd.notna(x) else ""
    )
    result["Player"] = df["player_name"]
    result["Role"] = df["role"]
    result["Minutes"] = df["minutes_played"].astype(int)

    if show_values:
        for display_name, aa_col in RATINGS_VALUES_COLUMNS.items():
            result[display_name] = df[aa_col].astype(float).round(2)
    else:
        for col in RATINGS_COLUMNS:
            display_name = RATINGS_DISPLAY_NAMES[col]
            result[display_name] = df[col].astype(float).round(0).astype(int)

    return result.sort_values("Overall", ascending=False).reset_index(drop=True)


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


def render_filters() -> tuple[str, str, str]:
    """
    Render the filter controls and return selected values.

    Returns:
        Tuple of (selected_conference, selected_category, selected_data_type)
    """
    conference_options = ["All MLS", "Eastern Conference", "Western Conference"]
    category_options = list(PHASE_CATEGORIES.keys())

    col_conference, col_category, col_data_type, col_toggle = st.columns(
        [3, 4, 2, 3],
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

    with col_data_type:
        render_toggle(["For", "Against"], key="phases_data_type", default="For")

    with col_toggle:
        render_toggle(["Values", "Percentiles"], key="view_mode", default="Values")

    data_type = st.session_state.get("phases_data_type", "For")
    return conference_choice, category_choice, data_type


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
            "sortingOrder": ["desc", "asc", None],
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
        "headerClass": "team-style-header no-subheader-border phase-divider-header",
        "children": [{
            "field": "Team Style",
            "headerName": "",
            "width": 170,
            "minWidth": 150,
            "sortable": True,
            "filter": False,
            "suppressMenu": True,
            "cellClass": "team-style-cell team-divider",
            "headerClass": "styles-dark-subheader team-divider-header",
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
            "sortingOrder": ["desc", "asc", None],
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
            "width": 122,
            "minWidth": 100,
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

    # JavaScript to unpin Team column on mobile (<768px) - no auto-fit
    on_grid_ready = get_mobile_unpin_callback(size_to_fit=False)

    # Build grid options
    grid_options = {
        "columnDefs": column_defs,
        "defaultColDef": {
            "sortable": True,
            "sortingOrder": ["desc", "asc", None],
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


def render_team_xg_table(data: pd.DataFrame, per_game: bool = False) -> None:
    """Render the expected goals table with AgGrid.

    Args:
        data: DataFrame with Logo, Team, and xG columns (prefixed with group names)
        per_game: If True, format with 2 decimal places; otherwise 1
    """
    if data.empty:
        st.info("No data matches the current filters.")
        return

    column_defs = [
        create_logo_column_def(),
        create_team_column_def("team-cell team-divider"),
    ]

    # cellClassRules to highlight sorted column
    sorted_highlight_rule = JsCode("""
        function(params) {
            if (!params.api) return false;
            const sortedCols = params.api.getColumnState().filter(c => c.sort);
            if (sortedCols.length === 0) return false;
            return sortedCols[0].colId === params.colDef.field;
        }
    """)

    decimals = 2 if per_game else 1
    decimal_formatter = JsCode(
        f"function(params) {{ return params.value != null ? params.value.toFixed({decimals}) : '-'; }}"
    )
    int_formatter = JsCode(
        "function(params) { return params.value != null ? Math.round(params.value).toString() : '-'; }"
    )
    int_fields = {"Shots", "SOT"}

    # Build Rating group (Overall, Attack, Defense)
    rating_fields = [f"Rating | {RATING_DISPLAY_NAMES[c]}" for c in RATING_COLUMNS]
    if all(f in data.columns for f in rating_fields):
        rating_overall_style = JsCode(
            "function(params) { return params.value != null ? params.value.toString() : '-'; }"
        )
        rating_children = []
        for i, field in enumerate(rating_fields):
            display_name = field.split(" | ")[1]
            is_last = (i == len(rating_fields) - 1)
            band_class = "phase-band-1" if i % 2 == 0 else "phase-band-2"
            cell_class = "numeric-cell rating-overall" if display_name == "Overall" else "numeric-cell rating-other"
            if is_last:
                cell_class += " phase-divider"
            rating_children.append({
                "field": field,
                "headerName": display_name,
                "width": 80,
                "minWidth": 65,
                "valueFormatter": rating_overall_style,
                "type": ["numericColumn"],
                "cellClass": cell_class,
                "cellClassRules": {
                    "sorted-col-highlight": sorted_highlight_rule,
                },
                "sortable": True,
                "filter": False,
                "headerClass": f"{band_class} style-header-wrap" + (" phase-divider-header" if is_last else ""),
                "wrapHeaderText": True,
                "autoHeaderHeight": True,
            })
        column_defs.append({
            "headerName": "Rating",
            "headerClass": "phase-band-1 phase-divider-header",
            "children": rating_children,
        })

    # Build grouped columns: Total, Attack, Defense
    groups = [
        ("Total", [f"Total | {XG_DISPLAY_NAMES[c]}" for c in XG_SUMMARY_COLUMNS]),
        ("Attack", [f"Attack | {XG_DISPLAY_NAMES[c]}" for c in XG_COLUMNS]),
        ("Defense", [f"Defense | {XG_DISPLAY_NAMES[c]}" for c in XG_AGAINST_COLUMNS]),
    ]

    for group_idx, (group_name, fields) in enumerate(groups):
        children = []
        # Insert Pts as first child of Total group
        if group_name == "Total":
            children.append({
                "field": "Pts",
                "headerName": "Pts",
                "width": 65,
                "minWidth": 55,
                "valueFormatter": int_formatter,
                "type": ["numericColumn"],
                "cellClass": "numeric-cell",
                "cellClassRules": {
                    "sorted-col-highlight": sorted_highlight_rule,
                },
                "sortable": True,
                "filter": False,
                "headerClass": "phase-band-2 style-header-wrap",
                "wrapHeaderText": True,
                "autoHeaderHeight": True,
            })
        band_offset = len(children)  # account for Pts column in Total group
        for i, field in enumerate(fields):
            display_name = field.split(" | ")[1]
            is_last = (i == len(fields) - 1)
            band_class = "phase-band-2" if (i + band_offset) % 2 == 0 else "phase-band-1"
            base_class = "numeric-cell phase-divider" if is_last else "numeric-cell"
            use_int = display_name in int_fields and not per_game
            col_def = {
                "field": field,
                "headerName": display_name,
                "width": 100,
                "minWidth": 80,
                "valueFormatter": int_formatter if use_int else decimal_formatter,
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
            children.append(col_def)

        group_band = "phase-band-1" if group_idx % 2 == 0 else "phase-band-2"
        column_defs.append({
            "headerName": group_name,
            "headerClass": f"{group_band} phase-divider-header",
            "children": children,
        })

    # Refresh cells on sort change
    on_sort_changed = JsCode("""
        function(params) {
            params.api.refreshCells({ force: true });
        }
    """)

    on_grid_ready = get_mobile_unpin_callback(size_to_fit=False)

    grid_options = {
        "columnDefs": column_defs,
        "defaultColDef": {
            "sortable": True,
            "sortingOrder": ["desc", "asc", None],
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

    custom_css = get_team_styles_table_css()
    custom_css.update({
        ".rating-overall": {
            "color": f"{COLORS['green']} !important",
            "font-weight": "700 !important",
        },
        ".rating-other": {
            "color": "#ffffff !important",
            "font-weight": "700 !important",
        },
    })

    AgGrid(
        data,
        gridOptions=grid_options,
        height=560,
        allow_unsafe_jscode=True,
        custom_css=custom_css,
        theme="balham-dark",
    )


def render_player_ratings_table(data: pd.DataFrame, show_values: bool = False) -> None:
    """Render the player ratings table with AgGrid."""
    if data.empty:
        st.info("No data matches the current filters.")
        return

    column_defs = [
        create_logo_column_def(),
        {
            "field": "Player",
            "headerName": "",
            "pinned": "left",
            "width": 280,
            "minWidth": 280,
            "sortable": True,
            "filter": False,
            "suppressMenu": True,
            "cellClass": "team-divider",
            "headerClass": "team-divider-header",
        },
    ]

    # Minutes formatter
    minutes_formatter = JsCode(
        "function(params) { return params.value != null ? params.value.toLocaleString() : '-'; }"
    )

    # Value formatter based on mode
    if show_values:
        value_formatter = JsCode(
            "function(params) { return params.value != null ? params.value.toFixed(2) : '-'; }"
        )
    else:
        value_formatter = JsCode(
            "function(params) { return params.value != null ? Math.round(params.value).toString() : '-'; }"
        )

    # Sort highlight rule
    sorted_highlight_rule = JsCode("""
        function(params) {
            if (!params.api) return false;
            const sortedCols = params.api.getColumnState().filter(c => c.sort);
            if (sortedCols.length === 0) return false;
            return sortedCols[0].colId === params.colDef.field;
        }
    """)

    # Bold value formatter for Overall column
    if show_values:
        overall_formatter = JsCode(
            "function(params) { return params.value != null ? params.value.toFixed(2) : '-'; }"
        )
    else:
        overall_formatter = JsCode(
            "function(params) { return params.value != null ? Math.round(params.value).toString() : '-'; }"
        )

    # Overall column - green header in Ratings mode, standard in Values mode
    overall_header_class = (
        "phase-band-2 style-header-wrap phase-divider-header"
        if show_values
        else "overall-header style-header-wrap phase-divider-header"
    )
    overall_col_def = {
        "field": "Overall",
        "headerName": "Overall",
        "width": 90,
        "minWidth": 80,
        "valueFormatter": overall_formatter,
        "type": ["numericColumn"],
        "cellClass": "numeric-cell overall-rating-cell phase-divider" if not show_values else "numeric-cell phase-divider",
        "cellClassRules": {
            "sorted-col-highlight": sorted_highlight_rule,
        },
        "sortable": True,
        "filter": False,
        "headerClass": overall_header_class,
        "wrapHeaderText": True,
        "autoHeaderHeight": True,
    }

    # Build component rating columns (skip Overall)
    component_names = [v for k, v in RATINGS_DISPLAY_NAMES.items() if k != "overall_rating"]
    component_children = []
    for i, col in enumerate(component_names):
        is_last = (i == len(component_names) - 1)
        band_class = "phase-band-1" if i % 2 == 0 else "phase-band-2"
        base_class = "numeric-cell phase-divider" if is_last else "numeric-cell"
        col_def = {
            "field": col,
            "headerName": col,
            "minWidth": 105,
            "flex": 1,
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
        component_children.append(col_def)

    # Role - top-level group header
    column_defs.append({
        "headerName": "Role",
        "headerClass": "phase-band-2 phase-divider-header",
        "children": [{
            "field": "Role",
            "headerName": "",
            "width": 70,
            "minWidth": 60,
            "sortable": True,
            "filter": False,
            "cellClass": "numeric-cell phase-divider",
            "headerClass": "ratings-dark-subheader phase-divider-header",
        }],
    })

    # Minutes - top-level group header
    column_defs.append({
        "headerName": "Minutes",
        "headerClass": "phase-band-1 phase-divider-header",
        "children": [{
            "field": "Minutes",
            "headerName": "",
            "width": 90,
            "minWidth": 80,
            "valueFormatter": minutes_formatter,
            "type": ["numericColumn"],
            "cellClass": "numeric-cell phase-divider",
            "sortable": True,
            "filter": False,
            "headerClass": "ratings-dark-subheader phase-divider-header",
        }],
    })

    # Overall - top-level group with green-styled subheader
    column_defs.append({
        "headerName": "",
        "headerClass": "phase-band-1",
        "children": [overall_col_def],
    })

    # Component Ratings group
    column_defs.append({
        "headerName": "Ratings",
        "headerClass": "phase-band-1",
        "children": component_children,
    })

    # Callbacks
    on_sort_changed = JsCode("""
        function(params) {
            params.api.refreshCells({ force: true });
        }
    """)

    on_grid_ready = JsCode("""
        function(params) {
            const api = params.api;
            const isMobile = window.innerWidth < 768;
            if (isMobile) {
                api.applyColumnState({
                    state: [
                        { colId: 'Logo', pinned: null },
                        { colId: 'Player', pinned: null }
                    ]
                });
            }
            api.sizeColumnsToFit();
        }
    """)

    grid_options = {
        "columnDefs": column_defs,
        "defaultColDef": {
            "sortable": True,
            "sortingOrder": ["desc", "asc", None],
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

    custom_css = get_player_ratings_table_css()

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
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            height: var(--control-height) !important;
            width: 100% !important;
        }}

        [data-testid="stSegmentedControl"] button {{
            height: var(--control-height) !important;
            min-height: var(--control-height) !important;
            line-height: var(--control-height) !important;
            margin: 0 !important;
            padding: 0 18px !important;
            border-radius: 0 !important;
            white-space: nowrap !important;
            flex: 1 1 0% !important;
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

        /* === Number input styling (minutes filter) === */
        div[data-testid="stNumberInput"] {{
            margin: 0 !important;
            padding: 0 !important;
        }}

        div[data-testid="stNumberInput"] > div {{
            border-radius: var(--control-radius) !important;
            background: {COLORS['dark']} !important;
            border: 1px solid rgba(255,255,255,0.10) !important;
            overflow: hidden;
        }}

        div[data-testid="stNumberInput"] input {{
            height: var(--control-height) !important;
            background: transparent !important;
            border: none !important;
            color: rgba(255,255,255,0.92) !important;
            text-align: center !important;
            font-size: 0.875rem !important;
        }}

        div[data-testid="stNumberInput"] button {{
            background: transparent !important;
            border: none !important;
            color: rgba(255,255,255,0.4) !important;
        }}

        div[data-testid="stNumberInput"] button:hover {{
            color: rgba(255,255,255,0.9) !important;
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

        /* Inset slider track to align within dropdown rounded corners */
        .stSlider {{
            padding-left: 3% !important;
            padding-right: 3% !important;
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
    # Single container for filters + table
    with st.container(border=True):
        conference_choice, category_choice, data_type = render_filters()

        # Load data based on For/Against toggle
        filename = "phases_against.csv" if data_type == "Against" else "phases.csv"
        data_path = Path(__file__).resolve().parent / filename
        if not data_path.exists():
            st.error(f"Missing {filename} in the app directory")
            st.stop()
        df = load_data(str(data_path), get_file_mtime(data_path))

        df["team_name"] = df["team_name"].astype(str)
        df["phase"] = df["phase"].astype(str)

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
    data_path = Path(__file__).resolve().parent / "team_tendencies.csv"
    if not data_path.exists():
        st.error("Missing team_tendencies.csv in the app directory")
        st.stop()

    df = load_data(str(data_path), get_file_mtime(data_path))

    with st.container(border=True):
        # Season, Conference filter, and Values/Percentiles toggle
        season_options = sorted(df["season_name"].unique(), reverse=True)
        conference_options = ["All MLS", "Eastern Conference", "Western Conference"]

        col_season, col_conference, col_toggle = st.columns([2, 3, 3], vertical_alignment="center")

        with col_season:
            season_choice = st.selectbox(
                "Season",
                season_options,
                index=0,
                label_visibility="collapsed",
                key="tendencies_season",
            )

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

        # Filter by season and conference
        filtered_df = df[df["season_name"] == season_choice].copy()
        filtered_df = filter_by_conference(filtered_df, conference_choice)

        # Prepare and display table
        show_percentiles = st.session_state.get("tendencies_view_mode", "Values") == "Percentiles"
        table_data = prepare_team_tendencies_data(filtered_df, show_percentiles)

        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

        render_team_tendencies_table(table_data, show_percentiles)

        render_csv_download(table_data, "futi_team_tendencies.csv")


def render_team_xg_tab() -> None:
    """Render the Team Performance tab content."""
    data_path = Path(__file__).resolve().parent / "team_xg.csv"
    if not data_path.exists():
        st.error("Missing team_xg.csv in the app directory")
        st.stop()

    df = load_data(str(data_path), get_file_mtime(data_path))

    with st.container(border=True):
        conference_options = ["All MLS", "Eastern Conference", "Western Conference"]

        col_conference, col_toggle = st.columns([3, 3], vertical_alignment="center")

        with col_conference:
            conference_choice = st.selectbox(
                "Conference",
                conference_options,
                index=0,
                label_visibility="collapsed",
                key="xg_conference",
            )

        with col_toggle:
            render_toggle(["Totals", "Per Game"], key="xg_view_mode", default="Totals")

        # Filter by conference
        filtered_df = filter_by_conference(df, conference_choice)

        # Prepare and display table
        per_game = st.session_state.get("xg_view_mode", "Totals") == "Per Game"
        table_data = prepare_team_xg_data(filtered_df, per_game)

        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

        render_team_xg_table(table_data, per_game)

        render_csv_download(table_data, "futi_expected_goals.csv")


# =============================================================================
# RATING HISTORY TAB
# =============================================================================


def _apply_chart_layout(fig: go.Figure) -> None:
    """Apply shared dark-theme Plotly layout styling."""
    fig.update_layout(
        height=500,
        margin=dict(l=50, r=0, t=30, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, -apple-system, sans-serif", color="white", size=14),
        hovermode="x unified",
        yaxis=dict(
            range=[0, 100],
            gridcolor="rgba(255,255,255,0.06)",
            zeroline=False,
            title=None,
            tickfont=dict(size=13),
            ticksuffix="  ",
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(255,255,255,0.06)",
            zeroline=False,
            dtick="M12",
            tick0="2016-07-01",
            tickformat="%Y",
            title=None,
            tickfont=dict(size=13),
        ),
    )


def _render_date_slider(df: pd.DataFrame, key_prefix: str) -> tuple[int, int]:
    """Render a year-range slider and return (start_year, end_year)."""
    min_year = df["rating_date"].dt.year.min()
    max_year = df["rating_date"].dt.year.max()
    years = list(range(min_year, max_year + 1))
    if len(years) < 2:
        return min_year, max_year
    return st.select_slider(
        "Date range",
        options=years,
        value=(min_year, max_year),
        label_visibility="collapsed",
        key=f"{key_prefix}_date_range",
    )


def _filter_by_date(df: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    """Filter dataframe to rows within the year range."""
    return df[
        (df["rating_date"].dt.year >= start_year)
        & (df["rating_date"].dt.year <= end_year)
    ]


def _render_team_history_view(df: pd.DataFrame, all_teams: list[str]) -> None:
    """Render single-team rating history with Overall/Attack/Defense lines."""
    # Row 1: Team selectbox (left) | Compare/History toggle (right)
    col_team, col_toggle = st.columns([3, 3], vertical_alignment="center")
    with col_team:
        team = st.selectbox(
            "Team",
            all_teams,
            index=0,
            label_visibility="collapsed",
            key="history_team",
        )
    with col_toggle:
        render_toggle(
            ["Compare Teams", "Team History"],
            key="history_view_mode",
            default="Team History",
        )

    # Row 2: Date slider
    col_date, _ = st.columns([3, 3], vertical_alignment="center")
    with col_date:
        start_year, end_year = _render_date_slider(df, "team_history")

    team_df = _filter_by_date(
        df[df["team_name"] == team].sort_values("rating_date"),
        start_year, end_year,
    )

    # Add traces with Overall last so green line is on top (z-order)
    fig = go.Figure()
    ordered = ["Defense", "Attack", "Overall"]  # Overall last = on top (z-order)
    for display_name in ordered:
        col_name = RATING_TYPE_COLUMNS[display_name]
        fig.add_trace(go.Scatter(
            x=team_df["rating_date"],
            y=team_df[col_name],
            mode="lines",
            name=display_name,
            line=dict(color=RATING_TYPE_COLORS[display_name], width=2),
            hovertemplate=f"{display_name}: %{{y}}<extra></extra>",
        ))

    _apply_chart_layout(fig)
    fig.update_layout(
        xaxis=dict(
            spikemode="across",
            spikethickness=1,
            spikecolor="white",
            spikedash="solid",
            hoverformat="%B %Y",
        ),
        legend=dict(
            orientation="h",
            traceorder="reversed",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_compare_teams_view(df: pd.DataFrame, all_teams: list[str]) -> None:
    """Render multi-team comparison for a single rating type."""
    # Default all teams to checked (re-applies each time view is entered,
    # since Streamlit clears widget keys when widgets leave the DOM)
    for team in all_teams:
        if f"hist_cb_{team}" not in st.session_state:
            st.session_state[f"hist_cb_{team}"] = True

    # Row 1: Team picker (left) | Compare/History toggle (right)
    col_teams, col_toggle = st.columns([3, 3], vertical_alignment="center")
    with col_teams:
        n_selected = sum(1 for t in all_teams if st.session_state.get(f"hist_cb_{t}", True))
        if n_selected == len(all_teams):
            label = "All MLS"
        elif n_selected == 0:
            label = "No teams"
        elif n_selected == 1:
            selected_name = next(t for t in all_teams if st.session_state.get(f"hist_cb_{t}", True))
            label = selected_name
        else:
            label = f"{n_selected} teams"

        with st.popover(label, use_container_width=True):
            col_all, col_none = st.columns(2)
            with col_all:
                if st.button("Select All", use_container_width=True, key="hist_all"):
                    for team in all_teams:
                        st.session_state[f"hist_cb_{team}"] = True
                    st.rerun()
            with col_none:
                if st.button("Select None", use_container_width=True, key="hist_none"):
                    for team in all_teams:
                        st.session_state[f"hist_cb_{team}"] = False
                    st.rerun()

            for team in all_teams:
                st.checkbox(team, key=f"hist_cb_{team}")

    with col_toggle:
        render_toggle(
            ["Compare Teams", "Team History"],
            key="history_view_mode",
            default="Compare Teams",
        )

    # Row 2: Date slider (left) | Rating toggle (right)
    col_date, col_rating = st.columns([3, 3], vertical_alignment="center")
    with col_date:
        start_year, end_year = _render_date_slider(df, "compare")
    with col_rating:
        render_toggle(
            ["Overall", "Attack", "Defense"],
            key="history_rating_type",
            default="Overall",
        )

    # Determine selected teams from checkboxes
    selected_teams = [t for t in all_teams if st.session_state.get(f"hist_cb_{t}", True)]

    rating_type = st.session_state.get("history_rating_type", "Overall")
    col_name = RATING_TYPE_COLUMNS[rating_type]

    # Apply date filter
    filtered_df = _filter_by_date(df, start_year, end_year)

    fig = go.Figure()
    logos_dir = Path(__file__).resolve().parent / "logos"
    logo_data = []

    for team in selected_teams:
        team_df = filtered_df[filtered_df["team_name"] == team].sort_values("rating_date")
        if team_df.empty:
            continue

        color = TEAM_COLORS.get(team, "#FFFFFF")

        # Glow trace: white outline behind the colored line, hidden by default
        fig.add_trace(go.Scatter(
            x=team_df["rating_date"],
            y=team_df[col_name],
            mode="lines",
            line=dict(color="white", width=5),
            opacity=0,
            hoverinfo="skip",
            showlegend=False,
        ))

        # Main colored trace
        fig.add_trace(go.Scatter(
            x=team_df["rating_date"],
            y=team_df[col_name],
            mode="lines+markers",
            name=team,
            line=dict(color=color, width=2),
            marker=dict(size=20, opacity=0),
            opacity=0.7,
            hovertemplate=f"{team}: %{{y}}<extra></extra>",
            showlegend=False,
        ))

        last_row = team_df.iloc[-1]
        logo_path = logos_dir / f"{team}.png"
        if logo_path.exists():
            logo_data.append((last_row["rating_date"], last_row[col_name], logo_path))

    # Determine x-axis range (always show years even with no teams)
    date_range_df = filtered_df if not filtered_df.empty else df
    x_min = date_range_df["rating_date"].min()
    x_max = date_range_df["rating_date"].max()

    # Add logos at each line's endpoint
    for last_x, y_val, logo_path in logo_data:
        with open(logo_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        fig.add_layout_image(
            dict(
                source=f"data:image/png;base64,{encoded}",
                x=last_x,
                y=y_val,
                xref="x",
                yref="y",
                sizex=56 * 24 * 60 * 60 * 1000,
                sizey=4,
                xanchor="left",
                yanchor="middle",
            )
        )

    _apply_chart_layout(fig)
    fig.update_layout(
        xaxis=dict(
            range=[x_min, x_max + pd.Timedelta(days=75)],
            type="date",
        ),
        hovermode="closest",
    )

    # Render as raw HTML with client-side hover-to-highlight JS
    chart_html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=False,
        config={"displayModeBar": False},
    )
    hover_js = """
    <style>body { background: transparent !important; margin: 0; }</style>
    <script>
    (function() {
        function setup() {
            var plot = document.querySelector('.plotly-graph-div');
            if (!plot || !plot.data) { setTimeout(setup, 100); return; }
            // Traces are paired: glow (i*2) + color (i*2+1) per team
            var n = plot.data.length;
            var numTeams = n / 2;
            var locked = -1;

            function highlight(colorIdx) {
                // colorIdx is the index of the colored trace (odd indices)
                var glowIdx = colorIdx - 1;
                var opac = [], widths = [];
                for (var i = 0; i < n; i++) {
                    if (i === glowIdx) {
                        opac.push(0.4);  // show white glow
                        widths.push(5);
                    } else if (i === colorIdx) {
                        opac.push(1.0);
                        widths.push(3);
                    } else if (i % 2 === 0) {
                        opac.push(0);    // hide other glows
                        widths.push(5);
                    } else {
                        opac.push(0.15); // dim other lines
                        widths.push(1.5);
                    }
                }
                Plotly.restyle(plot, {opacity: opac, 'line.width': widths});
            }

            function resetAll() {
                var opac = [], widths = [];
                for (var i = 0; i < n; i++) {
                    if (i % 2 === 0) {
                        opac.push(0);    // glows hidden
                        widths.push(5);
                    } else {
                        opac.push(0.7);  // normal lines
                        widths.push(2);
                    }
                }
                Plotly.restyle(plot, {opacity: opac, 'line.width': widths});
            }

            plot.on('plotly_hover', function(data) {
                if (locked >= 0) return;
                highlight(data.points[0].curveNumber);
            });

            plot.on('plotly_unhover', function() {
                if (locked >= 0) return;
                resetAll();
            });

            plot.on('plotly_click', function(data) {
                var ci = data.points[0].curveNumber;
                if (locked === ci) {
                    locked = -1;
                    resetAll();
                } else {
                    locked = ci;
                    highlight(ci);
                }
            });

            // Double-click anywhere to unlock
            plot.on('plotly_doubleclick', function() {
                if (locked >= 0) {
                    locked = -1;
                    resetAll();
                }
            });
        }
        setup();
    })();
    </script>
    """
    components.html(
        chart_html + hover_js,
        height=530,
        scrolling=False,
    )


def render_rating_history_tab() -> None:
    """Render the Team Ratings tab content."""
    data_path = Path(__file__).resolve().parent / "team_ratings.csv"
    if not data_path.exists():
        st.error("Missing team_ratings.csv in the app directory")
        st.stop()

    df = load_data(str(data_path), get_file_mtime(data_path))
    df["rating_date"] = pd.to_datetime(df["rating_date"])
    all_teams = sorted(df["team_name"].unique().tolist())

    with st.container(border=True):
        view_mode = st.session_state.get("history_view_mode", "Compare Teams")
        if view_mode == "Team History":
            _render_team_history_view(df, all_teams)
        else:
            _render_compare_teams_view(df, all_teams)


def render_player_ratings_tab() -> None:
    """Render the Player Ratings tab content."""
    data_path = Path(__file__).resolve().parent / "drafts" / "player_ratings.csv"
    if not data_path.exists():
        st.error("Missing player_ratings.csv in the app directory")
        st.stop()

    df = load_data(str(data_path), get_file_mtime(data_path))

    with st.container(border=True):
        role_options = ["All Roles"] + sorted(df["role"].dropna().unique().tolist())
        team_options = ["All Teams"] + sorted(df["team_name"].dropna().unique().tolist())

        col_team, col_role, col_minutes, col_toggle = st.columns(
            [2.5, 2, 1.5, 3], vertical_alignment="center"
        )

        with col_team:
            team_choice = st.selectbox(
                "Team",
                team_options,
                index=0,
                label_visibility="collapsed",
                key="ratings_team",
            )

        with col_role:
            role_choice = st.selectbox(
                "Position",
                role_options,
                index=0,
                label_visibility="collapsed",
                key="ratings_role",
            )

        with col_minutes:
            min_minutes = st.number_input(
                "Min minutes",
                min_value=0,
                max_value=int(df["minutes_played"].max()),
                value=None,
                step=100,
                label_visibility="collapsed",
                key="ratings_min_minutes",
                placeholder="Minutes",
            )

        with col_toggle:
            render_toggle(["Ratings", "Values"], key="ratings_view_mode", default="Ratings")

        col_search, _ = st.columns([4.5, 4.5])
        with col_search:
            player_search = st.text_input(
                "Search players",
                label_visibility="collapsed",
                key="ratings_player_search",
                placeholder="Search players",
            )

        # Filter by team, role, minutes, and player name
        filtered_df = df.copy()
        if team_choice != "All Teams":
            filtered_df = filtered_df[filtered_df["team_name"] == team_choice]
        if role_choice != "All Roles":
            filtered_df = filtered_df[filtered_df["role"] == role_choice]
        if min_minutes is not None and min_minutes > 0:
            filtered_df = filtered_df[filtered_df["minutes_played"] >= min_minutes]
        if player_search:
            filtered_df = filtered_df[filtered_df["player_name"].str.contains(player_search, case=False, na=False)]

        # Prepare and display table
        show_values = st.session_state.get("ratings_view_mode", "Ratings") == "Values"
        table_data = prepare_player_ratings_data(filtered_df, show_values)

        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

        render_player_ratings_table(table_data, show_values)

        render_csv_download(table_data, "futi_player_ratings.csv")


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
    tab_phases, tab_styles, tab_tendencies, tab_xg, tab_history = st.tabs([
        "Phases", "Team Styles", "Team Tendencies", "Team Performance",
        "Team Ratings",
    ])

    with tab_phases:
        render_phases_tab()

    with tab_styles:
        render_team_styles_tab()

    with tab_tendencies:
        render_team_tendencies_tab()

    with tab_xg:
        render_team_xg_tab()

    with tab_history:
        render_rating_history_tab()

    # Player Ratings tab — hidden until ready for public release
    # with tab_ratings:
    #     render_player_ratings_tab()


if __name__ == "__main__":
    main()
