#!/usr/bin/env python3
"""Regenerate the projects section of the profile README from the GitHub API.

The section lives between PROJECTS:START / PROJECTS:END markers in README.md.
Run by .github/workflows/update-projects.yml; can also be run locally:

    python scripts/update_projects.py            # fetch from GitHub and rewrite README.md
    python scripts/update_projects.py --dry-run  # print the generated block only
"""
import argparse
import html
import json
import os
import re
import sys
import urllib.request

# ---- configuration ---------------------------------------------------------
USER = "JoaoVictorAAbreu-Dev"
PROFILE_REPO = USER                  # the profile repo itself is never listed
FEATURED_COUNT = 6                   # cards shown in the grid
SHOWCASE_TOPIC = "showcase"          # repos with this topic are always featured first
# Repos matching these (case-insensitive) are kept out of the featured grid.
# They still appear in the collapsible "all repositories" list.
FEATURED_EXCLUDE = [r"^fiap", r"^fia-", r"^cp-?\d", r"^gs[-_\d]"]
README = "README.md"
START, END = "<!-- PROJECTS:START -->", "<!-- PROJECTS:END -->"
# ---------------------------------------------------------------------------


def fetch_repos(user, token=None):
    repos, page = [], 1
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme-updater",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    while True:
        url = (
            f"https://api.github.com/users/{user}/repos"
            f"?per_page=100&type=owner&sort=pushed&page={page}"
        )
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
            batch = json.load(r)
        repos += batch
        if len(batch) < 100:
            return repos
        page += 1


def visible(repos):
    return [
        r for r in repos
        if not r.get("fork") and not r.get("archived") and not r.get("private")
        and r["name"].lower() != PROFILE_REPO.lower()
    ]


def sort_recent(repos):
    return sorted(repos, key=lambda r: r.get("pushed_at") or r.get("updated_at") or "", reverse=True)


def is_excluded(repo):
    if SHOWCASE_TOPIC in (repo.get("topics") or []):
        return False
    return any(re.search(p, repo["name"], re.I) for p in FEATURED_EXCLUDE)


def pick_featured(repos):
    ordered = sort_recent(repos)
    showcase = [r for r in ordered if SHOWCASE_TOPIC in (r.get("topics") or [])]
    others = [r for r in ordered if r not in showcase and not is_excluded(r)]
    return (showcase + others)[:FEATURED_COUNT]


def tags(repo):
    items = []
    if repo.get("language"):
        items.append(repo["language"])
    lang = (repo.get("language") or "").lower().replace(" ", "-")
    topics = [t for t in (repo.get("topics") or []) if t not in (SHOWCASE_TOPIC, lang)]
    items += topics[:3]
    return " · ".join(f"<code>{html.escape(t)}</code>" for t in items)


def card(repo):
    desc = html.escape((repo.get("description") or "").strip()) or "No description yet."
    return (
        '    <td width="50%" valign="top">\n'
        f'      <a href="{repo["html_url"]}"><strong>{html.escape(repo["name"])}</strong></a><br />\n'
        f"      {desc}<br />\n"
        f"      <sub>{tags(repo)}</sub>\n"
        "    </td>"
    )


def grid(repos):
    rows = []
    for i in range(0, len(repos), 2):
        pair = [card(r) for r in repos[i:i + 2]]
        if len(pair) == 1:
            pair.append('    <td width="50%"></td>')
        rows.append("  <tr>\n" + "\n".join(pair) + "\n  </tr>")
    return '<table align="center">\n' + "\n".join(rows) + "\n</table>"


def full_list(repos):
    lines = []
    for r in sort_recent(repos):
        desc = (r.get("description") or "").strip()
        lang = r.get("language")
        extra = " · ".join(x for x in [desc, f"`{lang}`" if lang else ""] if x)
        lines.append(f"- [{r['name']}]({r['html_url']})" + (f" — {extra}" if extra else ""))
    return (
        f"<details>\n<summary><sub>all repositories ({len(repos)})</sub></summary>\n\n"
        + "\n".join(lines)
        + "\n\n</details>"
    )


def build_block(repos):
    repos = visible(repos)
    return "\n\n".join([
        grid(pick_featured(repos)),
        full_list(repos),
        f'<p align="center"><sub><a href="https://github.com/{USER}?tab=repositories">$ ls ~/repositories →</a></sub></p>',
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-json", help="read repos from a JSON file instead of the API (testing)")
    ap.add_argument("--readme", default=README)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.from_json:
        with open(args.from_json, encoding="utf-8") as f:
            repos = json.load(f)
    else:
        repos = fetch_repos(USER, os.environ.get("GITHUB_TOKEN"))

    block = build_block(repos)
    if args.dry_run:
        print(block)
        return 0

    with open(args.readme, encoding="utf-8") as f:
        text = f.read()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        sys.exit(f"markers {START} / {END} not found in {args.readme}")
    new = pattern.sub(lambda _: f"{START}\n{block}\n{END}", text)
    if new == text:
        print("no changes")
        return 0
    with open(args.readme, "w", encoding="utf-8") as f:
        f.write(new)
    print("README updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
