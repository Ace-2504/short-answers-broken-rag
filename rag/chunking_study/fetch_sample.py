"""
Phase-1 recon: pull a small, representative sample of Yugipedia prose so we can
benchmark chunking configs BEFORE committing to one. Uses the MediaWiki API and
mwparserfromhell to strip wiki markup down to plain prose -- the same cleaning
path the real Phase-1 collector will use.

Output: rag/chunking_study/sample_corpus.jsonl  ({doc_id, title, text})
"""
import json, time, pathlib, sys
import requests
import mwparserfromhell

API = "https://yugipedia.com/api.php"
# Descriptive User-Agent is required MediaWiki etiquette.
UA = "Vizuara-SLM-Assignment/0.1 (educational research; harman2504sandhu@gmail.com)"
OUT = pathlib.Path(__file__).parent / "sample_corpus.jsonl"

# Prose-heavy seed pages across the in-scope question types: archetype strategy,
# game mechanics, and general rulings concepts. Missing titles are skipped.
SEED_TITLES = [
    # archetypes (strategy prose)
    "Sky Striker", "Blue-Eyes", "Dark Magician", "Salamangreat", "Eldlich",
    "Branded", "Tearlaments", "Kashtira", "Spright", "Runick", "Labrynth",
    "Mathmech", "Adventurer Token", "Dogmatika", "Swordsoul", "Floowandereeze",
    "Purrely", "Rescue-ACE", "Vanquish Soul", "Snake-Eye", "Fire King",
    "Voiceless Voice", "Yubel", "Centur-Ion", "Unchained", "Bystial",
    # mechanics / rules concepts
    "Normal Summon", "Special Summon", "Tribute Summon", "Synchro Summon",
    "Xyz Summon", "Link Summon", "Pendulum Summon", "Ritual Summon",
    "Fusion Summon", "Chain", "Spell Speed", "Fast Effect", "Trigger Effect",
    "Ignition Effect", "Continuous Effect", "Attribute", "Type (property)",
    "Graveyard", "Banished", "Hand", "Deck", "Main Monster Zone",
    "Extra Monster Zone", "Once per turn", "Cost", "Target", "Negate",
    "Battle Phase", "Damage Step", "Priority", "Missing the timing",
]

def fetch_wikitext(titles):
    """Fetch raw wikitext for up to 50 titles in one API call."""
    params = {
        "action": "query", "prop": "revisions", "rvslots": "main",
        "rvprop": "content", "format": "json", "formatversion": "2",
        "redirects": "1", "titles": "|".join(titles),
    }
    r = requests.get(API, params=params, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.json().get("query", {}).get("pages", [])

def rev_content(page):
    """Content location varies by MediaWiki version: new API nests it under
    slots.main.content, legacy returns it directly on the revision."""
    rev = page["revisions"][0]
    if "slots" in rev:
        return rev["slots"]["main"]["content"]
    return rev["content"]

def clean(wikitext):
    """Strip templates/markup to plain prose, then tidy whitespace and drop
    trailing reference/link sections and short nav lines."""
    text = mwparserfromhell.parse(wikitext).strip_code(normalize=True, collapse=True)
    lines, out = text.splitlines(), []
    for ln in lines:
        s = ln.strip()
        low = s.lower()
        # stop at appendix-style sections that are not prose
        if low in ("references", "external links", "see also", "gallery", "trivia"):
            break
        if len(s) < 25:            # drop nav fragments / stray tokens
            continue
        out.append(s)
    return "\n".join(out)

def main():
    seen, kept, total_chars = set(), 0, 0
    with OUT.open("w", encoding="utf-8") as f:
        # batch titles 50 at a time
        for i in range(0, len(SEED_TITLES), 50):
            batch = SEED_TITLES[i:i+50]
            pages = fetch_wikitext(batch)
            for p in pages:
                if p.get("missing") or "revisions" not in p:
                    continue
                title = p["title"]
                if title in seen:
                    continue
                seen.add(title)
                wt = rev_content(p)
                prose = clean(wt)
                if len(prose) < 400:      # too thin to be useful prose
                    continue
                kept += 1
                total_chars += len(prose)
                f.write(json.dumps(
                    {"doc_id": f"doc-{kept:03d}", "title": title, "text": prose},
                    ensure_ascii=False) + "\n")
                print(f"  kept {title!r:45s} {len(prose):>6d} chars")
            time.sleep(0.5)           # be polite to the API
    print(f"\nKept {kept} pages, {total_chars/1e6:.2f} MB of prose -> {OUT.name}")
    if kept < 15:
        print("WARNING: few pages kept; seed titles may be wrong.", file=sys.stderr)

if __name__ == "__main__":
    main()
