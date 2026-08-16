#!/usr/bin/env python3
"""Draw profile-stats.png from GitHub GraphQL. Used by .github/workflows/stats.yml."""
from __future__ import annotations

import json
import os
import urllib.request
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

USER = "bedirrhaan"
OUT = Path(__file__).resolve().parent / "profile-stats.png"
SKIP_LANGS = {"Makefile", "Roff", "Perl", "Batchfile", "Dockerfile", "Objective-C"}

QUERY = """
query($login:String!) {
  user(login:$login) {
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(first:100, ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC) {
      nodes {
        stargazerCount
        languages(first:10, orderBy:{field:SIZE, direction:DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar { totalContributions }
    }
  }
}
"""


def gh_graphql(query: str, variables: dict) -> dict:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "bedirrhaan-stats",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read().decode())
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


def pick_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    )
    for path in names:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def collect() -> dict:
    user = gh_graphql(QUERY, {"login": USER})["user"]
    stars = 0
    langs: dict[str, dict] = defaultdict(lambda: {"size": 0, "color": "#737373"})
    for node in user["repositories"]["nodes"]:
        stars += node["stargazerCount"]
        for edge in node["languages"]["edges"]:
            name = edge["node"]["name"]
            if name in SKIP_LANGS:
                continue
            if name == "SCSS":
                name = "CSS"
            langs[name]["size"] += edge["size"]
            langs[name]["color"] = edge["node"]["color"] or "#737373"
    ranked = sorted(langs.items(), key=lambda kv: -kv[1]["size"])[:4]
    total = sum(v["size"] for _, v in ranked) or 1
    return {
        "stars": stars,
        "commits": user["contributionsCollection"]["totalCommitContributions"],
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "contrib": user["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "langs": [
            {
                "name": name,
                "pct": round(100 * meta["size"] / total),
                "color": meta["color"],
            }
            for name, meta in ranked
        ],
    }


def hex_to_rgba(value: str) -> tuple[int, int, int, int]:
    value = (value or "#737373").lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    r, g, b = int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    return (r, g, b, 255)


def draw(stats: dict) -> None:
    width, height = 680, 188
    bg, border, red = (10, 10, 10, 255), (127, 29, 29, 255), (239, 68, 68, 255)
    muted, text, track = (163, 163, 163, 255), (250, 250, 250, 255), (31, 31, 31, 255)

    im = Image.new("RGBA", (width, height), bg)
    d = ImageDraw.Draw(im)
    title, body, number, small = pick_font(17, True), pick_font(13), pick_font(13, True), pick_font(12)

    d.rounded_rectangle((1, 1, width - 2, height - 2), radius=10, outline=border, width=2)
    d.line((340, 16, 340, height - 16), fill=border, width=1)
    d.text((22, 16), "GitHub Stats", font=title, fill=red)

    rows = [
        ("Stars", str(stats["stars"])),
        ("Commits", str(stats["commits"])),
        ("Pull requests", str(stats["prs"])),
        ("Issues", str(stats["issues"])),
        ("Contributions", str(stats["contrib"])),
    ]
    y = 50
    for label, value in rows:
        d.text((22, y), label, font=body, fill=muted)
        d.text((280, y), value, font=number, fill=text)
        y += 24

    d.text((360, 16), "Languages", font=title, fill=red)
    y = 50
    bar_x, bar_w, bar_h = 360, 292, 7
    for lang in stats["langs"]:
        d.text((360, y), f"{lang['name']}  {lang['pct']}%", font=small, fill=text)
        d.rounded_rectangle((bar_x, y + 16, bar_x + bar_w, y + 16 + bar_h), radius=3, fill=track)
        fill_w = max(8, int(bar_w * lang["pct"] / 100))
        d.rounded_rectangle(
            (bar_x, y + 16, bar_x + fill_w, y + 16 + bar_h),
            radius=3,
            fill=hex_to_rgba(lang["color"]),
        )
        y += 32

    im.save(OUT, "PNG", optimize=True)


if __name__ == "__main__":
    draw(collect())
    print(f"wrote {OUT}")
