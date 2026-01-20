# Active Tasks

---

## ✅ PRIORITY 1: Team Column Scroll Behavior (CLOSED)

### Final Decision
Team column is **not pinned** - it scrolls away with phase columns. Only the Logo column is pinned/frozen.

AG Grid doesn't natively support "scroll priority" behavior (where Team would appear before phase columns when scrolling left). Custom JavaScript scroll handling would be required, which adds complexity. The current behavior (Team scrolls with data, Logo stays pinned) is acceptable.

### Current State
- Logo column: pinned left (always visible)
- Team column: scrolls with phase columns (not pinned)

---

## Task 8: Right-Align Numbers in Data Columns

### Goal
Ensure all numeric values in the data columns are right-aligned for better readability and visual alignment of decimal points. Keep header text center-aligned.

### Current State
- Numbers may be using default alignment (left or center)
- Headers are center-aligned (good, keep this)

### Implementation Plan

#### 8.1 Add Cell Alignment to Phase Columns
In `render_data_table()`, add `cellStyle` to phase column configurations:

```python
child_def = {
    "field": col_name,
    "headerName": metric_display,
    "width": 80,
    "minWidth": 70,
    "valueFormatter": value_formatter,
    "type": ["numericColumn"],  # This should help with alignment
    "cellStyle": {"textAlign": "right"},  # Explicit right alignment
}
```

#### 8.2 Verify Header Alignment
Headers should remain center-aligned. The `type: ["numericColumn"]` may affect header alignment, so verify and add explicit header styling if needed:

```python
".ag-header-cell": {
    "text-align": "center !important",
    ...
}
```

### Files to Modify
- `app.py`: Add `cellStyle` to phase column definitions in `render_data_table()`

### Testing Checklist
- [ ] All numeric values in Count, Won, Share columns are right-aligned
- [ ] Decimal points align vertically within each column
- [ ] Percentages align at the % symbol
- [ ] Header text remains center-aligned
- [ ] Team column text remains left-aligned

---

## ✅ Task 9: Match Second Row Header Banding to First Row (COMPLETE)

### Goal
Apply the same alternating background color banding to the second row of headers (COUNT, WON, SHARE) that currently applies to the first row (phase names like Buildup, Progression).

### Current State
- First row headers (phase group names) have alternating banding: `#0E374B` and `#0A2D3D`
- Second row headers (metric names) use a uniform background color
- This creates visual disconnect between the two header rows

### Implementation Plan

#### 9.1 Add headerClass to Child Columns
When building child column definitions, pass down the same band class from the parent group:

```python
for i, (phase_name, children) in enumerate(phase_groups.items()):
    band_class = "phase-band-1" if i % 2 == 0 else "phase-band-2"

    # Apply band_class to child columns too
    for child in children:
        child["headerClass"] = band_class  # Same class as parent group

    column_defs.append({
        "headerName": phase_name,
        "headerClass": band_class,
        "children": children,
    })
```

#### 9.2 Update CSS for Child Headers
Ensure the band classes apply their background to the second row headers:

```python
".phase-band-1.ag-header-cell": {
    "background-color": "#0E374B !important",
},
".phase-band-2.ag-header-cell": {
    "background-color": "#0A2D3D !important",
},
```

Or if AG Grid uses different selectors for child headers, target those specifically.

### Files to Modify
- `app.py`:
  - Update the column group loop to add `headerClass` to child columns
  - Update `custom_css` to apply band colors to second-row headers

### Testing Checklist
- [ ] COUNT, WON, SHARE headers under "Buildup" have same background as "Buildup" header
- [ ] COUNT, WON, SHARE headers under "Progression" have same background as "Progression" header
- [ ] Alternating pattern is visually clear across both header rows
- [ ] Banding continues consistently for all phase groups

### Visual Reference

**Before** (current):
```
┌▓▓▓▓▓▓▓▓▓Buildup▓▓▓▓▓▓▓▓▓▓┬░░░░░░░Progression░░░░░░░░┐
│  COUNT  │  WON   │ SHARE  │  COUNT  │  WON   │ SHARE │  ← uniform color
```

**After** (goal):
```
┌▓▓▓▓▓▓▓▓▓Buildup▓▓▓▓▓▓▓▓▓▓┬░░░░░░░Progression░░░░░░░░┐
│▓ COUNT ▓│▓ WON  ▓│▓SHARE▓│░ COUNT ░│░ WON  ░│░SHARE░│  ← matching banding
```

---

## Implementation Order

1. ~~**Priority 1**: Team Column Scroll Behavior~~ ✅ CLOSED (accepted current behavior)
2. ~~**Task 8**: Right-align numbers in data columns~~ ✅ COMPLETE
3. ~~**Task 9**: Match second row header banding to first row~~ ✅ COMPLETE
4. ~~**Task 10**: Style CSV download button to match segmented control~~ ✅ COMPLETE

---

## ✅ Task 10: Style CSV Download Button to Match Segmented Control (COMPLETE)

### Goal
Style the `.csv` download button to look **identical** to an unselected button in the Values/Percentiles segmented control toggle.

### Current Problem
Streamlit's `st.download_button` has CSS that cannot be overridden easily:
- Streamlit may apply inline styles (higher specificity than our CSS)
- Component may use shadow DOM isolation
- Dynamic class names (st-emotion-cache-*) that change between builds

**Previous attempts that FAILED:**
- `[data-testid="stDownloadButton"]` selectors with `!important`
- `.st-key-csv_download` class targeting (using the `key` parameter)
- Various nested selector combinations

### Current Workaround (Partial)
Currently using a custom HTML `<a>` tag instead of `st.download_button`:
```python
csv_b64 = base64.b64encode(csv_data.encode()).decode()
download_placeholder.markdown(
    f'<a href="data:text/csv;base64,{csv_b64}" download="futi_phases.csv" class="csv-download-btn">.csv</a>',
    unsafe_allow_html=True,
)
```

This gives us full CSS control via `.csv-download-btn` class.

### Required Investigation

**Step 1: Inspect the segmented control (working reference)**
1. Open browser DevTools (F12 or right-click → Inspect)
2. Click on the **Values** or **Percentiles** button in the toggle
3. In Elements panel, find the element hierarchy
4. Note these exact values from Computed Styles:
   - Container: `height`, `border-radius`, `border`, `background`
   - Unselected button: `height`, `background`, `color`, `font-size`, `font-weight`, `padding`
   - Selected button: `background`, `color`, `border-radius`

**Step 2: Inspect our custom download button**
1. Click on the `.csv` button
2. Find the `<a class="csv-download-btn">` element
3. Check Computed Styles - compare to segmented control values
4. Look for any styles NOT being applied (crossed out in Styles panel)

**Step 3: Identify discrepancies**
Record what's different:
- [ ] Height mismatch?
- [ ] Border-radius not pill-shaped?
- [ ] Background color wrong?
- [ ] Border missing or wrong color?
- [ ] Text color wrong?
- [ ] Font size/weight wrong?
- [ ] Hover state not working?

### Target Styles (Reference)

The download button should match these exact values:

```css
/* Container/button combined (since it's standalone) */
.csv-download-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 44px;                              /* var(--control-height) */
    padding: 0 18px;
    border-radius: 999px;                      /* full pill */
    border: 1px solid rgba(255,255,255,0.10);
    background: rgba(6,34,48,0.70);
    color: rgba(255,255,255,0.7);
    font-family: Inter, system-ui, sans-serif;
    font-size: 0.875rem;                       /* 14px */
    font-weight: 500;
    text-decoration: none;
    cursor: pointer;
}

.csv-download-btn:hover {
    background: #0FE6B4;                       /* COLORS['green'] */
    color: #03151E;                            /* COLORS['dark'] */
}
```

### Current CSS Location
`app.py` → `inject_styles()` function → `/* === Custom CSV download button ... */` section (around line 907-938)

### Implementation Steps

1. **Run the app locally**: `.venv/bin/streamlit run app.py`
2. **Open in browser**: http://localhost:8501
3. **Complete Step 1-3 above** (DevTools inspection)
4. **Record findings** in this document under "Investigation Results"
5. **Update CSS** in `app.py` based on findings
6. **Test** using checklist below

### Investigation Results
*(Fill in after DevTools inspection)*

**Segmented control computed styles:**
- Container height: ___
- Container border-radius: ___
- Container background: ___
- Container border: ___
- Button color: ___
- Button font-size: ___
- Button font-weight: ___

**Download button computed styles:**
- Height: ___
- Border-radius: ___
- Background: ___
- Border: ___
- Color: ___
- Font-size: ___
- Font-weight: ___

**Discrepancies found:**
- ___

### Testing Checklist
Run app and visually compare the `.csv` button to the Values/Percentiles toggle:

- [ ] **Height**: Button is exactly same height as toggle (44px)
- [ ] **Shape**: Full pill shape (completely rounded ends)
- [ ] **Border**: Subtle border visible, matches toggle border
- [ ] **Background**: Semi-transparent dark background, matches toggle
- [ ] **Text color**: Muted white text, matches unselected toggle button
- [ ] **Font**: Same size and weight as toggle text
- [ ] **Hover - background**: Fills with green (#0FE6B4)
- [ ] **Hover - text**: Text turns dark (#03151E)
- [ ] **Focus**: No blue outline or glow on click/focus
- [ ] **Alignment**: Button vertically aligned with other controls in the row

### Visual Reference

**Goal** - Download button should look like this:
```
┌─────────────────┐ ┌─────────────────────┐ ┌──────────┬────────────┐ ┌───────┐
│ All teams    ▼  │ │ All phases       ▼  │ │  Values  │ Percentiles│ │ .csv  │
└─────────────────┘ └─────────────────────┘ └──────────┴────────────┘ └───────┘
     Dropdown            Dropdown              Segmented Control       Download
                                               (pill shape)           (pill shape)
```

All four controls should have:
- Same height (44px)
- Pill-shaped borders (999px radius)
- Same border color (rgba(255,255,255,0.10))
- Same semi-transparent dark background

---

# Completed Tasks (Compressed)

<details>
<summary>Click to expand completed task history</summary>

## Tasks 1-7 Summary (All Complete)

| Task | Description | Status |
|------|-------------|--------|
| 1 | Team logos in far left 50px column | ✓ Complete |
| 2 | Sticky/pinned columns via AgGrid | ✓ Complete |
| 3 | Number formatting (decimals, %) | ✓ Complete |
| 4 | Two-tiered headers (phase groups) | ✓ Complete |
| 5 | Only logo sticky, Team scrolls | ✓ Complete |
| 6 | Remove Team filter icon, widen column | ✓ Complete |
| 7 | Phase header banding | ✓ Complete |

### Key Implementation Details

**Technology**: Switched from `st.dataframe()` (Glide Data Grid) to `streamlit-aggrid` for proper column pinning support.

**Table Structure**:
- Logo column: 50px, pinned left, custom JS cell renderer for base64 images
- Team column: 230px, scrollable (not pinned), no filter icon
- Phase columns: Grouped under phase names, two-tier headers

**Styling**:
- Dark theme: `#0E374B` (dark2), `#0A2D3D` (darker band)
- Green accent: `#0FE6B4`
- Alternating row backgrounds
- Phase header banding with alternating colors
- Vertical divider lines between phase clusters

**Number Formatting** (via JS valueFormatter):
- Count: `%.1f` (one decimal)
- Won/Success rate: `%.1f%%` (percentage)
- Share: `%.1f%%` (percentage)
- Percentile: `%d` (integer)

**Files Modified**: `app.py`, `requirements.txt` (added streamlit-aggrid)

### Session-by-Session Progress

- **Session 1-2**: Task 1 complete (logos), Task 2 attempted but failed (CSS sticky doesn't work with canvas)
- **Session 3**: Task 2 complete (switched to AgGrid), Task 3 complete (number formatting)
- **Session 4**: Task 4 complete (two-tier headers via column groups)
- **Session 5**: Task 5 complete (only logo pinned)
- **Session 6**: Task 6 complete (removed filter, widened Team)
- **Session 7**: Task 7 complete (phase banding)
- **Session 8**: Additional refinements (header centering, dark band color)
- **Session 9**: Divider lines between phase clusters

</details>
