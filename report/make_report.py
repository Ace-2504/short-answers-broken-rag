"""Generate the one-page report.pdf (A4, 11pt) — written in Harman's voice, the five
required points. Pure-python (fpdf2), no native deps."""
from fpdf import FPDF

A = (46, 125, 184)      # A base (blue)
B = (199, 127, 20)      # B fine-tune (amber)
C = (21, 155, 118)      # C retrieval (green)
INK = (25, 29, 27); MUT = (95, 100, 96); LINE = (205, 210, 205)

pdf = FPDF(format="A4", unit="mm")
pdf.set_margins(17, 15, 17)
pdf.set_auto_page_break(auto=False)
pdf.add_page()
W = 210 - 34   # content width

def h(txt, size=11):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", size); pdf.set_text_color(*INK)
    pdf.multi_cell(W, 5.2, txt)
def body(txt, size=10.5):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", size); pdf.set_text_color(*INK)
    pdf.multi_cell(W, 4.2, txt, markdown=True)
def gap(mm=1.7): pdf.ln(mm)

# ---- title ----
pdf.set_font("Helvetica", "B", 16); pdf.set_text_color(*INK)
pdf.multi_cell(W, 7, "Fine-tuning vs. retrieval: a Yu-Gi-Oh small language model")
pdf.set_x(pdf.l_margin); pdf.set_font("Helvetica", "", 9); pdf.set_text_color(*MUT)
pdf.multi_cell(W, 4.5, "Harman Singh Sandhu  -  Build an Enterprise SLM from Scratch  -  August 2026")
pdf.ln(1); pdf.set_draw_color(*LINE); pdf.line(17, pdf.get_y(), 17+W, pdf.get_y()); gap(2.5)

# ---- 1. what I built ----
h("What I built")
body("I built three versions of a Yu-Gi-Oh question-answering system on top of Gemma 2 2B and "
     "compared them on the same 60 held-out questions. System A is the untouched base model, "
     "closed-book; System B is my QLoRA fine-tune of the same model, also closed-book; and System C "
     "is that fine-tune with a retriever feeding it passages from my own corpus. I picked Yu-Gi-Oh "
     "rulings and card facts on purpose: the base model clearly does not know them - it scored about "
     "1.5 out of 12 on a quick probe and confidently made up card text - so the three systems can "
     "actually separate. Every answer is graded by a reference-grounded AI judge that compares "
     "against a written gold answer and its exact evidence, so the scores are reproducible by "
     "someone who does not play the game.")
gap()

# ---- 2. headline table ----
h("Headline result (mean score / 10, n = 60)")
gap(1)
rows = [("A  base, closed-book", "3.98 +/- 0.39", "-", MUT),
        ("B  fine-tune, closed-book", "5.25 +/- 0.54", "+1.27 over A,  p = 0.007  (significant)", INK),
        ("C  fine-tune + retrieval", "8.05 +/- 0.42", "+2.80 over B,  p < 0.001  (significant)", INK)]
pdf.set_font("Helvetica", "", 10)
for name, score, note, col in rows:
    y = pdf.get_y()
    pdf.set_fill_color(*(A if name[0]=="A" else B if name[0]=="B" else C))
    pdf.rect(17, y+0.8, 2.2, 4.2, "F")
    pdf.set_text_color(*INK); pdf.set_xy(21, y); pdf.cell(58, 5.5, name[3:] if name[1]==" " else name)
    pdf.set_font("Helvetica", "B", 10); pdf.cell(26, 5.5, score)
    pdf.set_font("Helvetica", "", 10); pdf.set_text_color(*col); pdf.cell(0, 5.5, note, ln=1)
pdf.set_x(pdf.l_margin); pdf.set_font("Helvetica", "", 8.5); pdf.set_text_color(*MUT)
pdf.multi_cell(W, 4, "Paired bootstrap 95% CI + t-test + Wilcoxon, on the same items.")
gap(1.5)

# ---- 3. the one plot ----
h("The one plot I would show")
gap(1)
cx, cy = 17, pdf.get_y()          # chart origin
ch, cw = 34, 90                   # height, width
base_y = cy + ch
pdf.set_draw_color(*LINE); pdf.line(cx, base_y, cx+cw, base_y)
for i,(lab, val, col) in enumerate([("A", 3.98, A), ("B", 5.25, B), ("C", 8.05, C)]):
    bh = val/10*ch
    bx = cx + 8 + i*28
    pdf.set_fill_color(*col); pdf.rect(bx, base_y-bh, 20, bh, "F")
    pdf.set_font("Helvetica", "B", 9); pdf.set_text_color(*INK)
    pdf.set_xy(bx, base_y-bh-4.6); pdf.cell(20, 4, f"{val:.2f}", align="C")
    pdf.set_font("Helvetica", "", 8.5); pdf.set_text_color(*MUT)
    pdf.set_xy(bx, base_y+0.6); pdf.cell(20, 4, lab, align="C")
pdf.set_xy(cx+cw+4, cy+4)
pdf.set_font("Helvetica", "", 9); pdf.set_text_color(*MUT)
pdf.multi_cell(W-cw-6, 4.3, "Each step up the ladder is real, and retrieval is the biggest single "
               "jump - that is the whole experiment in one picture.")
pdf.set_y(base_y+6)

# ---- 4. expected vs disagreed ----
h("What I expected, and where it disagreed")
body("Before I ran it I expected that fine-tuning closed-book would not really "
     "beat the base model, because teaching a model question-answer pairs teaches it the shape of an "
     "answer, not the facts. Retrieval matched that expectation - it was the biggest win by far. But one "
     "result surprised me: my fine-tune did significantly beat the base model closed-book (+1.27). "
     "When I broke the score down, the reason was groundedness, which went from 0.18 up to 0.87. The "
     "base model gives long, confident, wrong answers; my fine-tune learned to give tight, careful "
     "ones that do not invent card details, and the judge rewards that. The facts still only come "
     "from retrieval - correctness only jumps from 2.35 to 3.85 when I turn retrieval on - so the "
     "fine-tune learned a better answer shape, not new facts. The thesis held; the fine-tune just "
     "helped a little more than I expected.")
gap()

# ---- 5. time-sink ----
h("What cost me the most time, and what I would change")
body("The corpus cost me the most time. My first instinct was to grab card text, but a lot of that "
     "is short, repeated effect text, and my cleaning kept either throwing away good rulings or "
     "keeping junk. I lost the most hours tailoring the cleaning to what my corpus actually held - "
     "for example I found a rare set of struck-through 'previously official' rulings that my markup "
     "stripper was silently keeping as if they were still current. Next time I would read a few "
     "hundred real pages before writing a single cleaning rule, and I would separate 'commentary "
     "about cards' from 'the cards themselves' from day one, instead of discovering halfway through "
     "that my retriever could not answer 'what does this card do' because I had never put the card "
     "facts in.")
gap()

# ---- 6. what I learnt ----
h("What I learnt")
body("Three things stuck with me. First, **RAG's ceiling is the reader, not the retriever.** When I "
     "tested 'what is the effect of Blackwing Full Armor Master?' live, the retriever handed my model the "
     "exact card text and it still scored only 6 out of 10 - it named the card's type and material, but "
     "dropped the actual effect. Recall is already 0.93, so the limit is my 2.6-billion model finishing "
     "what it is handed, which is why System C stops near 8, not 10. Second, **a reference-grounded judge "
     "can grade a domain it does not know.** On that same question it scored the two made-up answers 1 out "
     "of 10 with groundedness zero, purely by checking them against the evidence I hand it - never needing "
     "to know the card itself. Third, **match the retriever to the domain's shape.** Yu-Gi-Oh questions "
     "turn on exact card names that dense embeddings blur, so pairing them with plain keyword search "
     "lifted recall@5 to 0.93 - and that hybrid is what feeds System C.")

# ---- footer ----
pdf.set_y(-14); pdf.set_draw_color(*LINE); pdf.line(17, pdf.get_y(), 17+W, pdf.get_y())
pdf.ln(1.5); pdf.set_font("Helvetica", "", 8); pdf.set_text_color(*MUT)
pdf.cell(0, 4, "Model: huggingface.co/Ace-2504/gemma-2-2b-yugioh-qa    -    total cost ~ $3 of the $25 budget.")

pdf.output("report/report.pdf")
print("wrote report/report.pdf ; pages:", pdf.page_no())
