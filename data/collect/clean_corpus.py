"""Phase-1 corpus cleaning — implements docs/corpus-cleaning-system.md.

Cleans the YUGIPEDIA prose only (card-facts pass through untouched, per decision).
Default DRY_RUN: reports exactly what each rule/threshold would drop, deletes nothing.
Set DRY_RUN=False to write data/corpus/corpus_clean.jsonl (+ card-facts appended).

Pipeline (Yugipedia): C1 line/boilerplate/citation/short-line -> C2 length(200)/language
-> C3 MinHash-LSH dedup(0.80) -> C4 (split already tagged; report cross-split near-dups).
"""
import json, re, os, pathlib, collections, statistics
from langdetect import detect, LangDetectException
from datasketch import MinHash, MinHashLSH

DRY_RUN = os.environ.get("APPLY") != "1"
DIR = pathlib.Path(__file__).parents[1] / "corpus"
YUGI = DIR / "corpus.jsonl"
CARDS = DIR / "cardfacts.jsonl"

DOC_FLOOR = 200          # C2.1 (lowered from slides' 600)
SYMBOL_MAX = 0.30        # C1a
SHINGLE_K = 5            # C3
NUM_PERM = 128           # C3
DUP_THRESHOLD = 0.80     # C3
DEDUP_EXEMPT = {"tips"}  # C3: distinct cards share searcher lists -> keep every card's page

SECTION_HEADERS = {"previously official rulings", "mentions in other rulings",
                   "judge program forum rulings", "official rulings"}
DROP_LINE_RES = [
    re.compile(r"^\s*Category:", re.I),
    re.compile(r"^\s*(File|Image):", re.I),
    re.compile(r"^\s*\|.*\|\s*$"),
    re.compile(r"^\s*https?://\S+\s*$", re.I),
    re.compile(r"(all rights reserved|©|\(c\)\s*\d{4})", re.I),
    re.compile(r"^\s*page\s+\d+(\s+of\s+\d+)?\s*$", re.I),
]
CITATION_RE = re.compile(r"Konami\s*[A-Za-z]*\s*FAQ.*$")      # C1b (to end of line)
INLINE_HEAD_RE = re.compile(r"=={2,}[^=]+=={2,}")             # C1b ===...===

def symbol_ratio(s):
    ns = [c for c in s if not c.isspace()]
    return sum(1 for c in ns if not c.isalnum()) / max(1, len(ns))

def clean_doc(text, tally):
    """Apply C1a/C1b/C1c to one doc's lines. Returns cleaned text; updates tally."""
    out = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        # C1b in-line strips first (so a citation-only tail doesn't survive)
        line2 = INLINE_HEAD_RE.sub("", line)
        line2 = CITATION_RE.sub("", line2).strip()
        if line2 != line:
            tally["C1b_inline_strips"] += 1
        line = line2
        if not line:
            tally["C1b_became_empty"] += 1
            continue
        # C1a drop-line rules
        low = line.lower()
        if low in SECTION_HEADERS:
            tally["C1a_section_header"] += 1; continue
        if any(r.search(line) for r in DROP_LINE_RES):
            tally["C1a_boilerplate"] += 1; continue
        if symbol_ratio(line) > SYMBOL_MAX:
            tally["C1a_symbol_heavy"] += 1; continue
        # C1c short-line: <40 chars kept only if ends in terminal punctuation
        if len(line) < 40 and line[-1] not in ".!?":
            tally["C1c_short_dropped"] += 1; continue
        out.append(line)
    return "\n".join(out)

def shingle_minhash(text):
    words = text.split()
    if len(words) < SHINGLE_K:
        sh = {" ".join(words)} if words else set()
    else:
        sh = {" ".join(words[i:i+SHINGLE_K]) for i in range(len(words)-SHINGLE_K+1)}
    m = MinHash(num_perm=NUM_PERM)
    if sh:
        m.update_batch([s.encode("utf-8") for s in sh])
    return m, sh

def main():
    docs = [json.loads(l) for l in YUGI.open(encoding="utf-8")]
    n_cards = sum(1 for _ in CARDS.open(encoding="utf-8"))
    raw_mb = sum(len(d["text"].encode()) for d in docs) / 1e6
    tally = collections.Counter()

    # ---- C1 ----
    cleaned = []
    for d in docs:
        ct = clean_doc(d["text"], tally)
        cleaned.append({**d, "text": ct})
    c1_mb = sum(len(d["text"].encode()) for d in cleaned) / 1e6

    # ---- C2.1 length ----
    lens = [len(d["text"]) for d in cleaned]
    band_under = sum(1 for L in lens if L < DOC_FLOOR)
    band_200_600 = sum(1 for L in lens if DOC_FLOOR <= L < 600)
    after_len = [d for d in cleaned if len(d["text"]) >= DOC_FLOOR]

    # ---- C2.3 language ----
    non_en = []
    for d in after_len:
        try:
            if detect(d["text"][:2000]) != "en":
                non_en.append(d)
        except LangDetectException:
            non_en.append(d)
    non_en_ids = {id(d) for d in non_en}
    after_lang = [d for d in after_len if id(d) not in non_en_ids]

    # ---- C3 MinHash-LSH dedup (tips exempt: distinct cards share searcher lists) ----
    lsh = MinHashLSH(threshold=DUP_THRESHOLD, num_perm=NUM_PERM)
    kept, dropped_dup = [], []
    for i, d in enumerate(after_lang):
        if d["source"] in DEDUP_EXEMPT:
            kept.append(d)                       # exempt -> always keep
            continue
        m, sh = shingle_minhash(d["text"])
        if sh and lsh.query(m):
            dropped_dup.append(d)
        else:
            lsh.insert(str(i), m)
            kept.append(d)
    kept_mb = sum(len(d["text"].encode()) for d in kept) / 1e6

    # ---- searched-by preservation check ----
    sb_before = sum(1 for d in docs if "can be searched by" in d["text"])
    sb_after = sum(1 for d in kept if "can be searched by" in d["text"])

    # ---- report ----
    print(f"{'='*66}\nDRY RUN — corpus cleaning (Yugipedia only; card-facts untouched)\n{'='*66}")
    print(f"card-facts: {n_cards} passages passed through unchanged (no cleaning)\n")
    print(f"Yugipedia raw: {len(docs)} docs, {raw_mb:.2f} MB\n")
    print("C1 line cleaning (lines removed / modified):")
    for k in ["C1a_section_header","C1a_boilerplate","C1a_symbol_heavy","C1c_short_dropped",
              "C1b_inline_strips","C1b_became_empty"]:
        print(f"   {k:24s}: {tally[k]:>7d}")
    print(f"   chars after C1: {c1_mb:.2f} MB ({100*(raw_mb-c1_mb)/raw_mb:.1f}% removed)\n")
    print(f"C2.1 length floor = {DOC_FLOOR}:")
    print(f"   docs < {DOC_FLOOR} (dropped)      : {band_under}")
    print(f"   docs in [{DOC_FLOOR},600) (kept, would die at 600): {band_200_600}")
    print(f"   -> after length: {len(after_len)} docs\n")
    print(f"C2.3 language (non-English dropped): {len(non_en)}")
    print(f"   -> after language: {len(after_lang)} docs\n")
    print(f"C3 MinHash-LSH dedup (Jaccard {DUP_THRESHOLD}, k={SHINGLE_K}, h={NUM_PERM}):")
    print(f"   near-duplicate docs dropped: {len(dropped_dup)}")
    print(f"   -> kept: {len(kept)} docs, {kept_mb:.2f} MB\n")
    print(f"searched-by lines preserved: {sb_before} docs before -> {sb_after} after "
          f"(Pattern-1 kept)\n")
    print("FUNNEL:")
    print(f"   raw {len(docs)} ({raw_mb:.2f}MB) -> C1 -> len {len(after_len)} -> "
          f"lang {len(after_lang)} -> dedup KEPT {len(kept)} ({kept_mb:.2f}MB)")
    print(f"   free-prose floor 20 MB: {'OK' if kept_mb>=20 else 'BELOW — needs attention'}")
    print(f"   + card-facts {n_cards} passages -> total corpus docs {len(kept)+n_cards}")

    print("\nsamples — docs in [200,600) that a 600-floor would have killed:")
    for d in [x for x in after_len if len(x["text"]) < 600][:3]:
        print(f"   [{d['source']}] {d['title']} ({len(d['text'])}c): {d['text'][:110]!r}")
    print("\nsamples — near-duplicates flagged by MinHash:")
    for d in dropped_dup[:3]:
        print(f"   [{d['source']}] {d['title']} ({len(d['text'])}c): {d['text'][:110]!r}")

    if not DRY_RUN:
        out = DIR / "corpus_clean.jsonl"
        with out.open("w", encoding="utf-8") as f:
            for d in kept:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
            for l in CARDS.open(encoding="utf-8"):
                f.write(l)
        print(f"\nAPPLIED -> wrote {out} ({len(kept)} prose + {n_cards} cardfacts)")

if __name__ == "__main__":
    main()
