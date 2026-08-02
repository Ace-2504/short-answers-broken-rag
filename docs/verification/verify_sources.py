"""Verify the volume/availability/license claims in docs/assignment-verification.md
by actually hitting the APIs and counting. No assumptions. Run 2026-08-01 results
are recorded in the VERIFIED section of docs/assignment-verification.md."""
import requests, json, sys

UA = "Vizuara-SLM-Assignment/0.1 (educational; harman2504sandhu@gmail.com)"
H = {"User-Agent": UA}
API = "https://yugipedia.com/api.php"

def categoryinfo(cats):
    """Member counts for candidate Yugipedia categories."""
    print("\n=== Yugipedia category sizes (prop=categoryinfo) ===")
    for i in range(0, len(cats), 20):
        batch = cats[i:i+20]
        params = {"action": "query", "prop": "categoryinfo", "format": "json",
                  "formatversion": "2", "titles": "|".join("Category:"+c for c in batch)}
        try:
            r = requests.get(API, params=params, headers=H, timeout=30); r.raise_for_status()
            for p in r.json().get("query", {}).get("pages", []):
                ci = p.get("categoryinfo")
                title = p.get("title", "?").replace("Category:", "")
                if ci is None:
                    print(f"  {title:28s} : (missing / not a category)")
                else:
                    print(f"  {title:28s} : {ci.get('pages',0):>7} pages, "
                          f"{ci.get('subcats',0)} subcats")
        except Exception as e:
            print(f"  batch error: {e}", file=sys.stderr)

def sample_page_bytes(titles):
    """Fetch a few real card/episode pages, count raw wikitext bytes."""
    print("\n=== sample raw wikitext size per page (before cleaning) ===")
    params = {"action": "query", "prop": "revisions", "rvslots": "main",
              "rvprop": "content", "format": "json", "formatversion": "2",
              "redirects": "1", "titles": "|".join(titles)}
    r = requests.get(API, params=params, headers=H, timeout=30); r.raise_for_status()
    for p in r.json().get("query", {}).get("pages", []):
        if p.get("missing"):
            print(f"  {p['title']:35s} : MISSING"); continue
        rev = p["revisions"][0]
        content = rev.get("content") or rev["slots"]["main"]["content"]
        print(f"  {p['title']:35s} : {len(content.encode('utf-8')):>7} bytes wikitext")

def ygoprodeck():
    print("\n=== YGOPRODeck cardinfo (claim: ~13,000 cards, ~5 MB) ===")
    url = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
    r = requests.get(url, headers=H, timeout=60); r.raise_for_status()
    raw = r.content
    data = json.loads(raw).get("data", [])
    print(f"  cards returned : {len(data)}")
    print(f"  payload size   : {len(raw)/1e6:.2f} MB")
    desc = sum(len(c.get('desc','')) for c in data)
    print(f"  total effect-text (desc) chars : {desc/1e6:.2f} MB  ((c) Konami; paraphrase only)")

if __name__ == "__main__":
    categoryinfo([
        "Episodes", "Characters", "Archetypes", "Cards", "TCG cards", "OCG cards",
        "Anime cards", "Video games", "Booster Packs", "Sets", "Yu-Gi-Oh! GX episodes",
        "Series", "Manga chapters",
    ])
    sample_page_bytes([
        "Dark Magician", "Ash Blossom & Joyous Spring", "Pot of Greed",
        "Yugi Muto", "Elemental HERO",
    ])
    ygoprodeck()
