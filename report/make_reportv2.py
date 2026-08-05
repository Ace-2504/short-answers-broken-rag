"""Generate report.pdf (A4, one page) - written in Harman's voice; foregrounds the RAG study and the
biased/unbiased dual evaluation. Pure-python (fpdf2), no native deps. Output: report.pdf (repo root)."""
from fpdf import FPDF

A = (46, 125, 184)      # A base (blue)
B = (199, 127, 20)      # B fine-tune (amber)
C = (21, 155, 118)      # C retrieval (green)
INK = (25, 29, 27); MUT = (95, 100, 96); LINE = (205, 210, 205)
LH = 3.4                # shared body line height

pdf = FPDF(format="A4", unit="mm")
pdf.set_margins(17, 14, 17)
pdf.set_auto_page_break(auto=True, margin=9)
pdf.add_page()
W = 210 - 34   # content width

def h(txt, size=9.9):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", size); pdf.set_text_color(*INK)
    pdf.multi_cell(W, 4.0, txt); pdf.ln(0.1)
def body(txt, size=9.0):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", size); pdf.set_text_color(*INK)
    pdf.multi_cell(W, LH, txt, markdown=True)
def bullet(txt, size=9.2, indent=3.4):     # hanging indent: '-' at margin, wrapped text aligns under text
    x0 = pdf.l_margin; y = pdf.get_y()
    pdf.set_font("Helvetica", "", size); pdf.set_text_color(*INK)
    pdf.set_xy(x0, y); pdf.cell(indent, LH, "-")
    pdf.set_x(x0 + indent); pdf.multi_cell(W - indent, LH, txt, markdown=True)
def gap(mm=1.0): pdf.ln(mm)

# ---- title: repository name + hero tagline ----
pdf.set_font("Helvetica", "B", 15); pdf.set_text_color(*INK)
pdf.multi_cell(W, 6.2, "Short-Answers-Broken-RAG", align="C")
pdf.set_x(pdf.l_margin); pdf.set_font("Helvetica", "", 10.5); pdf.set_text_color(*MUT)
pdf.multi_cell(W, 4.7, "Fine-tuning vs. retrieval - why the reader, not the retriever, is a small model's ceiling", align="C")
pdf.ln(0.8); pdf.set_draw_color(*LINE); pdf.line(17, pdf.get_y(), 17+W, pdf.get_y()); gap(2.0)

# ---- 1. what I built ----
h("1.  What I built")
body("I built three versions of a Yu-Gi-Oh question-answering system on Gemma 2 2B and compared them on the "
     "same held-out questions. System A is the untouched base model, closed-book; System B is my QLoRA "
     "fine-tune, also closed-book; System C is that fine-tune with a retriever feeding it passages from my "
     "own corpus. I chose Yu-Gi-Oh rulings and card facts on purpose - the base model clearly does not know "
     "them (about 3 out of 12 on a hand probe, confidently inventing card text) - so the three systems can "
     "actually separate. Every answer is graded by a reference-grounded AI judge against a written gold "
     "answer and its exact evidence.")
gap()

# ---- 2. headline: two evaluations ----
h("2.  Headline result - two evaluations (mean score / 10, n = 60 each)")
gap(0.5)
pdf.set_font("Helvetica", "B", 9.1); pdf.set_text_color(*MUT)
pdf.set_x(21); pdf.cell(70, 5.0, "System"); pdf.cell(36, 5.0, "Biased 60"); pdf.cell(0, 5.0, "Balanced 60", ln=1)
for name, bi, un, col in [("A   base, closed-book", "3.98", "1.93", A),
                          ("B   fine-tune, closed-book", "5.25", "2.62", B),
                          ("C   fine-tune + retrieval", "8.05", "8.25", C)]:
    y = pdf.get_y()
    pdf.set_fill_color(*col); pdf.rect(17, y+0.8, 2.2, 3.9, "F")
    pdf.set_xy(21, y); pdf.set_font("Helvetica", "", 9.6); pdf.set_text_color(*INK); pdf.cell(70, 5.0, name)
    pdf.set_font("Helvetica", "B", 9.6); pdf.cell(36, 5.0, bi); pdf.cell(0, 5.0, un, ln=1)
gap(0.5)
body("I evaluated twice, because my first 60 questions were skewed (45% rulings, 45% card facts): once on "
     "that original set, and again on a category-balanced 'unbiased' 60 (15 per category). On the balanced "
     "set the closed-book systems collapse while **C holds up**, so retrieval's advantage is larger once the "
     "bias is removed. Paired significance (bootstrap CI + t-test + Wilcoxon): B beats A strongly on the "
     "biased set (+1.27, p = 0.007) but only marginally on the balanced one (+0.68, p = 0.04); retrieval "
     "(B -> C) is strongly significant on both.")
gap()

# ---- 3. the RAG study (centerpiece) ----
h("3.  The RAG study - is retrieval or the reader the bottleneck?")
body("System C stalls near **8/10** on answer quality, even though retrieval already fetches the right "
     "passage **93%** of the time. These are two different measures - 93% is a retrieval number (is the "
     "right passage found?), while 8/10 is the judge's answer-quality score - so the gap between them is "
     "itself the clue: the passage is usually there, but the answer still is not a 10. That is why I pointed "
     "my experiments at the remaining 7% - the questions where the RAG could be blamed - to see whether fixing "
     "retrieval would fix the score. Every retrieval-side experiment failed to move it, which is what "
     "indirectly proved the problem is the reader, not my RAG implementation. What each showed:")
gap(0.5)
bullet("**Reranking** (re-order the retrieved passages): no help - slightly worse, 8.05 -> 7.55.")
bullet("**Deeper retrieval** (pull more passages): recall rose 0.93 -> 0.97, but the score did not move.")
bullet("**Repairing a split-effect chunk**: I reconstructed a card's missing effect text back into the "
       "context - and the model still dropped it.")
bullet("**Six cheap reader fixes** (self-consistency, self-checking, quote-then-answer): all failed.")
bullet("**A stronger reader on the same context**: the only thing that worked - given the identical "
       "passages, a stronger model produced the complete, correct answer where my fine-tune under-answered.")
gap(0.5)
body("So even after aiming squarely at the 7%, nothing on the retrieval side moved the number - the limit is "
     "my 2.6-billion model reading what it already has.")
gap(0.6)
body("**A few things the debugging pinned down:**")
bullet("The reranker was not broken - it kept the gold passage at rank 1 (recall@5 stayed 0.93) and only "
       "reshuffled the surrounding passages, which is enough to wobble a small model's answer.")
bullet("Two-thirds of the lost points are 'card-fact' questions, but reading them showed the model inverting "
       "yes/no rulings it had the passage for - a reading failure, not a missing fact.")
bullet("The one real chunking bug I found (an effect split across two passages) I repaired - and the model "
       "still dropped the recovered clause: proof the context was already enough.")
gap()

# ---- 4. what I concluded ----
h("4.  What I concluded")
body("**The bottleneck is not the retriever, it is the reader.** Fine-tuning teaches the **shape** of an "
     "answer and retrieval supplies the **facts** - correctness only jumps once real passages are in the "
     "prompt - but a small model mis-reads passages it already holds, and no retrieval trick fixes that. "
     "Retrieval engineering is a dead end once recall is high; only a stronger reader, or retraining the "
     "model to read from its context, moves the number. I confirmed this with a controlled test: on the "
     "same passages, a stronger model produced complete, correct answers where my 2.6B reader did not.")
gap()

# ---- 5. what surprised me / open question ----
h("5.  What surprised me")
body("My fine-tune's own gain shrank to marginal once I balanced the categories - a good reminder that my "
     "earlier, skewed test set had been quietly flattering it, and that I should check the make-up of an "
     "evaluation set before trusting a headline number.")
gap()

# ---- 6. what I learnt ----
h("6.  What I learnt")
body("Three lessons stuck with me. First, **test the cheap thing before you assume** - the small "
     "experiments (reranking, deeper retrieval, chunk-repair) told me where the problem was not, and saved "
     "me from paying to fix the wrong thing. Second, **a skewed test set quietly flatters your model** - my "
     "fine-tune looked clearly better until I rebalanced the categories and its edge shrank to marginal, so "
     "I now check the make-up of an evaluation set before I trust a number. Third, **a reference-grounded "
     "judge lets me score a domain I do not know** - handing it a gold answer and its evidence gave me "
     "reproducible marks on Yu-Gi-Oh without my being an expert.")
gap()

# ---- 7. an open question (open-ended close) ----
h("7.  An open question")
body("One thing I could not fully test, and I would put it to anyone reading this: my fine-tuning answers had "
     "a median length of only 17 words. Could that short-answer habit be leaking into System C, making it "
     "drop details even when the passage clearly holds them - a better explanation for the incomplete answers "
     "than anything on the retrieval side? I would welcome other views on it.")
gap(0.6)
body("**External evidence for the reader bottleneck.** Pandey (2026), \"Can Small Language Models Use What "
     "They Retrieve?\", arXiv:2603.11513 - even a 7B model uses an oracle-retrieved passage only ~15% of the "
     "time. Baturova et al. (2026), \"Little Brains, Big Feats\", arXiv:2606.30062 - on fixed context, the "
     "reader alone swings answer quality. Liu et al. (2025), \"ROSE-RAG\", Findings of ACL - prompt-only "
     "fixes fail on small readers.")

# ---- footer ----
gap(0.8)
pdf.set_draw_color(*LINE); pdf.line(17, pdf.get_y(), 17+W, pdf.get_y()); gap(0.5)
pdf.set_x(pdf.l_margin); pdf.set_font("Helvetica", "", 8.2); pdf.set_text_color(*MUT)
pdf.multi_cell(W, 3.4, "A study by Harman Singh Sandhu, CSE student at JIIT Noida and BS Data Science, IIT "
               "Madras.    Published 6 August 2026.")

pdf.output("report.pdf")
print("wrote report.pdf ; pages:", pdf.page_no())
