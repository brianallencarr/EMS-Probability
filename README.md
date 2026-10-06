
# EMS Probability Explorer v3.1.0

A button-driven, chief-facing Streamlit application for querying 10 years of EMS call data.

## Major v2 additions

- Button-first workflow with four tabs:
  - Quick buttons
  - Build a probability
  - Compare
  - Natural language
- Incident-level concurrency engine
- Wilson 95% confidence intervals
- Small-sample warnings
- Audit / show-math drawer
- Monthly probability visualization
- JSON result export
- Descriptive risk ratio and odds ratio in comparison mode

## Concurrency definition

The raw unit-level export is collapsed to one interval per distinct incident:

- incident start = earliest `Incident Unit Notified By Dispatch Date Time`
- incident end = latest `Incident Unit Back In Service Date Time`

For a new incident at time `t`, `active_incidents_at_start` is the number of distinct incident intervals active immediately after that incident begins.

Thus:

- `2+ concurrent at dispatch` means the new incident begins while at least one other distinct incident is already active.
- `3+ concurrent at dispatch` means at least three total distinct incidents, including the new one, are active at that dispatch instant.

This is an incident-based probability, not the fraction of clock time during which the system is concurrently occupied.

## Run on macOS

1. Unzip the folder.
2. Open Terminal.
3. `cd` into the folder.
4. Run:

```bash
./run.sh
```

If blocked:

```bash
chmod +x run.sh
./run.sh
```

## Run on Windows

Double-click `run.bat`, or from PowerShell:

```powershell
.\run.bat
```

## Docker

```bash
docker build -t ems-probability-explorer .
docker run --rm -p 8501:8501 ems-probability-explorer
```

Then open `http://localhost:8501`.

## Data governance

The current natural-language parser is local and rule-based. EMS records are not sent to an external LLM.

## Files in data/

The four canonical project files are included plus one derived concurrency cache:

- EMS_10yr_Clean_Normalized.csv
- EMS_10yr_Normalization_Rules.csv
- Incident-Dates-and-Times-last-10-years_2026-08-29_180618.csv
- EMS_10yr_P87_Calculated_Details_DAD.xlsx
- EMS_10yr_Concurrency_Incident_Level.csv


## v2.2 startup patch

Startup quick buttons are now: 2+ Concurrent Calls, Cardiac Calls, Trauma Calls, and Turnout ≤ 2 min.


## v2.4 time-of-day buttons

Added six four-hour quick filters based on the normalized dispatch-hour field: 00–04, 04–08, 08–12, 12–16, 16–20, and 20–24. Each interval is left-inclusive and right-exclusive (for example, 08–12 means 08:00 through 11:59:59).

## v2.5 quick-access buttons

Added clinical quick-access buttons:
- Trauma/Injury
- Cardiac
- Respiratory
- Neurologic

Added performance quick-access buttons:
- Turnout ≤ 2 min
- Response ≤ 10 min
- Scene ≤ 20 min
- Commitment > 90 min

## v2.6 quick-access additions

Gender:
- Male
- Female
- Unspecified

Age:
- 0–9
- 10–17
- 18–24
- 25–44
- 45–64
- 65–74
- 75–84
- 85+

## v2.7 multi-select quick access

Quick-access buttons are now toggleable. The user can select more than two filters before calculation.

Rules:
- Multiple selections within clinical, gender, weekday, season, time, or age are OR.
- Selections across different categories are AND.
- Multiple performance metrics are AND.
- Concurrency threshold is a single selector (2+, 3+, or 4+).
- Concurrency cannot yet be mixed with clinical, age, gender, or performance filters because those fields are not all present in the incident-level concurrency cache.

## v2.8 — enriched concurrency

New file:
- `EMS_10yr_Clean_Normalized_Concurrency_Enriched.csv`

Method:
- Concurrency is calculated once per unique incident using earliest unit-notified time and latest unit-back-in-service time.
- Those concurrency fields are joined back to each matching normalized record by incident number.
- No conflicting incident-level age, gender, impression, unit, or performance value is collapsed into a fabricated singular value.

This enables combined queries using concurrency with:
- clinical impression
- age
- gender
- day / season / time
- zone
- unit
- performance measures

Semantics:
- `EMS_10yr_Concurrency_Incident_Level.csv` remains the correct one-row-per-incident table for pure system-demand concurrency probabilities.
- The enriched table is used when concurrency is combined with clinical/demographic/operational record fields.

## v2.8.1 patch

Fixes multi-select notation rendering for month/season and other list-valued filters. Probability calculations were already handling list filters correctly; the failure occurred only while formatting the displayed P(A|B) notation.

## v2.8.2 — Wilson CI explanation

The Audit / Show Math section now explains the 95% Wilson confidence interval in chief-level operational language, including statistical precision, narrow vs. wide intervals, comparison use, and the correct frequentist interpretation.

## v2.8.3 — All clinical impressions

In Build a Probability → Clinical impression, the selector now includes `All`.

Selecting `All` applies no provider-impression restriction, allowing the user to build probabilities from other conditions without selecting a specific clinical family.

## v2.8.4 — Compare display clarity

The Compare screen no longer shows an ambiguous `n=` badge.

Each group now displays:
- observed probability;
- numerator = event records;
- denominator = total qualifying records.

Example:
`57 event records / 136 total qualifying records`

## v3.0
- Boolean query builder with AND / OR / NOT
- Temporal trends by year, month, weekday, hour, and 4-hour block
- Improved Compare with numerator/denominator, Wilson intervals, difference in proportions CI, risk ratio, and odds ratio
- One-click PDF executive brief export
- Dedicated concurrency tab
- Preserves quick buttons, enriched concurrency, All clinical choice, and A-Shift branding


## v3.0.1
- Added concise in-app User Guide to Methods / Audit.
- Added Version Notes section.

## v3.0.2

- Fixed stray `NULL` / list rendering in **Audit / Show Math**.
- Audit sections now suppress invalid or empty filter objects.
- PDF label export now filters out null labels.

## v3.0.3

- Fixed Boolean audit `NULL` rendering at its source.
- Replaced Streamlit list-comprehension side effects with ordinary `for` loops.
- Boolean Event and Condition labels now render only as clean Markdown bullets.


## v3.1.0 — mobile deployment
- Sidebar collapsed by default.
- Touch-sized controls and two-across Quick Buttons.
- Horizontally scrollable tab navigation.
- 2×2 result metric layout.
- Stacked export controls.
- Phone-friendly Boolean Builder and Compare inputs.

### Deploy for iPhone / Android
Deploy to Streamlit Community Cloud or an authenticated department/intranet server, then open the HTTPS app URL on the phone.

**iPhone / iPad:** Safari → Share → **Add to Home Screen**.

**Android:** Chrome → menu → **Add to Home screen** / **Install app**.

No native App Store package is required; this remains a responsive Streamlit web app.
