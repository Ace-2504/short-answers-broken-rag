"""Phase-1 recon: enumerate the real prose categories on Yugipedia, sample each,
measure ACTUAL cleaned-prose bytes per page, and project total free-licensed prose
against the 20 MB floor. Verify before scaling to a full pull.

Prose spine (CC BY-SA 4.0): archetype/series pages, character bios, episode plots,
video-game pages, and mechanics/rules pages. Card effect text (c) Konami is excluded
automatically because strip_code drops the CardTable template it lives in.

Output: prints a per-category table + total projection; writes catalog.json (titles).
"""
import json, time, pathlib, sys, random
import requests
import mwparserfromhell

API = "https://yugipedia.com/api.php"
UA = "Vizuara-SLM-Assignment/0.1 (educational research; harman2504sandhu@gmail.com)"
H = {"User-Agent": UA}
OUT = pathlib.Path(__file__).parent / "catalog.json"

# (root category, recursion depth into subcategories). Depth handles the fact that
# Characters/Episodes have no direct pages, only per-series subcategories.
ROOTS = [
    ("Archetypes", 1),
    ("Series", 1),
    ("Characters", 3),
    ("Episodes", 3),
    ("Video games", 2),
    ("Game terms", 1),     # rules/mechanics glossary (name verified at runtime)
]
TITLE_CAP = 2500           # safety cap per root during recon
SAMPLE_PER_ROOT = 8        # pages to fetch+clean for the byte estimate
SEED = 20260801

def cat_members(title, types):
    """Yield all members (pages or subcats) of a category, following continuation."""
    cont = {}
    while True:
        params = {"action": "query", "list": "categorymembers", "format": "json",
                  "formatversion": "2", "cmtitle": f"Category:{title}",
                  "cmtype": types, "cmlimit": "500", **cont}
        r = requests.get(API, params=params, headers=H, timeout=30); r.raise_for_status()
        d = r.json()
        for m in d.get("query", {}).get("categorymembers", []):
            yield m
        if "continue" in d:
            cont = {"cmcontinue": d["continue"]["cmcontinue"]}
            time.sleep(0.2)
        else:
            return

def enumerate_pages(root, max_depth):
    """BFS the category tree; return {page_title} (ns 0 article pages)."""
    seen_cat, pages, queue = set(), set(), [(root, 0)]
    while queue and len(pages) < TITLE_CAP:
        cat, depth = queue.pop(0)
        if cat in seen_cat:
            continue
        seen_cat.add(cat)
        try:
            for m in cat_members(cat, "page|subcat"):
                if m["ns"] == 14 and depth < max_depth:          # subcategory
                    queue.append((m["title"].replace("Category:", ""), depth + 1))
                elif m["ns"] == 0:                               # article page
                    pages.add(m["title"])
                    if len(pages) >= TITLE_CAP:
                        break
        except Exception as e:
            print(f"    enum error in {cat}: {e}", file=sys.stderr)
        time.sleep(0.2)
    return pages

def fetch_wikitext(titles):
    params = {"action": "query", "prop": "revisions", "rvslots": "main",
              "rvprop": "content", "format": "json", "formatversion": "2",
              "redirects": "1", "titles": "|".join(titles)}
    r = requests.get(API, params=params, headers=H, timeout=30); r.raise_for_status()
    return r.json().get("query", {}).get("pages", [])

def clean(wikitext):
    """Strip markup/templates to plain prose. Card effect text lives inside the
    CardTable template and is removed by strip_code -> (c) Konami text excluded."""
    text = mwparserfromhell.parse(wikitext).strip_code(normalize=True, collapse=True)
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.lower() in ("references", "external links", "see also", "gallery", "notes"):
            break
        if len(s) < 25:
            continue
        out.append(s)
    return "\n".join(out)

def sample_bytes(titles, k):
    """Fetch k random pages, return mean cleaned-prose bytes/page."""
    pick = random.Random(SEED).sample(list(titles), min(k, len(titles)))
    sizes = []
    for i in range(0, len(pick), 50):
        for p in fetch_wikitext(pick[i:i+50]):
            if p.get("missing") or "revisions" not in p:
                continue
            rev = p["revisions"][0]
            wt = rev.get("content") or rev["slots"]["main"]["content"]
            sizes.append(len(clean(wt).encode("utf-8")))
        time.sleep(0.3)
    return (sum(sizes) / len(sizes)) if sizes else 0.0

def main():
    catalog, total_mb = {}, 0.0
    print(f"{'category':<16}{'pages':>8}{'avg_prose_B':>13}{'proj_MB':>10}")
    print("-" * 47)
    for root, depth in ROOTS:
        pages = enumerate_pages(root, depth)
        if not pages:
            print(f"{root:<16}{0:>8}   (empty / not a category)")
            continue
        avg = sample_bytes(pages, SAMPLE_PER_ROOT)
        proj = len(pages) * avg / 1e6
        total_mb += proj
        catalog[root] = sorted(pages)
        print(f"{root:<16}{len(pages):>8}{avg:>13.0f}{proj:>10.2f}")
    print("-" * 47)
    print(f"{'TOTAL (prose spine)':<16}{sum(len(v) for v in catalog.values()):>8}"
          f"{'':>13}{total_mb:>10.2f} MB   (floor = 20 MB)")
    json.dump(catalog, OUT.open("w"), indent=0)
    print(f"\nwrote {OUT.name} ({sum(len(v) for v in catalog.values())} titles)")
    if total_mb < 20:
        print("NOTE: below floor -> top up with card-page Rulings/Tips prose in the full pull.")
    else:
        print("NOTE: prose spine alone clears the 20 MB floor.")

if __name__ == "__main__":
    main()
