"""Phase-1 collection: add a structured CARD-FACTS source from YGOPRODeck, so the
RAG corpus can answer the fundamental card questions the rulings/tips corpus cannot
("what does X do?", "what are X's stats?", "is X banned?").

Each card -> one short retrievable passage: stats + archetype + banlist (facts,
freely usable) + effect text (© Konami / 4K Media, included as labeled fair-use
context, never counted toward the free-prose floor, never a verbatim-recall target).

Transparency: records the snapshot fetch date AND the newest card release date in
the data (the effective card-knowledge cutoff) -> data/corpus/cardfacts_stats.json.

Output: data/corpus/cardfacts.jsonl  ({doc_id, title, source:"cardfacts", split, text})
"""
import json, pathlib, random, datetime
import requests

OUTDIR = pathlib.Path(__file__).parents[1] / "corpus"
URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
UA = "Vizuara-SLM-Assignment/0.1 (educational research; harman2504sandhu@gmail.com)"
SEED = 20260801
HELDOUT_FRAC = 0.15

def render(c):
    name = c["name"]
    typ = c.get("type", "")
    race = c.get("race", "")
    attr = c.get("attribute")
    arch = c.get("archetype")
    frame = c.get("frameType", "")
    if "Monster" in typ:
        seg = [x for x in (attr, race, typ) if x]
        line = f'"{name}" is a ' + " ".join(seg)
        if frame == "link" and c.get("linkval") is not None:
            line += f', Link-{c["linkval"]}'
        elif c.get("level") is not None:
            line += f', {"Rank" if frame == "xyz" else "Level"} {c["level"]}'
        if c.get("atk") is not None:
            if frame == "link":
                line += f' with {c["atk"]} ATK'
            else:
                line += f' with {c["atk"]} ATK / {c.get("def")} DEF'
    else:  # spell / trap
        line = f'"{name}" is a {race} {typ}'.replace("  ", " ").strip()
    if arch:
        line += f', part of the "{arch}" archetype'
    text = line + "."
    desc = (c.get("desc") or "").strip()
    if desc:
        text += f"\nEffect: {desc}"
    bl = c.get("banlist_info") or {}
    status = []
    if bl.get("ban_tcg"): status.append(f'TCG {bl["ban_tcg"]}')
    if bl.get("ban_ocg"): status.append(f'OCG {bl["ban_ocg"]}')
    if status:
        text += "\nForbidden/Limited status: " + ", ".join(status) + "."
    return text

def newest_date(cards):
    dates = []
    for c in cards:
        for m in (c.get("misc_info") or []):
            for k in ("tcg_date", "ocg_date"):
                if m.get(k):
                    dates.append(m[k])
    return max(dates) if dates else None

def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    print("fetching YGOPRODeck cardinfo (misc=yes) ...")
    r = requests.get(URL, params={"misc": "yes"}, headers={"User-Agent": UA}, timeout=120)
    r.raise_for_status()
    cards = r.json()["data"]
    cutoff = newest_date(cards)

    records = [{"title": c["name"], "text": render(c)} for c in cards]
    rng = random.Random(SEED)
    rng.shuffle(records)
    n_heldout = int(len(records) * HELDOUT_FRAC)
    for i, rec in enumerate(records):
        rec["doc_id"] = f"card-{i:05d}"
        rec["source"] = "cardfacts"
        rec["split"] = "heldout" if i < n_heldout else "train"
    records.sort(key=lambda r: r["doc_id"])

    out = OUTDIR / "cardfacts.jsonl"
    total = 0
    with out.open("w", encoding="utf-8") as f:
        for rec in records:
            total += len(rec["text"].encode("utf-8"))
            f.write(json.dumps({k: rec[k] for k in ("doc_id", "title", "source", "split", "text")},
                               ensure_ascii=False) + "\n")

    stats = {
        "source": "cardfacts (YGOPRODeck v7)",
        "cards": len(records), "MB": round(total / 1e6, 3),
        "heldout": n_heldout, "train": len(records) - n_heldout,
        "snapshot_fetch_date": datetime.date.today().isoformat(),
        "newest_card_release_in_data": cutoff,
        "license_note": "stats/metadata = facts (free); effect text © Konami/4K Media, "
                        "labeled fair-use context only, not counted toward the 20 MB free-prose floor",
    }
    json.dump(stats, (OUTDIR / "cardfacts_stats.json").open("w"), indent=2)
    print(json.dumps(stats, indent=2))
    print(f"\nwrote {out} ({len(records)} cards, {total/1e6:.2f} MB)")

if __name__ == "__main__":
    main()
