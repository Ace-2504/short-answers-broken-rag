"""Phase-1 collection: build the curated, target-biased Yu-Gi-Oh prose corpus.

Composition (see docs decision): majority = Card Rulings + Card Tips + Archetypes +
Gameplay/mechanics (our interaction/timing/ruling targets); character bios + episode
plots capped as a ~15-20% lore minority. Card effect text (c) Konami is excluded
automatically -- it lives inside the CardTable template, which strip_code removes.

Held-out reservation: a HELDOUT_FRAC page-level split is tagged HERE, before any QA
generation, so held-out passages never enter training (leakage impossible by construction).
The retrieval index (Phase 4) still indexes ALL pages -- the split constrains training only.

Output: data/corpus/corpus.jsonl  ({doc_id, title, source, split, text})
        data/corpus/stats.json    (per-source and funnel counts)
Config caps are tunable; script reports actual MB so we can adjust to the ~25-30 MB target.
"""
import json, os, time, pathlib, sys, random, hashlib
import requests
import mwparserfromhell

API = "https://yugipedia.com/api.php"
UA = "Vizuara-SLM-Assignment/0.1 (educational research; harman2504sandhu@gmail.com)"
H = {"User-Agent": UA}
OUTDIR = pathlib.Path(__file__).parents[1] / "corpus"
SEED = 20260801
HELDOUT_FRAC = 0.15

# tag, kind, target, (depth for category), page cap, min cleaned bytes to keep.
# On-target sources first (majority); lore capped as minority. Namespaces are
# enumerated in FULL then randomly sampled to cap (removes alphabetical bias).
SOURCES = [
    dict(tag="rulings",   kind="namespace", target="Card Rulings", cap=8000, min_bytes=450),
    dict(tag="tips",      kind="namespace", target="Card Tips",     cap=9000, min_bytes=450),
    dict(tag="archetype", kind="category",  target="Archetypes",  depth=0, cap=800, min_bytes=500),
    dict(tag="mechanics", kind="category",  target="Gameplay",    depth=1, cap=200, min_bytes=350),
    dict(tag="mechanics", kind="category",  target="Terminology", depth=0, cap=60,  min_bytes=300),
    dict(tag="lore-char", kind="category",  target="Characters",  depth=3, cap=350, min_bytes=800),
    dict(tag="lore-ep",   kind="category",  target="Episodes",    depth=3, cap=180, min_bytes=1500),
]

def api_get(params):
    r = requests.get(API, params={**params, "format": "json", "formatversion": "2"},
                     headers=H, timeout=40)
    r.raise_for_status()
    return r.json()

def namespace_id(name):
    d = api_get({"action": "query", "meta": "siteinfo", "siprop": "namespaces"})
    for ns in d["query"]["namespaces"].values():
        if ns.get("name") == name or ns.get("canonical") == name:
            return ns["id"]
    raise ValueError(f"namespace not found: {name}")

def enum_namespace(name, cap):
    """Enumerate ALL pages in the namespace, then random-sample to cap. Sampling
    the full list (not taking the alphabetical first N) avoids selection bias."""
    nsid = namespace_id(name)
    titles, cont = [], {}
    while True:
        d = api_get({"action": "query", "list": "allpages", "apnamespace": nsid,
                     "aplimit": "500", "apfilterredir": "nonredirects", **cont})
        titles += [p["title"] for p in d["query"]["allpages"]]
        if "continue" in d:
            cont = {"apcontinue": d["continue"]["apcontinue"]}; time.sleep(0.2)
        else:
            break
    if len(titles) > cap:
        titles = random.Random(SEED).sample(titles, cap)
    return titles

def enum_category(cat, depth, cap):
    seen, pages, queue = set(), [], [(cat, 0)]
    while queue and len(pages) < cap:
        c, dep = queue.pop(0)
        if c in seen:
            continue
        seen.add(c)
        cont = {}
        while True:
            d = api_get({"action": "query", "list": "categorymembers",
                         "cmtitle": f"Category:{c}", "cmtype": "page|subcat",
                         "cmlimit": "500", **cont})
            for m in d["query"]["categorymembers"]:
                if m["ns"] == 14 and dep < depth:
                    queue.append((m["title"].replace("Category:", ""), dep + 1))
                elif m["ns"] == 0:
                    pages.append(m["title"])
            if "continue" in d and len(pages) < cap:
                cont = {"cmcontinue": d["continue"]["cmcontinue"]}; time.sleep(0.2)
            else:
                break
    # de-dup preserve order
    out, s = [], set()
    for t in pages:
        if t not in s:
            s.add(t); out.append(t)
    return out[:cap]

def fetch_wikitext(titles):
    d = api_get({"action": "query", "prop": "revisions", "rvslots": "main",
                 "rvprop": "content", "redirects": "1", "titles": "|".join(titles)})
    return d.get("query", {}).get("pages", [])

def clean(wikitext):
    text = mwparserfromhell.parse(wikitext).strip_code(normalize=True, collapse=True)
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.lower() in ("references", "external links", "see also", "gallery", "navigation"):
            break
        if len(s) < 25:
            continue
        out.append(s)
    return "\n".join(out)

def main():
    # SMOKE=1 -> tiny caps for a fast end-to-end validation before the full pull.
    if os.environ.get("SMOKE"):
        for s in SOURCES:
            s["cap"] = min(s["cap"], 8)
        print("SMOKE mode: caps reduced to <=8 pages/source")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    corpus_path = OUTDIR / "corpus.jsonl"
    seen_titles, seen_hashes = set(), set()
    records = []

    for src in SOURCES:
        tag, target = src["tag"], src["target"]
        print(f"\n[{tag}] enumerating {src['kind']} {target!r} (cap {src['cap']}) ...")
        try:
            if src["kind"] == "namespace":
                titles = enum_namespace(target, src["cap"])
            else:
                titles = enum_category(target, src["depth"], src["cap"])
        except Exception as e:
            print(f"  enum failed: {e}", file=sys.stderr); continue
        print(f"  {len(titles)} titles; fetching ...")
        kept_here = 0
        for i in range(0, len(titles), 50):
            batch = [t for t in titles[i:i+50] if t not in seen_titles]
            if not batch:
                continue
            try:
                pages = fetch_wikitext(batch)
            except Exception as e:
                print(f"  fetch error: {e}", file=sys.stderr); time.sleep(2); continue
            for p in pages:
                title = p.get("title", "")
                if p.get("missing") or "revisions" not in p or title in seen_titles:
                    continue
                seen_titles.add(title)
                rev = p["revisions"][0]
                wt = rev.get("content") or rev["slots"]["main"]["content"]
                prose = clean(wt)
                if len(prose.encode("utf-8")) < src["min_bytes"]:
                    continue
                h = hashlib.md5(prose.encode("utf-8")).hexdigest()
                if h in seen_hashes:
                    continue
                seen_hashes.add(h)
                records.append({"title": title, "source": tag, "text": prose})
                kept_here += 1
            time.sleep(0.25)
        print(f"  kept {kept_here} pages this source")

    # assign ids + held-out split (page level, seeded)
    rng = random.Random(SEED)
    rng.shuffle(records)
    n_heldout = int(len(records) * HELDOUT_FRAC)
    for i, r in enumerate(records):
        r["doc_id"] = f"doc-{i:05d}"
        r["split"] = "heldout" if i < n_heldout else "train"
    records.sort(key=lambda r: r["doc_id"])

    with corpus_path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps({"doc_id": r["doc_id"], "title": r["title"],
                                "source": r["source"], "split": r["split"],
                                "text": r["text"]}, ensure_ascii=False) + "\n")

    # stats
    tag_stats = {}
    for r in records:
        t = r["source"]; b = len(r["text"].encode("utf-8"))
        tag_stats.setdefault(t, {"pages": 0, "bytes": 0})
        tag_stats[t]["pages"] += 1; tag_stats[t]["bytes"] += b
    total_bytes = sum(s["bytes"] for s in tag_stats.values())
    stats = {"total_pages": len(records), "total_MB": round(total_bytes/1e6, 3),
             "heldout_pages": n_heldout, "train_pages": len(records)-n_heldout,
             "per_source": {t: {"pages": s["pages"], "MB": round(s["bytes"]/1e6, 3)}
                            for t, s in sorted(tag_stats.items())}}
    json.dump(stats, (OUTDIR / "stats.json").open("w"), indent=2)

    print("\n" + "=" * 52)
    print(f"{'source':<12}{'pages':>8}{'MB':>10}")
    for t, s in sorted(tag_stats.items()):
        print(f"{t:<12}{s['pages']:>8}{s['bytes']/1e6:>10.2f}")
    print("-" * 52)
    print(f"{'TOTAL':<12}{len(records):>8}{total_bytes/1e6:>10.2f} MB  "
          f"(floor 20 MB; heldout {n_heldout} / train {len(records)-n_heldout})")
    print(f"\nwrote {corpus_path} and stats.json")

if __name__ == "__main__":
    main()
