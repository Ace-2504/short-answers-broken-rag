"""Probe whether Gemma 2 2B (base) knows Yu-Gi-Oh. Closed-book (System A):
no context supplied. Spread from general trivia -> classic stats -> modern
cards -> specific rulings (our target question type). Each has a known answer.

Result on 2026-08-01: ~1.5/12 correct. Base model gets basic rules wrong,
cannot recall Dark Magician / Blue-Eyes ATK, and confidently fabricates card
text for modern cards/rulings. Confirms the domain-ignorance requirement by
measurement (see docs/assignment-verification.md, VERIFIED section).

Point URL at a running Gemma-2-2b-it base endpoint. This was run against the
local serve_api.py (model_id 'gemma-base'); adjust URL/MODEL/payload as needed.
"""
import requests, json, textwrap

URL = "http://localhost:8000/generate"
MODEL = "gemma-base"

PROBES = [
    ("GENERAL", "In one sentence, what is the Yu-Gi-Oh! Trading Card Game?",
     "A collectible card game where players duel using monster, spell and trap cards."),
    ("BASIC RULE", "In Yu-Gi-Oh, how many cards does a player draw during a normal Draw Phase?",
     "One card."),
    ("BASIC RULE", "What is the minimum number of cards allowed in a Main Deck in the TCG?",
     "40 cards (max 60)."),
    ("CLASSIC STAT", "What is the ATK of the card 'Dark Magician'?",
     "2500 ATK."),
    ("CLASSIC STAT", "What is the ATK of 'Blue-Eyes White Dragon'?",
     "3000 ATK."),
    ("MODERN CARD", "What Attribute is the card 'Ash Blossom & Joyous Spring'?",
     "FIRE."),
    ("MODERN CARD", "Describe what the monster effect of 'Sky Striker Ace - Raye' does.",
     "When a Sky Striker card is sent to GY / a monster is Special Summoned to opponent's field, "
     "you can Tribute Raye to Special Summon a Sky Striker Ace from Deck (except Raye)."),
    ("MODERN CARD", "What does the hand trap 'Maxx \"C\"' do?",
     "If your opponent Special Summons a monster, you draw 1 card for each; activated from hand."),
    ("RULING", "During the Damage Step, can you activate a normal (non-Quick-Play) Spell Card?",
     "No. Only a narrow set of effects can be activated in the Damage Step; normal Spells cannot."),
    ("RULING", "In Yu-Gi-Oh, what does it mean for an effect to be 'missing the timing'?",
     "An optional 'When... you can' effect cannot activate if its trigger condition was not the "
     "last thing to happen in the chain / resolution."),
    ("RULING", "Can 'Effect Veiler' negate the effect of a monster on the field during the "
     "opponent's Main Phase, and does it work on effects already on the field?",
     "Effect Veiler targets a face-up monster the opponent controls and negates its effects until "
     "end of turn; it is a Quick Effect used in the opponent's Main Phase."),
    ("MODERN ARCHETYPE", "In the 'Tearlaments' archetype, what typically happens when a "
     "Tearlaments monster is sent from the Deck or hand to the Graveyard?",
     "Its effect triggers to Fusion Summon a Tearlaments Fusion monster by shuffling materials "
     "from GY, and mills cards."),
]

def ask(question):
    r = requests.post(URL, json={"model_id": MODEL, "question": question,
                                 "max_new_tokens": 140, "temperature": 0.2, "top_p": 0.9},
                      timeout=120)
    r.raise_for_status()
    d = r.json()
    return d.get("completion") or d.get("answer") or d.get("text") or json.dumps(d)

def main():
    print(f"Probing {MODEL} @ {URL}\n" + "=" * 70)
    for i, (cat, q, gold) in enumerate(PROBES, 1):
        try:
            a = ask(q).strip()
        except Exception as e:
            a = f"[ERROR: {e}]"
        print(f"\n[{i:02d}] ({cat})")
        print("Q   :", q)
        print("GOLD:", textwrap.shorten(gold, 200))
        print("GEMMA:", textwrap.fill(a, 100, subsequent_indent="       "))
        print("-" * 70)

if __name__ == "__main__":
    main()
