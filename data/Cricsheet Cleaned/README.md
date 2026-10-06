# BBL data files for FIT3179 DV2

Made from 662 Cricsheet Big Bash League match files (BBL|01 2011/12 to BBL|15 2025/26) by `process_bbl.py`.
To rebuild: `python process_bbl.py <folder of json files> <output folder>`

## Files and which chart they feed

| File | Chart | One row per |
|---|---|---|
| `matches.csv` | Master table (join source) | match |
| `01_venues.csv` | 1. Proportional symbol map | venue (all seasons) |
| `01_venue_seasons.csv` | 1. Season slider version | venue × season |
| `02_state_matches.csv` | 2. Choropleth | state (join to ABS boundaries on `state_name`) |
| `03_team_seasons.csv` | 3. Heatmap, team × season | team × season |
| `04_home_away.csv` | 4. Dumbbell | team |
| `05_travel_flows.csv` | 5. Flow map (`rule` from home_lat/lon to venue_lat/lon) | team × season × away venue |
| `05_travel_totals.csv` | 5. Companion bar or tooltip | team × season |
| `06_innings_totals.csv` | 6. Ridgeline (filter `innings = 1` and `full_20_overs = 1`) | innings |
| `07_runs_per_over.csv` | 7. Heatmap, over × season | season × over |
| `08_phase_share.csv` | 8. Radial chart | season × phase |
| `09_bbl15_ladder_by_day.csv` | 9. Bump chart | match day × team |
| `10_bbl15_team_styles.csv` | 10. Parallel coordinates | team |
| `11_bbl15_final_worm.csv` | 11. Worm chart (x = `ball_in_innings`, y = `cumulative_runs`) | delivery |
| `12_batters_by_season.csv` | 12. Bubble chart (filter e.g. `balls >= 100`) | batter × team × season |

## Definitions and choices

- **Overs** are numbered 1 to 20 (Cricsheet starts at 0).
- **Legal balls** exclude wides and no-balls. **Balls faced** by a batter exclude wides only.
- **Super overs** are excluded from all run and ball counts; a tied match is credited to the super-over winner.
- **Retired hurt** is not counted as a wicket or an out.
- **Phases** are fixed bands: overs 1–6, 7–15 and 16–20. They are not called "powerplay" because the BBL powerplay rules changed from BBL|08 (power surge).
- **Home team**: the venue's main tenant if they played; otherwise the only team from that state; otherwise neutral (33 matches, mostly finals and hub games). Column `home_method` says which rule applied.
- **Finish** (`03_team_seasons.csv`): Champion, Runner-up, Finals, or Missed finals, from finals results. League W/L excludes finals.
- **Travel**: straight-line distance from the team's main home ground to each away venue, assuming a return trip for each match. It is a simplification, not actual itineraries.
- **Ladder** (`09`): 2 points for a win, 1 for a no result, ties broken on net run rate. The final positions and points match the official BBL|15 table.
- **Venue names** are tidied to one name per ground (e.g. Docklands Stadium = Marvel Stadium; Kardinia Park = GMHBA/Simonds Stadium; York Park = UTAS Stadium). Coordinates are approximate.

## Known limitations

- Cricsheet has fewer matches than were played for some early seasons (e.g. 27 for BBL|01, which had 31). Use rates and percentages rather than raw season counts where possible.
- Net run rates for BBL|15 match the official figures for six teams; Renegades and Thunder differ by a few hundredths because of how reduced-overs innings are counted. Positions are unaffected.

## Sources and licences

- Cricsheet, Big Bash League match data, https://cricsheet.org/downloads/ — Open Data Commons Attribution License (ODC-BY 1.0). Credit Cricsheet on your page.
- Australian Bureau of Statistics, *National, state and territory population, March 2026* (released 17 September 2026), https://www.abs.gov.au/statistics/people/population/national-state-and-territory-population/latest-release — CC BY 4.0.
- Venue coordinates: OpenStreetMap contributors (ODbL) — check and cite.
