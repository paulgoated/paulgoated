#!/usr/bin/env python3
"""
Generator kartu profil GitHub — tema "signal / datasheet".

Pemakaian:
  python generate.py            # data asli via GitHub GraphQL (butuh env GITHUB_TOKEN)
  python generate.py --sample   # data contoh untuk preview lokal (angka TIDAK asli)

Output: cards/*.svg  — tanpa dependency eksternal (standard library saja).
"""
import base64, datetime as dt, html, json, math, os, random, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"
OUT = ROOT / "cards"
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
T = CFG["theme"]
METRICS = {k: {int(w): m for w, m in v.items()} for k, v in json.loads((ASSETS / "metrics.json").read_text()).items()}
SANS = base64.b64encode((ASSETS / "geist-sans.woff2").read_bytes()).decode()
MONO = base64.b64encode((ASSETS / "geist-mono.woff2").read_bytes()).decode()
W = 840

# ------------------------------------------------------------------ util
def esc(s): return html.escape(str(s), quote=True)

def tw(s, size, weight=400, mono=False, ls=0):
    m = METRICS["mono" if mono else "sans"]
    m = m[min(m, key=lambda k: abs(k - weight))]
    return sum(m.get(ch, 0.6) for ch in str(s)) * size + ls * len(str(s))

def wrap(s, size, weight, max_w):
    lines, cur = [], ""
    for word in str(s).split():
        t = (cur + " " + word).strip()
        if tw(t, size, weight) <= max_w or not cur: cur = t
        else: lines.append(cur); cur = word
    if cur: lines.append(cur)
    return lines

def txt(x, y, s, size, weight=400, fill=None, anchor="start", mono=False, ls=0, op=1):
    fill = fill or T["text"]
    a = f' letter-spacing="{ls}"' if ls else ""
    o = f' opacity="{op}"' if op != 1 else ""
    cls = ' class="m"' if mono else ""
    return (f'<text{cls} x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}"{a}{o}>{esc(s)}</text>')

def rect(x, y, w, h, fill="none", stroke=None, rx=0, sw=1, dash=None, op=1):
    st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    da = f' stroke-dasharray="{dash}"' if dash else ""
    o = f' opacity="{op:.3f}"' if op != 1 else ""
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}"{st}{da}{o}/>'

def line(x1, y1, x2, y2, stroke=None, sw=1, dash=None):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke or T["border"]}" stroke-width="{sw}"{da}/>'

def ticks(w, h, m=10, L=14):
    """Tanda sudut ala crop-mark — ciri khas tema ini."""
    c = T["accent"]; p = []
    for x, y, dx, dy in [(m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)]:
        p.append(f'<path d="M{x},{y + dy * L} L{x},{y} L{x + dx * L},{y}" fill="none" stroke="{c}" stroke-width="2"/>')
    return "".join(p)

def head(no, title, w=W, right=None):
    out = txt(40, 46, f"{no:02d}", 12, 500, T["accent"], mono=True, ls=1)
    out += txt(68, 46, "— " + title.upper(), 12, 500, T["muted"], mono=True, ls=1.5)
    if right: out += txt(w - 40, 46, right, 12, 500, T["dim"], "end", mono=True, ls=1)
    out += line(40, 62, w - 40, 62)
    return out

SCAN = 3.6  # durasi satu sapuan playhead MFCC (detik)
ANIM_CSS = f"""
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.2}}}}
@keyframes blink{{0%,55%{{opacity:1}}56%,100%{{opacity:0}}}}
@keyframes grow{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
@keyframes growx{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
@keyframes fadeup{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
@keyframes col{{0%{{opacity:1}}25%,100%{{opacity:.42}}}}
@keyframes scan{{from{{transform:translateX(0)}}to{{transform:translateX(272px)}}}}
@keyframes nudge{{0%,70%,100%{{transform:none}}80%{{transform:translate(3px,-3px)}}}}
.pulse{{animation:pulse 1.8s ease-in-out infinite}}
.blink{{animation:blink 1.1s step-end infinite}}
.grow{{transform-box:fill-box;transform-origin:50% 100%;animation:grow .9s cubic-bezier(.2,.8,.2,1) both}}
.growx{{transform-box:fill-box;transform-origin:0 50%;animation:growx 1.1s cubic-bezier(.2,.8,.2,1) both}}
.fade{{animation:fadeup .6s cubic-bezier(.2,.8,.2,1) both}}
.col{{animation:col {SCAN}s linear infinite}}
.scan{{animation:scan {SCAN}s linear infinite}}
.nudge{{transform-box:fill-box;animation:nudge 2.4s ease-in-out infinite}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}"""

def anim(inner, cls, delay=0.0):
    if not CFG.get("animate", True): return inner
    st = f' style="animation-delay:{delay:.2f}s"' if delay else ""
    return f'<g class="{cls}"{st}>{inner}</g>'

def svg(w, h, body, title):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">
<style>@font-face{{font-family:"GS";src:url(data:font/woff2;base64,{SANS}) format("woff2");font-weight:100 900}}
@font-face{{font-family:"GM";src:url(data:font/woff2;base64,{MONO}) format("woff2");font-weight:100 900}}
text{{font-family:"GS",ui-sans-serif,system-ui,sans-serif}} .m{{font-family:"GM",ui-monospace,monospace}}{ANIM_CSS if CFG.get("animate", True) else ""}</style>
<defs><pattern id="g" width="16" height="16" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.8" fill="{T["grid"]}"/></pattern></defs>
{rect(0.5, 0.5, w - 1, h - 1, T["bg"], T["border"], 18)}
{rect(0.5, 0.5, w - 1, h - 1, "url(#g)", None, 18)}
{ticks(w, h)}
{body}
</svg>'''

# ------------------------------------------------------------------ kartu
def mfcc_cells(cols, rows, seed=3):
    """Heatmap dekoratif mirip MFCC: pita energi di koefisien rendah + 'tangisan' yang naik turun."""
    rnd = random.Random(seed); out = []
    for c in range(cols):
        burst = 0.55 + 0.45 * math.sin(c / cols * math.pi * 3.2) ** 2
        for r in range(rows):
            low = math.exp(-r / 5.5)
            formant = math.exp(-((r - 7 - 3 * math.sin(c / 6)) ** 2) / 6)
            v = (0.65 * low + 0.55 * formant) * burst + 0.12 * rnd.random()
            out.append((c, r, max(0.04, min(1, v))))
    return out

def card_hero(d):
    H = 306; c = dict(CFG["hero"]); p = d["profile"]; b = []
    c["name"] = c.get("name") or p["login"]
    c["bio"] = c.get("bio") or p.get("bio") or ""
    loc = (p.get("location") or c.get("location_fallback") or "").upper()
    status = c["status"].replace("{location}", loc).replace(" ·  · ", " · ")
    b.append(anim(f'<circle cx="46" cy="44" r="4" fill="{T["accent"]}"/>', "pulse"))
    b.append(txt(58, 48, status, 12, 500, T["muted"], mono=True, ls=1.2))
    # avatar kecil (opsional)
    nx = 40
    if d.get("avatar_b64"):
        b.append(f'<defs><clipPath id="av"><rect x="40" y="82" width="64" height="64" rx="14"/></clipPath></defs>'
                 f'<image href="data:image/png;base64,{d["avatar_b64"]}" x="40" y="82" width="64" height="64" clip-path="url(#av)" preserveAspectRatio="xMidYMid slice"/>'
                 + rect(40, 82, 64, 64, "none", T["border"], 14))
        nx = 122
    b.append(f'<text x="{nx}" y="136" font-size="64" font-weight="600" fill="{T["text"]}" letter-spacing="-2.5">'
             f'{esc(c["name"])}<tspan class="blink" fill="{T["accent"]}">.</tspan></text>')
    b.append(txt(40, 176, c["subtitle"], 13, 500, T["dim"], mono=True, ls=1))
    y = 206
    for ln in wrap(c["bio"], 16, 400, 430)[:2]:
        b.append(txt(40, y, ln, 16, 400, T["muted"])); y += 23
    x = 40
    for t in c["tags"]:
        w = tw(t, 12, 500, True, 1) + 24
        b.append(rect(x, 252, w, 26, T["panel"], T["border"], 6) + txt(x + 12, 269, t, 12, 500, T["text"], mono=True, ls=1))
        x += w + 8
    # panel MFCC
    px, py, cols, rows, cs = 520, 48, 34, 20, 8
    b.append(rect(px - 12, py - 12, cols * cs + 24, rows * cs + 52, T["panel"], T["border"], 10))
    colmap = {}
    for cc, r, v in mfcc_cells(cols, rows):
        colmap.setdefault(cc, []).append(rect(px + cc * cs, py + (rows - 1 - r) * cs, cs - 1.5, cs - 1.5, T["accent"], rx=1.5, op=v ** 1.6))
    for cc, cells in colmap.items():
        # tiap kolom menyala saat playhead lewat (delay negatif = sinkron dengan sapuan)
        b.append(anim("".join(cells), "col", cc / cols * SCAN - SCAN))
    if CFG.get("animate", True):
        b.append(f'<defs><linearGradient id="ph" x1="0" x2="1"><stop offset="0" stop-color="{T["accent"]}" stop-opacity="0"/>'
                 f'<stop offset="1" stop-color="{T["accent"]}" stop-opacity=".35"/></linearGradient></defs>')
        b.append(f'<g class="scan">{rect(px - 22, py - 4, 22, rows * cs + 6, "url(#ph)")}'
                 f'{rect(px - 1, py - 4, 2, rows * cs + 6, T["accent"], rx=1)}</g>')
    b.append(txt(px, py + rows * cs + 24, c["panel_caption"], 11, 500, T["dim"], mono=True, ls=0.8))
    b.append(anim(txt(px + cols * cs, py + rows * cs + 24, "● live", 11, 500, T["accent"], "end", mono=True), "pulse"))
    return svg(W, H, "".join(b), "Profile")

def card_spec():
    c = CFG["spec"]; rows = c["rows"]; H = 86 + len(rows) * 40 + 20
    b = [head(2, c["title"], right=f'{len(rows)} FIELDS')]
    y = 86
    for i, (k, v) in enumerate(rows):
        kw = tw(k.upper(), 12, 500, True, 1.5)
        vw = tw(v, 15, 500)
        row = (txt(40, y + 18, k.upper(), 12, 500, T["muted"], mono=True, ls=1.5)
               + line(40 + kw + 12, y + 14, W - 40 - vw - 12, y + 14, T["dim"], 1, "1 5")
               + txt(W - 40, y + 19, v, 15, 500, T["text"], "end"))
        b.append(anim(row, "fade", 0.15 + i * 0.09))
        y += 40
    return svg(W, H, "".join(b), c["title"])

def card_pinout(d):
    c = CFG["stack"]; b = [head(3, c["title"], right="PINOUT")]; y = 84
    groups = []
    for g in c["groups"]:
        if g.get("auto_languages"):
            auto = [n for n, _ in d["languages"][: g.get("max", 6)]]
            extra = [x for x in g.get("items", []) if x not in auto]
            g = {**g, "items": auto + extra}
        if g["items"]: groups.append(g)
    for g in groups:
        b.append(txt(40, y + 21, g["label"].upper(), 12, 500, T["accent"], mono=True, ls=1.5))
        x = 150; row_y = y
        for it in g["items"]:
            w = tw(it, 13, 500, True) + 38
            if x + w > W - 40: x = 150; row_y += 40
            k = len(b)
            led = anim(rect(x + 11, row_y + 12, 6, 6, T["accent"], rx=1), "pulse", (k * 0.37) % 1.8)
            b.append(anim(rect(x, row_y, w, 30, T["panel"], T["border"], 6) + led
                          + txt(x + 26, row_y + 20, it, 13, 500, T["text"], mono=True), "fade", 0.1 + k * 0.03))
            x += w + 8
        y = row_y + 46
        b.append(line(40, y - 8, W - 40, y - 8, T["border"], 1, "2 4"))
    H = y + 14
    return svg(W, H, "".join(b), c["title"])

def card_repo(r):
    w, H = 412, 210; b = []
    b.append(txt(28, 40, "04", 11, 500, T["accent"], mono=True, ls=1) + txt(50, 40, "— REPOSITORY", 11, 500, T["muted"], mono=True, ls=1.5))
    b.append(anim(txt(w - 28, 41, "↗", 16, 500, T["accent"], "end", mono=True), "nudge"))
    b.append(line(28, 54, w - 28, 54))
    b.append(txt(28, 92, r["name"], 24, 600, ls=-0.6))
    y = 120
    for ln in wrap(r.get("description") or "No description yet.", 14, 400, w - 56)[:2]:
        b.append(txt(28, y, ln, 14, 400, T["muted"])); y += 20
    b.append(rect(28, 172, 8, 8, T["accent"], rx=1.5))
    b.append(txt(44, 180, r.get("language") or "—", 12, 500, T["text"], mono=True))
    b.append(txt(w - 28, 180, f'★ {r.get("stars", 0)}', 12, 500, T["text"], "end", mono=True))
    return svg(w, H, "".join(b), r["name"])

def card_telemetry(d):
    H = 380; b = [head(5, "telemetry", right=f'UPDATED {d["today"]}')]
    pool = {"stars": (d["stars"], "STARS"), "contrib": (d["year_contrib"], f'CONTRIB {d["today"][:4]}'),
            "repos": (d["public_repos"], "PUBLIC REPOS"), "followers": (d["followers"], "FOLLOWERS"),
            "languages": (len(d["languages"]), "LANGUAGES"), "longest": (d["long_streak"], "BEST STREAK")}
    stats = [pool[k] for k in CFG.get("telemetry_tiles", ["stars", "contrib", "repos", "followers"])[:4]]
    cw = (W - 80) / 4
    for i, (v, lab) in enumerate(stats):
        x = 40 + i * cw
        if i: b.append(line(x, 82, x, 146))
        b.append(anim(txt(x + (16 if i else 0), 122, f"{v:,}", 38, 600, ls=-1)
                      + txt(x + (16 if i else 0), 144, lab, 11, 500, T["muted"], mono=True, ls=1.2), "fade", 0.1 + i * 0.12))
    # waveform 21 hari
    b.append(txt(40, 186, "LAST 21 DAYS", 11, 500, T["muted"], mono=True, ls=1.5))
    days = d["days21"]; mx = max([x["count"] for x in days] + [1])
    base_y, hmax, gap = 268, 66, 6
    bw = (W - 80 - gap * 20) / 21
    b.append(line(40, base_y + 0.5, W - 40, base_y + 0.5, T["border"]))
    for i, x in enumerate(days):
        bx = 40 + i * (bw + gap)
        future = x["date"] > d["today"]
        if future:
            b.append(rect(bx, base_y - 10, bw, 10, "none", T["dim"], 3, 1, "2 3"))
        elif x["count"] == 0:
            b.append(rect(bx, base_y - 3, bw, 3, T["dim"], rx=1.5))
        else:
            h = max(8, hmax * (x["count"] / mx) ** 0.75)
            bar = rect(bx, base_y - h, bw, h, T["accent"], rx=3, op=0.45 + 0.55 * x["count"] / mx)
            if x["date"] == d["today"]: bar = anim(bar, "pulse")
            b.append(anim(bar, "grow", 0.3 + i * 0.05))
        is_today = x["date"] == d["today"]
        b.append(txt(bx + bw / 2, base_y + 18, int(x["date"][-2:]), 10, 600 if is_today else 400,
                     T["accent"] if is_today else T["dim"], "middle", mono=True))
        if is_today:
            b.append(anim(txt(bx + bw / 2, base_y - hmax - 6, "today", 10, 500, T["accent"], "middle", mono=True), "pulse"))
    # bahasa
    langs = d["languages"][:5]; tot = sum(v for _, v in langs) or 1
    b.append(txt(40, 318, "LANGUAGES", 11, 500, T["muted"], mono=True, ls=1.5))
    ops = [1, 0.7, 0.5, 0.34, 0.22]; x = 40; avail = W - 80 - 4 * (len(langs) - 1)
    for i, (n, v) in enumerate(langs):
        sw = max(6, avail * v / tot)
        b.append(anim(rect(x, 328, sw, 8, T["accent"], rx=2, op=ops[i]), "growx", 1.2 + i * 0.15)); x += sw + 4
    x = 40
    for i, (n, v) in enumerate(langs):
        lab = f"{n} {100 * v / tot:.1f}%".replace(".0%", "%")
        b.append(rect(x, 352, 8, 8, T["accent"], rx=1.5, op=ops[i]) + txt(x + 14, 360, lab, 12, 500, T["text"], mono=True))
        x += 14 + tw(lab, 12, 500, True) + 22
    return svg(W, H, "".join(b), "Telemetry")

def card_signal(d):
    H = 200; b = [head(6, "signal strength", right="STREAK")]
    scale = max(30, d["long_streak"])
    for i, (v, lab) in enumerate([(d["cur_streak"], "CURRENT STREAK"), (d["long_streak"], f'LONGEST {d["today"][:4]}')]):
        y = 92 + i * 52
        b.append(txt(40, y + 14, lab, 11, 500, T["muted"], mono=True, ls=1.5))
        segs, x0, x1 = 40, 200, W - 150
        sw = (x1 - x0 - (segs - 1) * 3) / segs
        on = round(segs * v / scale)
        for s in range(segs):
            seg = rect(x0 + s * (sw + 3), y, sw, 18, T["accent"] if s < on else T["panel"],
                       None if s < on else T["border"], 2, op=(0.35 + 0.65 * (s + 1) / segs) if s < on else 1)
            if s < on:
                if s == on - 1: seg = anim(seg, "pulse", 1.5)
                seg = anim(seg, "grow", 0.3 + i * 0.4 + s * 0.04)
            b.append(seg)
        b.append(txt(W - 40, y + 16, f'{v} {"day" if v == 1 else "days"}', 18, 600, anchor="end"))
    return svg(W, H, "".join(b), "Streak")

# ------------------------------------------------------------------ data
def gql(query, variables):
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not tok: sys.exit("GITHUB_TOKEN belum di-set. Pakai --sample untuk preview.")
    req = urllib.request.Request("https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {tok}", "Content-Type": "application/json", "User-Agent": "profile-cards"})
    res = json.loads(urllib.request.urlopen(req, timeout=30).read())
    if res.get("errors"): sys.exit(f"GraphQL error: {res['errors']}")
    return res["data"]

CAL = "contributionCalendar{ totalContributions weeks{ contributionDays{ date contributionCount contributionLevel } } }"

def fetch(today):
    login = CFG["username"]
    year_from = f"{today[:4]}-01-01T00:00:00Z"
    q = f"""query($login:String!,$from:DateTime!){{ user(login:$login){{
      login name bio location avatarUrl(size:256) followers{{totalCount}} publicRepos: repositories(privacy:PUBLIC,ownerAffiliations:OWNER){{totalCount}}
      pinnedItems(first:6,types:REPOSITORY){{ nodes{{ ... on Repository{{ name description stargazerCount url isFork primaryLanguage{{name}} }} }} }}
      owned: repositories(ownerAffiliations:OWNER,isFork:false,privacy:PUBLIC,first:100,orderBy:{{field:PUSHED_AT,direction:DESC}}){{ nodes{{
        name description stargazerCount url primaryLanguage{{name}}
        languages(first:10,orderBy:{{field:SIZE,direction:DESC}}){{edges{{size node{{name}}}}}} }} }}
      year: contributionsCollection(from:$from){{ {CAL} }}
      recent: contributionsCollection{{ {CAL} }} }} }}"""
    u = gql(q, {"login": login, "from": year_from})["user"]
    langs = {}
    for n in u["owned"]["nodes"]:
        for e in n["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    days = lambda cal: [dd for w in cal["contributionCalendar"]["weeks"] for dd in w["contributionDays"]]
    recent = {x["date"]: x for x in days(u["recent"])}
    year_days = days(u["year"])
    avatar = None
    try:
        avatar = base64.b64encode(urllib.request.urlopen(u["avatarUrl"], timeout=20).read()).decode()
    except Exception as e:
        print("avatar gagal diunduh, pakai ikon:", e)
    local = ASSETS / "avatar.png"
    if local.exists(): avatar = base64.b64encode(local.read_bytes()).decode()
    repos = pick_repos(u, login)
    return {
        "avatar_b64": avatar,
        "profile": {"login": u["login"], "name": u["name"], "bio": u["bio"], "location": u["location"]},
        "stars": sum(n["stargazerCount"] for n in u["owned"]["nodes"]),
        "year_contrib": u["year"]["contributionCalendar"]["totalContributions"],
        "public_repos": u["publicRepos"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "languages": sorted(langs.items(), key=lambda kv: -kv[1]),
        "recent": recent, "year_days": year_days, "repos": repos,
    }

def to_card(r):
    return {"name": r["name"], "description": r.get("description"), "stars": r.get("stargazerCount", 0),
            "language": (r.get("primaryLanguage") or {}).get("name"), "url": r.get("url")}

def pick_repos(u, login):
    """Urutan: daftar manual di config -> repo yang di-pin di profil -> repo sendiri paling banyak star/terbaru."""
    n = CFG.get("repo_cards", 2)
    owned = [r for r in u["owned"]["nodes"] if r["name"].lower() != login.lower()]
    manual = CFG.get("repos") or []
    if manual:
        by = {r["name"].lower(): r for r in owned + u["pinnedItems"]["nodes"]}
        chosen = [by[m.lower()] for m in manual if m.lower() in by]
    else:
        chosen = [r for r in u["pinnedItems"]["nodes"] if r and r["name"].lower() != login.lower()]
    if len(chosen) < n:
        rest = sorted(owned, key=lambda r: -r["stargazerCount"])  # stabil: seri tetap urut push terbaru
        chosen += [r for r in rest if r not in chosen]
    return [to_card(r) for r in chosen[:n]]

def sample(today):
    rnd = random.Random(7)
    t = dt.date.fromisoformat(today)
    lv = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]
    recent, year_days = {}, []
    d0 = dt.date(t.year, 1, 1)
    for i in range((t - d0).days + 1):
        day = d0 + dt.timedelta(days=i); c = rnd.choice([0, 0, 0, 1, 2, 4, 7])
        rec = {"date": day.isoformat(), "contributionCount": c, "contributionLevel": lv[min(4, (c + 1) // 2)] if c else "NONE"}
        recent[rec["date"]] = rec; year_days.append(rec)
    return {"avatar_b64": None, "profile": {"login": "paulgoated", "name": None, "bio": "such sweet entropy", "location": None},
            "stars": 12, "year_contrib": sum(x["contributionCount"] for x in year_days),
            "public_repos": 9, "followers": 20,
            "languages": [("Python", 52), ("JavaScript", 24), ("TypeScript", 12), ("C++", 9), ("HTML", 3)],
            "recent": recent, "year_days": year_days,
            "repos": [{"name": "sample-repo-one", "description": "Contoh. Di workflow asli diisi dari repo yang kamu pin.",
                       "stars": 0, "language": "Rust", "url": "#"},
                      {"name": "sample-repo-two", "description": "Contoh kedua.", "stars": 0, "language": "C++", "url": "#"}]}

def streaks(recent, year_days, today):
    cur = 0; day = dt.date.fromisoformat(today)
    if recent.get(today, {}).get("contributionCount", 0) == 0: day -= dt.timedelta(days=1)
    while recent.get(day.isoformat(), {}).get("contributionCount", 0) > 0:
        cur += 1; day -= dt.timedelta(days=1)
    best = run = 0
    for x in year_days:
        if x["date"] > today: break
        run = run + 1 if x["contributionCount"] > 0 else 0; best = max(best, run)
    return cur, best

def main():
    now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=CFG.get("timezone_offset_hours", 0))
    today = now.date().isoformat()
    d = sample(today) if "--sample" in sys.argv else fetch(today)
    t = dt.date.fromisoformat(today)
    start = t - dt.timedelta(days=(t.weekday() + 1) % 7) - dt.timedelta(days=14)  # Minggu, 2 pekan lalu
    d["today"] = today
    d["days21"] = []
    for i in range(21):
        ds = (start + dt.timedelta(days=i)).isoformat()
        r = d["recent"].get(ds)
        d["days21"].append({"date": ds, "count": r["contributionCount"] if r else 0})
    d["cur_streak"], d["long_streak"] = streaks(d["recent"], d["year_days"], today)

    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("repo-*.svg"): old.unlink()
    files = {"hero.svg": card_hero(d), "spec.svg": card_spec(), "stack.svg": card_pinout(d),
             "telemetry.svg": card_telemetry(d), "streak.svg": card_signal(d)}
    for i, r in enumerate(d["repos"], 1):
        files[f"repo-{i}.svg"] = card_repo(r)
    for name, content in files.items():
        (OUT / name).write_text(content, encoding="utf-8")
    print("tersimpan:", ", ".join(files))
    write_readme(d, list(files))

def write_readme(d, files):
    img = lambda f, alt, w="100%": f'<img src="cards/{f}" width="{w}" alt="{esc(alt)}">'
    repos = "\n".join(f'  <a href="{esc(r.get("url") or "#")}">{img(f"repo-{i}.svg", r["name"], "49%")}</a>'
                      for i, r in enumerate(d["repos"], 1))
    md = f"""<!-- File ini dibuat otomatis oleh generate.py. Edit config.json, bukan file ini. -->
<p align="center">{img("hero.svg", d["profile"]["login"])}</p>
<p align="center">{img("spec.svg", "spec sheet")}</p>
<p align="center">{img("stack.svg", "tech stack")}</p>
<p align="center">
{repos}
</p>
<p align="center">{img("telemetry.svg", "github telemetry")}</p>
<p align="center">{img("streak.svg", "streak")}</p>
"""
    (ROOT / "README.md").write_text(md, encoding="utf-8")

if __name__ == "__main__":
    main()
