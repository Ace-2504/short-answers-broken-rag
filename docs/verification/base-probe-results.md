# Base-model ignorance probe — Gemma 2 2B (closed-book, System A)

> **Re-run 2026-08-05.** The original probe (2026-08-01) recorded only the aggregate (~1.5/12);
> the per-question answers were not saved, so this reproduces them by re-running the *exact same*
> 12 questions against the base model (`google/gemma-2-2b-it`, adapter disabled, greedy). Each
> answer is graded against its **known-correct answer** by the reference-grounded judge
> (`gemini-3.1-flash-lite`, 0–10). Generation is not perfectly deterministic, so wording may
> differ from the original run — but the finding (the base is ignorant of Yu-Gi-Oh) reproduces.

**Score this run: 3.0 / 12 correct** (3 correct, 0 partial, 9 wrong). Original run: ~1.5 / 12.

| # | Category | Judge /10 | Verdict |
|---|----------|:---------:|---------|
| 1 | GENERAL | 9 | correct |
| 2 | BASIC RULE | 10 | correct |
| 3 | BASIC RULE | 1 | wrong / fabricated |
| 4 | CLASSIC STAT | 1 | wrong / fabricated |
| 5 | CLASSIC STAT | 1 | wrong / fabricated |
| 6 | MODERN CARD | 1 | wrong / fabricated |
| 7 | MODERN CARD | 1 | wrong / fabricated |
| 8 | MODERN CARD | 1 | wrong / fabricated |
| 9 | RULING | 8 | correct |
| 10 | RULING | 2 | wrong / fabricated |
| 11 | RULING | 3 | wrong / fabricated |
| 12 | MODERN ARCHETYPE | 3 | wrong / fabricated |

---

### 1. [GENERAL] In one sentence, what is the Yu-Gi-Oh! Trading Card Game?

- **Known-correct answer:** A collectible card game where players duel using monster, spell and trap cards.
- **Gemma 2 2B (base) said:**

  > The Yu-Gi-Oh! Trading Card Game is a collectible card game where players duel each other using monsters, spells, and traps to reduce their opponent's Life Points to 0.

- **Graded:** **9/10** — *correct* (correctness 5/5, completeness 2/2, groundedness 1/2, clarity 1/1)
- **Judge note:** The answer is accurate but includes external information about Life Points not found in the evidence.

### 2. [BASIC RULE] In Yu-Gi-Oh, how many cards does a player draw during a normal Draw Phase?

- **Known-correct answer:** One card.
- **Gemma 2 2B (base) said:**

  > A player draws **1** card during a normal Draw Phase in Yu-Gi-Oh. 
  > 
  > This is a fundamental part of the game's mechanics.

- **Graded:** **10/10** — *correct* (correctness 5/5, completeness 2/2, groundedness 2/2, clarity 1/1)
- **Judge note:** The answer is accurate and matches the provided evidence.

### 3. [BASIC RULE] What is the minimum number of cards allowed in a Main Deck in the TCG?

- **Known-correct answer:** 40 cards (max 60).
- **Gemma 2 2B (base) said:**

  > The minimum number of cards allowed in a Main Deck in the TCG is **30**.

- **Graded:** **1/10** — *wrong / fabricated* (correctness 0/5, completeness 0/2, groundedness 0/2, clarity 1/1)
- **Judge note:** The answer provides an incorrect number that contradicts the provided evidence.

### 4. [CLASSIC STAT] What is the ATK of the card 'Dark Magician'?

- **Known-correct answer:** 2500 ATK.
- **Gemma 2 2B (base) said:**

  > The ATK of the card 'Dark Magician' is **2000**. 
  > 
  > This is a standard fact about the card, and it's not subject to any specific rulings or changes.

- **Graded:** **1/10** — *wrong / fabricated* (correctness 0/5, completeness 0/2, groundedness 0/2, clarity 1/1)
- **Judge note:** The answer provides the incorrect ATK value and contradicts the evidence.

### 5. [CLASSIC STAT] What is the ATK of 'Blue-Eyes White Dragon'?

- **Known-correct answer:** 3000 ATK.
- **Gemma 2 2B (base) said:**

  > The ATK of 'Blue-Eyes White Dragon' is **2500**. 
  > 
  > This is a straightforward answer based on the card's definition in the Yu-Gi-Oh! Trading Card Game.

- **Graded:** **1/10** — *wrong / fabricated* (correctness 0/5, completeness 0/2, groundedness 0/2, clarity 1/1)
- **Judge note:** The answer provides incorrect information that contradicts the gold evidence.

### 6. [MODERN CARD] What Attribute is the card 'Ash Blossom & Joyous Spring'?

- **Known-correct answer:** FIRE.
- **Gemma 2 2B (base) said:**

  > The card 'Ash Blossom & Joyous Spring' has the **Dark** Attribute.

- **Graded:** **1/10** — *wrong / fabricated* (correctness 0/5, completeness 0/2, groundedness 0/2, clarity 1/1)
- **Judge note:** The answer contradicts the provided evidence.

### 7. [MODERN CARD] Describe what the monster effect of 'Sky Striker Ace - Raye' does.

- **Known-correct answer:** When a Sky Striker card is sent to GY / a monster is Special Summoned to opponent's field, you can Tribute Raye to Special Summon a Sky Striker Ace from Deck (except Raye).
- **Gemma 2 2B (base) said:**

  > 'Sky Striker Ace - Raye' is a powerful Level 4 EARTH monster with a unique effect that makes it a valuable addition to any Sky Striker deck. 
  > 
  > Here's a breakdown of its effect:
  > 
  > **Effect:**
  > 
  > * **"When a Sky Striker monster you control is sent to the Graveyard by a card effect, you can send 1 "Sky Striker" monster from your hand to the Graveyard."**
  > 
  > **Explanation:**
  > 
  > * **Trigger:** This effect is triggered when a Sky Striker monster you control is sent to the Graveyard by any card effect. 
  > * **Sending a Monster:** You can choose to send any "Sky Striker" monster from your hand to the Graveyard. 
  > * **Flexibility:** This effect allows you to strategically send a specific Sky Striker monster to the Graveyard, potentially to activate other effects or to set up for future plays.
  > 
  > **Key Points:**
  > 
  > * **Targeted Sending:** You can choose which "Sky Striker

- **Graded:** **1/10** — *wrong / fabricated* (correctness 0/5, completeness 0/2, groundedness 0/2, clarity 1/1)
- **Judge note:** The answer describes an effect completely different from the gold evidence.

### 8. [MODERN CARD] What does the hand trap 'Maxx "C"' do?

- **Known-correct answer:** If your opponent Special Summons a monster, you draw 1 card for each; activated from hand.
- **Gemma 2 2B (base) said:**

  > You're asking about the hand trap **Maxx "C"**.  Here's the breakdown:
  > 
  > **Maxx "C" is a hand trap that can be activated in response to a card being activated or used.**
  > 
  > **How it works:**
  > 
  > * **Target:** Maxx "C" targets a specific card in your opponent's hand.
  > * **Effect:**  It negates the activation of the targeted card. 
  > * **Timing:** It can be activated at any time during your opponent's turn, even if they've already played a card.
  > * **Activation:** You can activate it by declaring it as a hand trap.
  > 
  > **Important Notes:**
  > 
  > * **No Specific Card:** Maxx "C" doesn't target a specific card by name. It targets any card in your opponent's hand.
  > * **No Effect on the Player's Hand:** Maxx "C" doesn't affect the player's hand. It

- **Graded:** **1/10** — *wrong / fabricated* (correctness 0/5, completeness 0/2, groundedness 0/2, clarity 1/1)
- **Judge note:** The answer provides completely incorrect information that contradicts the provided evidence.

### 9. [RULING] During the Damage Step, can you activate a normal (non-Quick-Play) Spell Card?

- **Known-correct answer:** No. Only a narrow set of effects can be activated in the Damage Step; normal Spells cannot.
- **Gemma 2 2B (base) said:**

  > No, you cannot activate a normal Spell Card during the Damage Step. 
  > 
  > Here's why:
  > 
  > * **The Damage Step is a specific phase:** It's the phase where damage is dealt and effects related to damage are resolved. 
  > * **Spell Cards are activated in other phases:** Spell Cards are activated in the Spell & Trap Card phases, or during the Main Phase, depending on the card's effect. 
  > * **Normal Spell Cards are not Quick-Play:**  Quick-Play Spell Cards can be activated during the Spell & Trap Card phase.
  > 
  > **In short:** The Damage Step is for dealing damage and resolving effects related to damage. Spell Cards are activated in other phases.

- **Graded:** **8/10** — *correct* (correctness 5/5, completeness 2/2, groundedness 0/2, clarity 1/1)
- **Judge note:** Groundedness is 0 because the answer includes information about 'Spell & Trap Card phases' and specific phases for normal spells which are not present in the provided evidence.

### 10. [RULING] In Yu-Gi-Oh, what does it mean for an effect to be 'missing the timing'?

- **Known-correct answer:** An optional 'When... you can' effect cannot activate if its trigger condition was not the last thing to happen in the chain / resolution.
- **Gemma 2 2B (base) said:**

  > In Yu-Gi-Oh, an effect being "missing the timing" means that it **doesn't activate or take effect at the correct moment according to the game's rules.** 
  > 
  > Here's a breakdown:
  > 
  > **Timing is Crucial:**
  > 
  > * **Activation:** Many card effects require specific timing to activate. This could be:
  >     * **When a card is activated:**  Like activating a spell or trap card.
  >     * **When a card is played:** Like summoning a monster.
  >     * **When a card is destroyed:** Like removing a monster from the field.
  > * **Effect Resolution:** Once an effect is activated, it needs to resolve according to the rules. This means it needs to be properly applied and its effects are carried out.
  > 
  > **Why Does Timing Matter?**
  > 
  > * **Preventing Unintended Actions:**  Timing ensures that effects don't trigger in the wrong situation, preventing unintended actions or unfair advantages.
  > * **Maintaining Game

- **Graded:** **2/10** — *wrong / fabricated* (correctness 1/5, completeness 0/2, groundedness 0/2, clarity 1/1)
- **Judge note:** The answer fails to mention the 'When... you can' clause or the requirement that the trigger must be the last thing to happen.

### 11. [RULING] Can 'Effect Veiler' negate the effect of a monster on the field during the opponent's Main Phase, and does it work on effects already on the field?

- **Known-correct answer:** Effect Veiler targets a face-up monster the opponent controls and negates its effects until end of turn; it is a Quick Effect used in the opponent's Main Phase.
- **Gemma 2 2B (base) said:**

  > You're asking about a very important aspect of 'Effect Veiler' and its interaction with monster effects. Here's the breakdown:
  > 
  > **Yes, 'Effect Veiler' can negate the effect of a monster on the field during the opponent's Main Phase.**
  > 
  > **Here's why:**
  > 
  > * **'Effect Veiler' is a Spell/Trap card that negates the activation of monster effects.**  This means it can stop the activation of a monster's effect, even if it's already on the field.
  > * **'Effect Veiler' can negate effects that are already on the field.** This is because it negates the effect of the monster itself, not just the effect that's being activated.
  > 
  > **Important Considerations:**
  > 
  > * **Timing:** 'Effect Veiler' can negate effects during the opponent's Main Phase, which is the phase where they can activate monster effects.
  > * **Effect Type:** 'Effect Veiler' can

- **Graded:** **3/10** — *wrong / fabricated* (correctness 1/5, completeness 1/2, groundedness 0/2, clarity 1/1)
- **Judge note:** The answer incorrectly identifies Effect Veiler as a Spell/Trap card, which contradicts the evidence provided.

### 12. [MODERN ARCHETYPE] In the 'Tearlaments' archetype, what typically happens when a Tearlaments monster is sent from the Deck or hand to the Graveyard?

- **Known-correct answer:** Its effect triggers to Fusion Summon a Tearlaments Fusion monster by shuffling materials from GY, and mills cards.
- **Gemma 2 2B (base) said:**

  > When a Tearlaments monster is sent from the Deck or hand to the Graveyard in Yu-Gi-Oh!, it triggers a specific effect that can significantly impact the game. 
  > 
  > Here's the breakdown:
  > 
  > **The Effect:**
  > 
  > * **Tearlaments' effect is triggered when a Tearlaments monster is sent to the Graveyard.** This effect is unique to the Tearlaments archetype and is triggered regardless of whether the monster was sent by a card effect or a player's action.
  > 
  > **The Trigger:**
  > 
  > * **The effect is triggered when the Tearlaments monster is sent to the Graveyard.** This means it's not about the monster being sent to the Graveyard, but rather the specific action of sending it to the Graveyard.
  > 
  > **The Result:**
  > 
  > * **The Tearlaments monster's effect is activated.** This effect can vary depending on the specific Tearlaments monster, but it often involves gaining a benefit or activating a special

- **Graded:** **3/10** — *wrong / fabricated* (correctness 1/5, completeness 0/2, groundedness 1/2, clarity 1/1)
- **Judge note:** The answer fails to mention the Fusion Summon or the milling effect, which are the core components of the gold answer.
