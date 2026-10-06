"""
Process Cricsheet Big Bash League JSON files into small CSVs for Vega-Lite.

Usage:
    python process_bbl.py <folder_of_cricsheet_json> <output_folder>

Data: Cricsheet (https://cricsheet.org), ODC-BY 1.0 licence.
Population: ABS, National, state and territory population, March 2026 (CC BY 4.0).
"""
import csv
import glob
import json
import math
import os
import sys
from collections import defaultdict

SRC, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------
TEAMS = {
    # team: (abbrev, home state, main home venue, colour)
    "Adelaide Strikers":   ("STR", "SA",  "Adelaide Oval",                "#0085CA"),
    "Brisbane Heat":       ("HEA", "QLD", "The Gabba",                    "#00B2A9"),
    "Hobart Hurricanes":   ("HUR", "TAS", "Bellerive Oval",               "#6A2C91"),
    "Melbourne Renegades": ("REN", "VIC", "Docklands Stadium",            "#E4002B"),
    "Melbourne Stars":     ("STA", "VIC", "Melbourne Cricket Ground",     "#00843D"),
    "Perth Scorchers":     ("SCO", "WA",  "Perth Stadium",                "#F58220"),
    "Sydney Sixers":       ("SIX", "NSW", "Sydney Cricket Ground",        "#E5007E"),
    "Sydney Thunder":      ("THU", "NSW", "Sydney Showground Stadium",    "#B5D334"),
}

# Raw Cricsheet venue name -> clean venue name
VENUE_ALIASES = {
    "Docklands Stadium, Melbourne": "Docklands Stadium",
    "Bellerive Oval, Hobart": "Bellerive Oval",
    "Brisbane Cricket Ground, Woolloongabba": "The Gabba",
    "Brisbane Cricket Ground, Woolloongabba, Brisbane": "The Gabba",
    "Brisbane Cricket Ground": "The Gabba",
    "Western Australia Cricket Association Ground": "WACA Ground",
    "W.A.C.A. Ground": "WACA Ground",
    "Manuka Oval, Canberra": "Manuka Oval",
    "GMHBA Stadium, South Geelong, Victoria": "Kardinia Park",
    "Simonds Stadium, South Geelong, Victoria": "Kardinia Park",
    "Geelong Cricket Ground": "Kardinia Park",
    "Aurora Stadium": "York Park",
    "Aurora Stadium, Launceston": "York Park",
    "University of Tasmania Stadium, Launceston": "York Park",
    "International Sports Stadium, Coffs Harbour": "C.ex Coffs International Stadium",
    "International Sports Stadium": "C.ex Coffs International Stadium",
    "Junction Oval, Melbourne": "Junction Oval",
    "Lavington Sports Oval, Albury": "Lavington Sports Oval",
    "North Sydney Oval, Sydney": "North Sydney Oval",
    "Cazaly's Stadium, Cairns": "Cazaly's Stadium",
}

# clean venue: (city, state, lat, lon, primary tenant or None)
# Coordinates are approximate (to about 100 m), from each ground's OpenStreetMap location.
VENUES = {
    "Adelaide Oval":                    ("Adelaide", "SA", -34.9156, 138.5961, "Adelaide Strikers"),
    "Melbourne Cricket Ground":         ("Melbourne", "VIC", -37.8200, 144.9834, "Melbourne Stars"),
    "Docklands Stadium":                ("Melbourne", "VIC", -37.8165, 144.9475, "Melbourne Renegades"),
    "Perth Stadium":                    ("Perth", "WA", -31.9512, 115.8890, "Perth Scorchers"),
    "WACA Ground":                      ("Perth", "WA", -31.9600, 115.8797, "Perth Scorchers"),
    "Sydney Cricket Ground":            ("Sydney", "NSW", -33.8915, 151.2249, "Sydney Sixers"),
    "Sydney Showground Stadium":        ("Sydney", "NSW", -33.8430, 151.0670, "Sydney Thunder"),
    "Stadium Australia":                ("Sydney", "NSW", -33.8470, 151.0634, "Sydney Thunder"),
    "Bellerive Oval":                   ("Hobart", "TAS", -42.8770, 147.3730, "Hobart Hurricanes"),
    "York Park":                        ("Launceston", "TAS", -41.4258, 147.1388, "Hobart Hurricanes"),
    "The Gabba":                        ("Brisbane", "QLD", -27.4858, 153.0381, "Brisbane Heat"),
    "Carrara Oval":                     ("Gold Coast", "QLD", -28.0063, 153.3667, "Brisbane Heat"),
    "Cazaly's Stadium":                 ("Cairns", "QLD", -16.9360, 145.7490, "Brisbane Heat"),
    "Manuka Oval":                      ("Canberra", "ACT", -35.3181, 149.1347, "Sydney Thunder"),
    "Kardinia Park":                    ("Geelong", "VIC", -38.1580, 144.3546, "Melbourne Renegades"),
    "Junction Oval":                    ("Melbourne", "VIC", -37.8545, 144.9790, "Melbourne Stars"),
    "Ted Summerton Reserve":            ("Moe", "VIC", -38.1730, 146.2550, "Melbourne Stars"),
    "C.ex Coffs International Stadium": ("Coffs Harbour", "NSW", -30.3196, 153.1003, "Sydney Sixers"),
    "North Sydney Oval":                ("Sydney", "NSW", -33.8360, 151.2075, "Sydney Sixers"),
    "Lavington Sports Oval":            ("Albury", "NSW", -36.0423, 146.9417, "Sydney Thunder"),
    "Traeger Park":                     ("Alice Springs", "NT", -23.7040, 133.8720, "Adelaide Strikers"),
}

# ABS, National, state and territory population, March 2026 (persons, '000)
POPULATION_000 = {
    "NSW": 8670.1, "VIC": 7154.2, "QLD": 5739.5, "SA": 1916.8,
    "WA": 3096.2, "TAS": 580.7, "NT": 268.9, "ACT": 489.7,
}
STATE_NAMES = {
    "NSW": "New South Wales", "VIC": "Victoria", "QLD": "Queensland",
    "SA": "South Australia", "WA": "Western Australia", "TAS": "Tasmania",
    "NT": "Northern Territory", "ACT": "Australian Capital Territory",
}

FINAL_STAGES = {"Final", "Semi Final", "Knockout", "Qualifier", "Challenger", "Eliminator"}


def season_label(s):
    """'2025/26' -> 'BBL|15'"""
    return f"BBL|{int(s[:4]) - 2010:02d}"


def phase(over_no):
    if over_no <= 6:
        return "Overs 1-6"
    if over_no <= 15:
        return "Overs 7-15"
    return "Overs 16-20"


def km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def write(name, rows, fields=None):
    rows = list(rows)
    fields = fields or list(rows[0].keys())
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  {name:28s} {len(rows):>6} rows")


def is_legal(d):
    ex = d.get("extras", {})
    return "wides" not in ex and "noballs" not in ex


# ---------------------------------------------------------------------------
# Pass over every match
# ---------------------------------------------------------------------------
matches, innings_rows, over_rows, batting = [], [], [], defaultdict(lambda: defaultdict(float))
team_bat = defaultdict(lambda: defaultdict(float))   # (season, team) batting by phase
team_bowl = defaultdict(lambda: defaultdict(float))  # (season, team) bowling
worm = {}  # match_id -> rows (kept for finals)
unknown_venues = set()

for path in sorted(glob.glob(os.path.join(SRC, "*.json"))):
    mid = os.path.basename(path)[:-5]
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    info = d["info"]
    season = info["season"]
    raw_venue = info["venue"]
    venue = VENUE_ALIASES.get(raw_venue, raw_venue)
    if venue not in VENUES:
        unknown_venues.add(raw_venue)
        continue
    city, state, lat, lon, tenant = VENUES[venue]
    t1, t2 = info["teams"]
    stage = info.get("event", {}).get("stage", "League")
    outcome = info["outcome"]
    winner = outcome.get("winner") or outcome.get("eliminator")
    result = ("won" if "winner" in outcome else
              "tie (super over)" if "eliminator" in outcome else outcome.get("result", ""))
    margin = outcome.get("by", {})
    margin_txt = (f"{margin['runs']} runs" if "runs" in margin else
                  f"{margin['wickets']} wickets" if "wickets" in margin else "")

    # Home team: the venue's tenant if playing, otherwise the only team from that state
    if tenant in (t1, t2):
        home, method = tenant, "tenant"
    else:
        local = [t for t in (t1, t2) if TEAMS[t][1] == state]
        home, method = (local[0], "state") if len(local) == 1 else ("", "neutral")

    # ---- innings -----------------------------------------------------------
    inn_summ = []
    for idx, inn in enumerate(d["innings"], start=1):
        if inn.get("super_over"):
            continue
        bat_team = inn["team"]
        bowl_team = t2 if bat_team == t1 else t1
        runs = wkts = legal = 0
        allotted = inn.get("target", {}).get("overs", info.get("overs", 20))
        per_over = defaultdict(lambda: [0, 0, 0])  # runs, wickets, legal balls
        worm_rows = []
        for ov in inn["overs"]:
            o = ov["over"] + 1
            for dl in ov["deliveries"]:
                r = dl["runs"]["total"]
                runs += r
                legal_ball = is_legal(dl)
                legal += legal_ball
                w = [x for x in dl.get("wickets", []) if x["kind"] != "retired hurt"]
                wkts += len(w)
                per_over[o][0] += r
                per_over[o][1] += len(w)
                per_over[o][2] += legal_ball

                # batter stats (balls faced = everything except wides)
                b = batting[(season, dl["batter"], bat_team)]
                b["runs"] += dl["runs"]["batter"]
                if "wides" not in dl.get("extras", {}):
                    b["balls"] += 1
                if dl["runs"]["batter"] == 4 and not dl["runs"].get("non_boundary"):
                    b["fours"] += 1
                if dl["runs"]["batter"] == 6:
                    b["sixes"] += 1
                for x in w:
                    batting[(season, x["player_out"], bat_team)]["outs"] += 1

                # team phase stats
                ph = phase(o)
                tb = team_bat[(season, bat_team)]
                tb[f"runs_{ph}"] += r
                tb[f"balls_{ph}"] += legal_ball
                tb["boundaries"] += dl["runs"]["batter"] in (4, 6)
                tb["balls"] += legal_ball
                bw = team_bowl[(season, bowl_team)]
                bw["runs_conceded"] += r
                bw["balls_bowled"] += legal_ball
                bw["wickets"] += len(w)
                bw[f"runs_{ph}"] += r
                bw[f"balls_{ph}"] += legal_ball

                worm_rows.append({
                    "match_id": mid, "innings": idx, "team": bat_team,
                    "over": o, "ball_in_innings": legal, "delivery": dl.get("actual_delivery", ""),
                    "runs_on_ball": r, "cumulative_runs": runs, "wicket": int(bool(w)),
                    "cumulative_wickets": wkts, "batter": dl["batter"], "bowler": dl["bowler"],
                    "player_out": w[0]["player_out"] if w else "",
                })
        # batter innings count
        seen = set()
        for ov in inn["overs"]:
            for dl in ov["deliveries"]:
                for p in (dl["batter"], dl["non_striker"]):
                    if p not in seen:
                        seen.add(p)
                        batting[(season, p, bat_team)]["innings"] += 1

        all_out = wkts >= 10
        overs_for_nrr = allotted if all_out else legal / 6
        inn_summ.append((bat_team, runs, overs_for_nrr))
        innings_rows.append({
            "match_id": mid, "season": season, "season_label": season_label(season),
            "date": info["dates"][0], "venue": venue, "innings": idx,
            "batting_team": bat_team, "bowling_team": bowl_team,
            "runs": runs, "wickets": wkts, "legal_balls": legal,
            "overs": f"{legal // 6}.{legal % 6}", "allotted_overs": allotted,
            "all_out": int(all_out), "full_20_overs": int(allotted == 20),
            "stage": stage,
        })
        for o, (r, w, lb) in per_over.items():
            over_rows.append({"season": season, "season_label": season_label(season),
                              "over": o, "runs": r, "wickets": w, "legal_balls": lb})
        worm[(mid, idx)] = worm_rows

    first = inn_summ[0] if inn_summ else ("", 0, 0)
    second = inn_summ[1] if len(inn_summ) > 1 else ("", 0, 0)
    matches.append({
        "match_id": mid, "season": season, "season_label": season_label(season),
        "date": info["dates"][0], "stage": stage,
        "is_final_series": int(stage in FINAL_STAGES),
        "venue": venue, "city": city, "state": state, "lat": lat, "lon": lon,
        "team1": t1, "team2": t2, "home_team": home, "home_method": method,
        "toss_winner": info["toss"]["winner"], "toss_decision": info["toss"]["decision"],
        "result": result, "winner": winner or "", "margin": margin_txt,
        "method": outcome.get("method", ""),
        "bat_first": first[0], "bat_first_runs": first[1],
        "bat_second": second[0], "bat_second_runs": second[1],
        "_nrr": inn_summ,
    })

if unknown_venues:
    print("WARNING: venues not in lookup (matches skipped):", unknown_venues)

matches.sort(key=lambda m: (m["date"], m["match_id"]))
print(f"Processed {len(matches)} matches\n")
print("Writing CSVs:")

# 00 master match table ------------------------------------------------------
write("matches.csv", ({k: v for k, v in m.items() if k != "_nrr"} for m in matches))

# 01 venues (proportional symbol map) ----------------------------------------
vcount, vseason = defaultdict(int), defaultdict(int)
vfirst, vlast = {}, {}
for m in matches:
    v = m["venue"]
    vcount[v] += 1
    vseason[(v, m["season"])] += 1
    vfirst[v] = min(vfirst.get(v, m["season"]), m["season"])
    vlast[v] = max(vlast.get(v, m["season"]), m["season"])
write("01_venues.csv", (
    {"venue": v, "city": c, "state": s, "lat": la, "lon": lo, "tenant": t,
     "tenant_colour": TEAMS[t][3], "matches": vcount[v],
     "first_season": vfirst[v], "last_season": vlast[v]}
    for v, (c, s, la, lo, t) in VENUES.items() if vcount[v]))
write("01_venue_seasons.csv", (
    {"venue": v, "season": s, "season_label": season_label(s), "lat": VENUES[v][2],
     "lon": VENUES[v][3], "tenant": VENUES[v][4], "matches": n}
    for (v, s), n in sorted(vseason.items())))

# 02 state choropleth --------------------------------------------------------
scount = defaultdict(int)
for m in matches:
    scount[m["state"]] += 1
write("02_state_matches.csv", (
    {"state": s, "state_name": STATE_NAMES[s], "matches": scount.get(s, 0),
     "population": int(POPULATION_000[s] * 1000),
     "matches_per_million": round(scount.get(s, 0) / (POPULATION_000[s] / 1000), 1)}
    for s in POPULATION_000))

# 03 team-season heatmap -----------------------------------------------------
ts = defaultdict(lambda: {"played": 0, "won": 0, "lost": 0, "no_result": 0, "finals": 0})
champ, runner = {}, {}
for m in matches:
    for t in (m["team1"], m["team2"]):
        r = ts[(m["season"], t)]
        if m["is_final_series"]:
            r["finals"] = 1
            continue
        r["played"] += 1
        if m["result"] == "no result":
            r["no_result"] += 1
        elif m["winner"] == t:
            r["won"] += 1
        else:
            r["lost"] += 1
    if m["stage"] == "Final":
        champ[m["season"]] = m["winner"]
        runner[m["season"]] = m["team2"] if m["winner"] == m["team1"] else m["team1"]


def finish(season, team, r):
    if champ.get(season) == team:
        return "Champion", 4
    if runner.get(season) == team:
        return "Runner-up", 3
    if r["finals"]:
        return "Finals", 2
    return "Missed finals", 1


rows = []
for (s, t), r in sorted(ts.items()):
    f, rank = finish(s, t, r)
    decided = r["won"] + r["lost"]
    rows.append({"season": s, "season_label": season_label(s), "team": t,
                 "abbrev": TEAMS[t][0], "league_played": r["played"],
                 "league_won": r["won"], "league_lost": r["lost"],
                 "league_no_result": r["no_result"],
                 "league_win_pct": round(100 * r["won"] / decided, 1) if decided else "",
                 "finish": f, "finish_rank": rank})
write("03_team_seasons.csv", rows)

# 04 home vs away (dumbbell) -------------------------------------------------
ha = defaultdict(lambda: defaultdict(int))
for m in matches:
    if not m["home_team"] or m["result"] == "no result":
        continue
    for t in (m["team1"], m["team2"]):
        side = "home" if t == m["home_team"] else "away"
        ha[t][f"{side}_played"] += 1
        ha[t][f"{side}_won"] += m["winner"] == t
write("04_home_away.csv", (
    {"team": t, "abbrev": TEAMS[t][0], "colour": TEAMS[t][3],
     "home_played": r["home_played"], "home_won": r["home_won"],
     "home_win_pct": round(100 * r["home_won"] / r["home_played"], 1),
     "away_played": r["away_played"], "away_won": r["away_won"],
     "away_win_pct": round(100 * r["away_won"] / r["away_played"], 1),
     "gap_pct_points": round(100 * (r["home_won"] / r["home_played"] - r["away_won"] / r["away_played"]), 1)}
    for t, r in sorted(ha.items())))

# 05 travel flows (flow map) -------------------------------------------------
flows, totals = defaultdict(int), defaultdict(float)
for m in matches:
    for t in (m["team1"], m["team2"]):
        hv = TEAMS[t][2]
        if m["venue"] == hv:
            continue
        flows[(t, m["season"], m["venue"])] += 1
rows = []
for (t, s, v), n in sorted(flows.items()):
    hv = VENUES[TEAMS[t][2]]
    vv = VENUES[v]
    dist = km(hv[2], hv[3], vv[2], vv[3])
    totals[(t, s)] += 2 * dist * n
    rows.append({"team": t, "abbrev": TEAMS[t][0], "colour": TEAMS[t][3],
                 "season": s, "season_label": season_label(s),
                 "home_venue": TEAMS[t][2], "home_lat": hv[2], "home_lon": hv[3],
                 "venue": v, "venue_lat": vv[2], "venue_lon": vv[3],
                 "trips": n, "km_one_way": round(dist)})
write("05_travel_flows.csv", rows)
write("05_travel_totals.csv", (
    {"team": t, "abbrev": TEAMS[t][0], "season": s, "season_label": season_label(s),
     "return_km": round(k)} for (t, s), k in sorted(totals.items())))

# 06 innings totals (ridgeline) ----------------------------------------------
write("06_innings_totals.csv", innings_rows)

# 07 runs per over (heatmap) -------------------------------------------------
agg = defaultdict(lambda: [0, 0, 0, 0])
for r in over_rows:
    a = agg[(r["season"], r["over"])]
    a[0] += r["runs"]; a[1] += r["wickets"]; a[2] += r["legal_balls"]; a[3] += 1
write("07_runs_per_over.csv", (
    {"season": s, "season_label": season_label(s), "over": o, "overs_bowled": n,
     "avg_runs": round(ru / n, 2), "run_rate": round(6 * ru / lb, 2) if lb else "",
     "wickets_per_100_overs": round(100 * w / n, 1)}
    for (s, o), (ru, w, lb, n) in sorted(agg.items())))

# 08 phase share (radial) ----------------------------------------------------
ph = defaultdict(lambda: defaultdict(int))
for r in over_rows:
    ph[r["season"]][phase(r["over"])] += r["runs"]
rows = []
for s, d_ in sorted(ph.items()):
    tot = sum(d_.values())
    for p in ("Overs 1-6", "Overs 7-15", "Overs 16-20"):
        rows.append({"season": s, "season_label": season_label(s), "phase": p,
                     "runs": d_[p], "share_pct": round(100 * d_[p] / tot, 1)})
write("08_phase_share.csv", rows)

# 09 BBL|15 ladder after each match day (bump chart) -------------------------
LATEST = max(m["season"] for m in matches)
league = [m for m in matches if m["season"] == LATEST and not m["is_final_series"]]
st = {t: {"P": 0, "W": 0, "L": 0, "NR": 0, "pts": 0, "rf": 0, "of": 0.0, "ra": 0, "ob": 0.0}
      for t in TEAMS}
rows = []
dates = sorted({m["date"] for m in league})
for day in dates:
    for m in (x for x in league if x["date"] == day):
        for t in (m["team1"], m["team2"]):
            s_ = st[t]
            s_["P"] += 1
            if m["result"] == "no result":
                s_["NR"] += 1; s_["pts"] += 1
                continue
            if m["winner"] == t:
                s_["W"] += 1; s_["pts"] += 2
            else:
                s_["L"] += 1
            for bat, runs, ovs in m["_nrr"]:
                if bat == t:
                    s_["rf"] += runs; s_["of"] += ovs
                else:
                    s_["ra"] += runs; s_["ob"] += ovs

    def nrr(s_):
        return (s_["rf"] / s_["of"] - s_["ra"] / s_["ob"]) if s_["of"] and s_["ob"] else 0.0

    order = sorted(TEAMS, key=lambda t: (-st[t]["pts"], -nrr(st[t])))
    for pos, t in enumerate(order, start=1):
        rows.append({"date": day, "team": t, "abbrev": TEAMS[t][0], "colour": TEAMS[t][3],
                     "played": st[t]["P"], "won": st[t]["W"], "lost": st[t]["L"],
                     "no_result": st[t]["NR"], "points": st[t]["pts"],
                     "nrr": round(nrr(st[t]), 3), "position": pos})
write("09_bbl15_ladder_by_day.csv", rows)
final_ladder = rows[-8:]

# 10 BBL|15 team styles (parallel coordinates) -------------------------------
rows = []
for t in TEAMS:
    b, w = team_bat[(LATEST, t)], team_bowl[(LATEST, t)]
    games = sum(1 for m in matches if m["season"] == LATEST and t in (m["team1"], m["team2"]))
    rr = lambda runs, balls: round(6 * runs / balls, 2) if balls else ""
    rows.append({
        "team": t, "abbrev": TEAMS[t][0], "colour": TEAMS[t][3], "matches": games,
        "bat_rr_overs_1_6": rr(b["runs_Overs 1-6"], b["balls_Overs 1-6"]),
        "bat_rr_overs_7_15": rr(b["runs_Overs 7-15"], b["balls_Overs 7-15"]),
        "bat_rr_overs_16_20": rr(b["runs_Overs 16-20"], b["balls_Overs 16-20"]),
        "boundary_pct": round(100 * b["boundaries"] / b["balls"], 1),
        "bowl_economy": rr(w["runs_conceded"], w["balls_bowled"]),
        "bowl_economy_overs_16_20": rr(w["runs_Overs 16-20"], w["balls_Overs 16-20"]),
        "wickets_per_match": round(w["wickets"] / games, 2),
    })
write("10_bbl15_team_styles.csv", rows)

# 11 BBL|15 final, ball by ball (worm chart) ---------------------------------
fin = next(m for m in matches if m["season"] == LATEST and m["stage"] == "Final")
write("11_bbl15_final_worm.csv", worm[(fin["match_id"], 1)] + worm[(fin["match_id"], 2)])

# 12 batters per season (bubble chart) ---------------------------------------
rows = []
for (s, p, t), b in batting.items():
    if b["balls"] == 0:
        continue
    rows.append({"season": s, "season_label": season_label(s), "batter": p, "team": t,
                 "abbrev": TEAMS[t][0], "colour": TEAMS[t][3],
                 "innings": int(b["innings"]), "runs": int(b["runs"]), "balls": int(b["balls"]),
                 "outs": int(b["outs"]), "fours": int(b["fours"]), "sixes": int(b["sixes"]),
                 "average": round(b["runs"] / b["outs"], 2) if b["outs"] else "",
                 "strike_rate": round(100 * b["runs"] / b["balls"], 1)})
rows.sort(key=lambda r: (r["season"], -r["runs"]))
write("12_batters_by_season.csv", rows)

# ---------------------------------------------------------------------------
print(f"\n{season_label(LATEST)} final: {fin['team1']} v {fin['team2']}, "
      f"winner {fin['winner']} by {fin['margin']} ({fin['date']}, {fin['venue']})")
print(f"{season_label(LATEST)} ladder computed from data:")
for r in final_ladder:
    print(f"  {r['position']}. {r['team']:20s} P{r['played']} W{r['won']} L{r['lost']} "
          f"NR{r['no_result']} Pts {r['points']}  NRR {r['nrr']:+.3f}")
