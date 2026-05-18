# Plan: Refactor dashboard.py → Single-Page IPO List with Tap-to-Expand

## Goal

Replace the current 4-tab (`Overview`, `IPO Browser`, `Sector Analysis`) layout with a single-page IPO card list where each card expands inline to show full detail (score breakdown, peer comparison, liquidity). No auto-scanning. Everything is on-demand.

## Files Changed

| File | Action |
|------|--------|
| `dashboard.py` | **Rewrite** — keep helpers, gut multi-page navigation, restructure as single page |
| `scoring_engine.py` | **No changes** — import stays, must not touch |
| `peer_comparison.py` | **No changes** — import stays, must not touch |
| `ipo_scores.json` | **No schema changes** — data format preserved |

## Architecture (New Flow)

```
[Start] → load_scores() from ipo_scores.json
            ↓
   Single-page layout:
     ┌─────────────────────────────────────┐
     │ Header: Title + "Add New IPO" btn   │
     ├─────────────────────────────────────┤
     │ Filters bar: Verdict / Sector /     │
     │ Market dropdowns + Search text      │
     ├─────────────────────────────────────┤
     │ Count: "Showing N of M IPOs"        │
     ├─────────────────────────────────────┤
     │ IPO Card ──────────────────────     │
     │ [Name] [Sector] [Alpha: XX/100]     │
     │ [Verdict Badge]  [Refresh btn]      │
     │ (tap to expand v)                   │
     │ ┌ Detail ──────────────────────┐    │
     │ │ Score gauge                   │    │
     │ │ Quick stats (market, price,   │    │
     │ │   PE, oversub, margin, CAGR)  │    │
     │ │ Score breakdown chart (7 bar) │    │
     │ │ Peer comparison table         │    │
     │ │ Liquidity risk assessment     │    │
     │ └───────────────────────────────┘    │
     │──────────────────────────────────────│
     │ ... next card ...                    │
     └─────────────────────────────────────┘
     │ Footer (as before)                    │
```

## Implementation Steps

### Step 1: Strip Multi-Page Navigation

**What:** Remove the `st.sidebar.radio` page switcher, the 3 `elif page == ...` blocks, and all Overview / Sector Analysis code.

**Details:**
- Delete lines ~434-792 except the footer.
- Keep: everything in the "Data helpers" section (`load_scores`, `save_scores`, `prepare_df`), all component functions (`kpi_card`, `score_gauge`, `score_breakdown_chart`, `render_ipo_detail`, `verdict_distribution`, `sector_score_chart`), CSS, imports, sidebar branding.
- Keep sidebar stats display (Total IPOs, BUY/NEUTRAL/AVOID counts, Avg Score) as a sidebar summary.
- Remove scraped listings / Bursa refresh logic (global refresh button).
- The old "Manual entry" form moves to the new "Add New IPO" button.

### Step 2: Build Single-Page IPO Card List

**What:** After the sidebar, render a single-page layout.

**Structure:**

```
st.title()
st.markdown()  # subtitle
col_add, col_fill = st.columns([1, 3])
with col_add:
    "Add New IPO" button (opens empty expander with form)

Filters row (side-by-side):
  - Verdict multiselect (BUY/NEUTRAL/AVOID)
  - Sector multiselect
  - Market multiselect
  - Search text input

st.caption(f"Showing {len(filtered)} of {len(scores)} IPOs")

For each IPO in filtered list → render_card(ipo)
```

**`render_card(ipo)` function:**

```python
def render_card(ipo: dict):
    score_val = ipo.get("alpha_score") or ipo.get("total_score", 0)
    verdict = ipo.get("verdict", "N/A")
    color = VERDICT_COLORS.get(verdict, "#95A5A6")

    # Build collapsed card header
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.markdown(f"**{ipo['company_name']}**  ·  {ipo.get('sector', 'N/A')}")
    with col2:
        # Color-coded Alpha Score badge
        st.markdown(f"<div style='background:{color}15;border:1px solid {color};...'>{score_val:.0f}/100</div>")
    with col3:
        # Verdict badge
        st.markdown(f"<div style='...'>{verdict}</div>")
        # Refresh data button
        if st.button(f"🔄 Refresh", key=f"refresh_{ipo.get('company_name', 'unknown')}"):
            rescore = calculate_alpha_score(ipo)
            ipo["alpha_score"] = rescore["total_score"]
            ipo["verdict"] = rescore["verdict"]
            ipo["score_breakdown"] = rescore["breakdown"]
            save_scores(...)
            st.rerun()

    # Expandable detail
    with st.expander("📊 View Details", expanded=False):
        render_ipo_detail(ipo)
```

**Header format per card** (no expander, click-based show/hide):

Use `st.expander` inside the card with `label` being the card summary: company name + sector + color-coded score + verdict badge. The expander body calls the existing `render_ipo_detail(ipo)`.

Alternative approach for cleaner UX: use `st.expander` directly with a rich label. This is the most Streamlit-idiomatic way.

**Label format:**
```
f"🏷️ {company_name} — {sector}  |  Alpha: {score:.0f}/100  [{verdict}]"
```

### Step 3: "Add New IPO" Button → Form

**What:** A button at the top of the page that opens an empty `st.expander` with the manual entry form.

**Implementation:**

```python
show_add_form = st.button("➕ Add New IPO", type="primary")
if show_add_form:
    # Force expander open via session state
    with st.expander("➕ Add New IPO", expanded=True):
        # Show the same form from old IPO Browser
        with st.form("manual_ipo_form"):
            ...  # same fields
            if submitted:
                result = calculate_alpha_score(ipo_data)
                ... save & show success
```

Use `st.session_state["show_add_form"]` to toggle the expander open/closed.

### Step 4: Per-IPO "Refresh" Button

**What:** Each card gets a small "Refresh Data" button. When clicked:

1. Calls `calculate_alpha_score(ipo)` with the IPO's existing data
2. Updates `ipo["alpha_score"]`, `ipo["verdict"]`, `ipo["score_breakdown"]`
3. Persists to `ipo_scores.json`
4. Calls `st.rerun()` to reflect changes

**Implementation** (inside `render_card`):

```python
refresh_key = f"refresh_{ipo.get('company_name', '')}_{ipo.get('ticker', '')}"
if st.button("🔄 Refresh", key=refresh_key, help="Re-score this IPO"):
    result = calculate_alpha_score(ipo)
    ipo["alpha_score"] = result["total_score"]
    ipo["verdict"] = result["verdict"]
    ipo["score_breakdown"] = result["breakdown"]
    scores = load_scores()
    # Find and update this IPO in list
    for i, s in enumerate(scores):
        if s.get("company_name") == ipo.get("company_name"):
            scores[i] = ipo
            break
    save_scores(scores)
    st.success(f"✅ {ipo['company_name']} re-scored: {result['total_score']:.1f}/100 → {result['verdict']}")
    st.rerun()
```

### Step 5: Clean Up Unused Code & Imports

**Remove from imports:**
- `from scraper_integration import batch_scrape_all` — no more Bursa scraping
- `full_pipeline_with_peers` from peer_comparison (only `compare_ipo_to_sector` needed)

**Remove component functions no longer needed:**
- `verdict_distribution` (pie chart, was for Overview page)
- `sector_score_chart` (was for Overview + Sector Analysis)
- Maybe keep them commented or move to a separate utils module if needed later

Actually — requirements say keep `scoring_engine.py` and `peer_comparison.py` unchanged. The dashboard.py's own unused functions can be removed. But to be safe, leave them in place (they don't hurt). The import of `batch_scrape_all` should be removed though since it brings in scraper dependency.

**Remove:**
- `from scraper_integration import batch_scrape_all`
- `@st.cache_data` block for `get_live_bursa_ipos`
- Old sidebar navigation radio
- All 3 page blocks (Overview, IPO Browser page-switching logic, Sector Analysis)
- Old "Refresh from Bursa" button
- The `unused render_card` mention — actually there is no such function currently, it's all inline within the "IPO Browser" tab.

### Step 6: Keep / Preserve

**Preserve unchanged from current dashboard.py:**
- Imports: `st`, `pd`, `plt`, `go`, `make_subplots` — keep all (plotly needed for gauge/charts)
- Path setup, `BOT_DIR`, `DATA_DIR`, `SCORES_DB`
- `load_scores()`, `save_scores()`, `prepare_df()`
- CSS styling block
- `kpi_card()`, `score_gauge()`, `score_breakdown_chart()`, `render_ipo_detail()`
- `VERDICT_COLORS`, `BURSA_BLUE`, etc.
- Sidebar branding + stats (adapt slightly)
- Footer

## State Management

Use `st.session_state` for:
- `show_add_form: bool` — toggles the "Add New IPO" expander
- `expanded_ipo: str | None` — currently expanded IPO name (or use `st.expander` default behavior)

**New state variables:**

```python
if "show_add_form" not in st.session_state:
    st.session_state.show_add_form = False
```

## Data Flow

```
ipo_scores.json ──load_scores()──→ list[dict] ──filter──→ filtered list
                                                          │
                            ┌─────────────────────────────┘
                            ↓
                     render_card(ipo) for each
                            │
                   ┌────────┴────────┐
                   ↓                 ↓
            Refresh btn →    Expander →
            update dict →   render_ipo_detail()
            save → rerun       │
                         score_gauge()
                         score_breakdown_chart()
                         compare_ipo_to_sector()
                         assess_liquidity_risk()
```

## Edge Cases

| Case | Handling |
|------|----------|
| No IPOs in DB | Show `st.info("No IPOs yet. Click 'Add New IPO' to get started.")` |
| IPO missing `alpha_score` | Fallback to `total_score`, default to 0 |
| Broken JSON file | Return `[]` (existing behavior) |
| Duplicate name on Add | Check existing names, show error (existing behavior) |
| Refresh on IPO with nulls | `calculate_alpha_score` handles missing fields defensively |
| All filters removed | Show all IPOs |
| Search no match | Show 0 results caption |

## Test / Verification

```bash
cd bursa-ipo-bot && streamlit run dashboard.py
```

Or via streamlit_app.py:
```bash
cd bursa-ipo-bot && streamlit run streamlit_app.py
```

Verify:
1. Page loads as single list — no sidebar tabs for navigation
2. Each IPO shows as a card with name, sector, color-coded score, verdict badge
3. Click card → expand → shows score breakdown, peer comparison, liquidity
4. "Add New IPO" → form → submit → appears in list
5. Each card has a "Refresh" button → re-scores → updates display
6. Data persists in `ipo_scores.json`
7. Sidebar shows summary stats (count, verdict breakdown, avg score)

## Migration Path

1. Open `dashboard.py`
2. Delete lines 434-792 (all page logic + sidebar navigation)
3. Delete the `import batch_scrape_all` at top
4. Delete `verdict_distribution()` and `sector_score_chart()` functions if desired (optional cleanup)
5. Delete `prepare_df()` if no longer needed (or keep for sidebar stats)
6. Insert new single-page code in place of old page blocks
7. Keep footer

## Summary of What Stays vs Goes

| Element | Status |
|---------|--------|
| CSS styling | ✅ Keep |
| `load_scores` / `save_scores` | ✅ Keep |
| `prepare_df` | ✅ Keep (used for sidebar stats) |
| `kpi_card` | ✅ Keep |
| `score_gauge` | ✅ Keep |
| `score_breakdown_chart` | ✅ Keep |
| `render_ipo_detail` | ✅ Keep (called by expander) |
| `verdict_distribution` | ❌ Remove (pie chart — Overview only) |
| `sector_score_chart` | ❌ Remove (Overview / Sector Analysis only) |
| Sidebar branding | ✅ Keep |
| Sidebar stats | ✅ Keep (adapt to show counts) |
| `batch_scrape_all` import | ❌ Remove |
| `full_pipeline_with_peers` import | ❌ Remove |
| Sidebar radio navigation | ❌ Remove |
| Overview page block | ❌ Remove |
| IPO Browser page block | ❌ Remove (replace with card list) |
| Sector Analysis page block | ❌ Remove |
| Manual entry form | ♻️ Move to "Add New IPO" expander at top |
| "Refresh from Bursa" button | ❌ Remove |
| Footer | ✅ Keep |
