"""Generate assets/mal.svg from the public MyAnimeList profile + anime list (stdlib only)."""

import base64
import json
import re
import sys
import urllib.request
from collections import Counter
from html import escape, unescape
from pathlib import Path

USER = "Yezun_hikari"
OUT = Path(__file__).resolve().parents[2] / "assets" / "mal.svg"
MAX_WATCHING = 4
TOP_GENRES = 5
NSFW = {"Hentai", "Erotica", "Ecchi"}
UA = {"User-Agent": "Mozilla/5.0 (profile-mal-card)"}

# MAL blue on a dark card
BG, BORDER, TITLE, TEXT, MUTED, ACCENT, BAR_BG = (
    "#0d1117",
    "#30363d",
    "#6e9cff",
    "#e6edf3",
    "#8b949e",
    "#2e51a2",
    "#21262d",
)


def get(url):
    with urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=30
    ) as r:
        return r.read()


def profile_stats():
    html = unescape(
        re.sub(
            r"<[^>]+>",
            " ",
            get(f"https://myanimelist.net/profile/{USER}").decode("utf-8"),
        )
    )
    html = html[html.index("Anime Stats") :]

    def num(label):
        m = re.search(label + r":?\s+([\d,.]+)", html)
        if not m:
            sys.exit(f"MAL profile: '{label}' not found (page layout changed?)")
        return m.group(1).replace(",", "")

    return {
        "days": num("Days"),
        "completed": num("Completed"),
        "episodes": num("Episodes"),
        "ptw": num("Plan to Watch"),
    }


def anime_list():
    entries, offset = [], 0
    while True:  # load.json pages in steps of 300
        page = json.loads(
            get(
                f"https://myanimelist.net/animelist/{USER}/load.json?status=7&offset={offset}"
            )
        )
        entries += page
        if len(page) < 300:
            return entries
        offset += 300


def data_uri(url):
    with urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=30
    ) as r:
        return f"data:{r.headers.get_content_type()};base64,{base64.b64encode(r.read()).decode()}"


def clip(text, n):
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def main():
    stats = profile_stats()
    entries = anime_list()
    # genres over everything already started (1 watching, 2 completed, 3 on-hold, 4 dropped), not plan-to-watch
    genres = Counter(
        g["name"] for e in entries if e["status"] in (1, 2, 3, 4) for g in e["genres"]
    ).most_common(TOP_GENRES)
    watching = sorted(
        (
            e
            for e in entries
            if e["status"] == 1 and not NSFW & {g["name"] for g in e["genres"]}
        ),
        key=lambda e: e["updated_at"],
        reverse=True,
    )[:MAX_WATCHING]

    W, H = 820, 250
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        (
            "<style>text{font-family:'Segoe UI',Ubuntu,'Helvetica Neue',sans-serif}"
            f".t{{fill:{TITLE};font-size:18px;font-weight:600}}"
            f".n{{fill:{TEXT};font-size:22px;font-weight:700}}"
            f".l{{fill:{MUTED};font-size:12px}}"
            f".g{{fill:{TEXT};font-size:12px}}"
            f".s{{fill:{TEXT};font-size:11px}}</style>"
        ),
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="8" fill="{BG}" stroke="{BORDER}"/>',
        f'<text x="24" y="38" class="t">MyAnimeList · {escape(USER)}</text>',
    ]

    for i, (num, label) in enumerate(
        [
            (stats["days"], "Days watched"),
            (stats["completed"], "Completed"),
            (stats["episodes"], "Episodes"),
            (stats["ptw"], "Plan to watch"),
        ]
    ):
        x = 24 + i * 88
        out.append(f'<text x="{x}" y="80" class="n">{num}</text>')
        out.append(f'<text x="{x}" y="98" class="l">{label}</text>')

    top = max((c for _, c in genres), default=1)
    out.append('<text x="24" y="130" class="l">Top genres</text>')
    for i, (name, count) in enumerate(genres):
        y = 146 + i * 19
        out.append(f'<text x="24" y="{y + 10}" class="g">{escape(name)}</text>')
        out.append(
            f'<rect x="130" y="{y}" width="200" height="10" rx="5" fill="{BAR_BG}"/>'
        )
        out.append(
            f'<rect x="130" y="{y}" width="{200 * count / top:.1f}" height="10" rx="5" fill="{ACCENT}"/>'
        )
        out.append(f'<text x="338" y="{y + 10}" class="s">{count}</text>')

    out.append(f'<line x1="380" y1="24" x2="380" y2="{H - 24}" stroke="{BORDER}"/>')
    out.append('<text x="404" y="38" class="t">Currently watching</text>')
    cw, ch = 88, 125
    for i, e in enumerate(watching):
        x, y = 404 + i * (cw + 12), 56
        title = e["anime_title_eng"] or e["anime_title"]
        eps = (
            f"{e['num_watched_episodes']}/{e['anime_num_episodes']}"
            if e["anime_num_episodes"]
            else str(e["num_watched_episodes"])
        )
        out.append(
            f'<clipPath id="c{i}"><rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="6"/></clipPath>'
        )
        out.append(
            f'<image href="{data_uri(e["anime_image_path"])}" x="{x}" y="{y}" width="{cw}" height="{ch}" '
            f'preserveAspectRatio="xMidYMid slice" clip-path="url(#c{i})"/>'
        )
        out.append(
            f'<text x="{x}" y="{y + ch + 18}" class="s">{escape(clip(title, 15))}</text>'
        )
        out.append(f'<text x="{x}" y="{y + ch + 33}" class="l">Ep {eps}</text>')
    if not watching:
        out.append('<text x="404" y="80" class="l">Nothing right now</text>')

    out.append("</svg>")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {OUT} ({stats}, {len(entries)} entries, {len(watching)} watching)")


if __name__ == "__main__":
    main()
