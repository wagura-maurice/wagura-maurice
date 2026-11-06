#!/usr/bin/env python3
"""Generate assets/activity.svg — a Repobeats-style activity card for wagura-maurice.

Data source: GitHub Events API (public events, up to 300 recent).
Aggregates last-30-day pushes, PRs, issues, per-day intensity heatmap,
and most active repos.
"""
import json
import os
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

USER = "wagura-maurice"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
DAYS = 30
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "activity.svg")


def api(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "activity-card",
        },
    )
    return json.load(urllib.request.urlopen(req))


def fetch_events():
    events = []
    for page in (1, 2, 3):
        try:
            batch = api(f"/users/{USER}/events?per_page=100&page={page}")
        except Exception:
            batch = api(f"/users/{USER}/events/public?per_page=100&page={page}")
        if not batch:
            break
        events += batch
    return events


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DAYS)

    events = fetch_events()
    per_day = Counter()
    pushes = prs = issues_opened = issues_closed = 0
    repo_hits = Counter()

    for e in events:
        created = datetime.fromisoformat(e["created_at"].replace("Z", "+00:00"))
        repo = e.get("repo", {}).get("name", "").split("/")[-1]
        if created < cutoff:
            continue
        t = e["type"]
        if t == "PushEvent":
            pushes += 1
            repo_hits[repo] += len(e.get("payload", {}).get("commits", [])) or 1
        elif t == "PullRequestEvent":
            if e.get("payload", {}).get("action") == "opened":
                prs += 1
        elif t == "IssuesEvent":
            a = e.get("payload", {}).get("action")
            if a == "opened":
                issues_opened += 1
            elif a == "closed":
                issues_closed += 1
        if t in ("PushEvent", "PullRequestEvent", "IssuesEvent", "CreateEvent",
                 "ReleaseEvent", "PullRequestReviewEvent"):
            per_day[created.date()] += 1
            repo_hits[repo] += 0  # ensure counted repos exist
            if t != "PushEvent":
                repo_hits[repo] += 1

    total = sum(per_day.values())
    max_day = max(per_day.values(), default=1)
    top_repos = [r for r, n in repo_hits.most_common(3) if r] or ["-"]
    top_counts = [n for r, n in repo_hits.most_common(3) if r] or [0]
    max_hits = max(top_counts) if top_counts else 1

    # heatmap cells: oldest -> newest, right-aligned at x=420
    cells = []
    for i in range(DAYS):
        d = (cutoff + timedelta(days=i + 1)).date()
        n = per_day.get(d, 0)
        op = 0.2 if n == 0 else min(1.0, 0.4 + 0.6 * n / max_day)
        x = 420 + i * 11
        cells.append(
            f'    <rect x="{x}" y="19" width="8" height="8" rx="1.5" '
            f'fill="#EC4899" opacity="{op:.1f}"/>'
        )

    # mini bars: last 4 weeks activity
    def bars(x0, color):
        out = []
        for w in range(4):
            wstart = cutoff + timedelta(days=7 * w)
            wend = wstart + timedelta(days=7)
            n = sum(v for d, v in per_day.items() if wstart.date() <= d < wend.date())
            h = 8 + int(67 * n / max_day) if max_day else 8
            out.append(
                f'  <rect x="{x0 + w * 14}" y="{145 - h}" width="10" '
                f'height="{h}" fill="{color}"/>'
            )
        return "\n".join(out)

    def delta(n):
        return f"▲ +{n}" if n else "— 0"

    def repo_rows():
        colors = ["#61ADF4", "#CF54FC", "#FF7A35"]
        out = []
        for i, (repo, n) in enumerate(zip(top_repos, top_counts)):
            y = 225 + i * 28
            w = int(400 * n / max_hits) or 4
            out.append(f'  <text x="40" y="{y + 10}" class="mono" fill="#C9D1D9">{esc(repo)}</text>')
            out.append(f'  <rect x="220" y="{y}" width="{w}" height="10" rx="5" fill="{colors[i]}"/>')
            out.append(f'  <text x="630" y="{y + 10}" class="mono" fill="#777">{n} events</text>')
        return "\n".join(out)

    svg = f"""<svg width="814" height="318" viewBox="0 0 814 318" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .sans {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; font-size: 12px; }}
    .title {{ font-size: 20px; font-weight: 600; fill: #C9D1D9; }}
    .big {{ font-size: 34px; font-weight: 700; }}
    .delta {{ font-size: 13px; font-weight: 600; }}
    .cap {{ font-size: 11px; fill: #777; }}
    .label {{ font-size: 12px; fill: #C9D1D9; }}
  </style>
  <rect x="0.5" y="0.5" width="813" height="317" rx="8" stroke="rgba(0,0,0,0.15)" fill="rgba(0,0,0,0)"/>
  <rect x="0.5" y="0.5" width="813" height="317" rx="8" stroke="rgba(255,255,255,0.15)" fill="rgba(0,0,0,0)"/>
  <rect x="0.5" y="0.5" width="813" height="47" rx="8" stroke="rgba(255,255,255,0.1)"/>
  <text x="20" y="30" class="sans title">{total} Contributions in the Last {DAYS} Days</text>
{chr(10).join(cells)}

  <text x="40" y="90" class="sans big" fill="#61ADF4">{issues_opened}/{issues_closed}</text>
  <text x="40" y="110" class="sans label">Issues Opened/Closed</text>
  <text x="40" y="128" class="sans delta" fill="#459631">{delta(issues_opened)} opened</text>
  <text x="40" y="144" class="sans cap">past month</text>
{bars(160, "#61ADF4")}

  <text x="300" y="90" class="sans big" fill="#CF54FC">{prs}</text>
  <text x="300" y="110" class="sans label">Pull Requests Opened</text>
  <text x="300" y="128" class="sans delta" fill="#459631">{delta(prs)} opened</text>
  <text x="300" y="144" class="sans cap">past month</text>
{bars(430, "#CF54FC")}

  <text x="560" y="90" class="sans big" fill="#FF7A35">{pushes}</text>
  <text x="560" y="110" class="sans label">Pushes</text>
  <text x="560" y="128" class="sans delta" fill="#459631">{delta(pushes)} pushes</text>
  <text x="560" y="144" class="sans cap">past month</text>
{bars(680, "#FF7A35")}

  <text x="40" y="190" class="sans title" font-size="16">Most Active Repos</text>
{repo_rows()}

  <text x="40" y="312" class="sans cap">Generated {now:%Y-%m-%d %H:%M} UTC from live GitHub events</text>
</svg>
"""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(svg)
    print(f"wrote {OUT} — {total} events counted, top repos: {top_repos}")


if __name__ == "__main__":
    main()
