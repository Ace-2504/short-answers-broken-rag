"""Shared helpers for the Phase-2 pipeline (generation, gauntlet, held-out)."""
import json, os, re, sys, time, pathlib

def gemini():
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        sys.exit("Set GEMINI_API_KEY first.")
    from google import genai
    return genai.Client(api_key=key), os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

def call_json(cli, model, prompt, retries=2):
    """Call the model and parse a JSON reply, tolerating code fences. Retries on error."""
    for attempt in range(retries + 1):
        try:
            txt = cli.models.generate_content(model=model, contents=prompt).text.strip().strip("`")
            if txt.lower().startswith("json"):
                txt = txt[4:].strip()
            return json.loads(txt)
        except Exception:
            if attempt == retries:
                raise
            time.sleep(1.5)

def chunk(text, size=1000, overlap=150):
    step = max(1, size - overlap)
    out, i, n = [], 0, len(text)
    while i < n:
        out.append(text[i:i+size])
        if i + size >= n:
            break
        i += step
    return out

def toks(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))

def containment(a, b):
    ta = toks(a)
    return len(ta & toks(b)) / max(1, len(ta))

def load_ids(path, key):
    """Ids already present in a JSONL file — used to skip finished work on resume."""
    done = set()
    if pathlib.Path(path).exists():
        for line in pathlib.Path(path).open(encoding="utf-8"):
            try:
                done.add(json.loads(line)[key])
            except Exception:
                pass
    return done

def load_jsonl(path):
    p = pathlib.Path(path)
    return [json.loads(l) for l in p.open(encoding="utf-8")] if p.exists() else []
