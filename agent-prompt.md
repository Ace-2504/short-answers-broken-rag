Fine-tune Gemma 2 2B, put a retriever behind it, and ship it
Course: Build an Enterprise SLM from Scratch

What this assignment is really asking
In the sessions we ran an experiment that did not go the way most people expect. We fine-tuned Gemma 2 2B on 7,141 question and answer pairs from our own corpus and evaluated it closed-book against the untouched base model, on 58 held-out questions with a reference-grounded judge. It did not win. The grounded fine-tune came out 0.36 points below base, which on 58 items is not a real difference (t = -1.15), and the fine-tune that had been through closed-book QA training first came out 1.52 points below base, which is (t = -5.3). Fine-tuning on question and answer pairs teaches a model the shape of an answer. The facts were never in the gradient signal in a form the model could store.

Then we put a retriever in front of the same models and gave them the passages at inference time. Base plus retrieval scored 2.74 points higher than base alone on the same items (t = 5.06). Retrieval was the entire win. And once retrieval was switched on, the fine-tuned model and the base model were indistinguishable from each other (-0.34, t = -0.92), which is worth sitting with for a moment: all of that training bought nothing that the retriever did not already provide.

Your job in this assignment is to reproduce that experiment honestly on a domain of your own choosing, and to report what you find even if it disagrees with what we found. A carefully measured negative result is a complete answer here. An unmeasured claim is not.

You will build three systems and compare them on the same held-out questions:

SystemWhat it isA
google/gemma-2-2b-it
, untouched, closed bookBYour fine-tune of Gemma 2 2B, closed bookCYour fine-tune of Gemma 2 2B, with your retriever supplying passages

Part 1: Build a domain corpus and a dataset
Pick a domain that is not legal or financial, so you are not retracing our corpus. Medical guidelines, a codebase's documentation, tax rules, a sport's rulebook, university regulations, and product manuals all work. The one hard requirement is that the domain has text a base model will not already know well, because otherwise every system scores the same and you have measured nothing.

Collect the corpus. At least 20 MB of raw text. Say where it came from and confirm you are allowed to use it.

Clean and chunk it. We chunked at 1,000 characters with 150 characters of overlap. Use whatever you can defend.

Generate a supervised set. Use a strong teacher model to write question and answer pairs from passages of your corpus. We produced 7,141 clean pairs and threw away a lot more than that. Aim for at least 2,000 clean pairs.

Gate the quality. Every pair the teacher produces is not automatically good. Have a judge score them and drop the bottom, and report how many you generated against how many survived.

Hold out a test set before you train anything. At least 60 questions, and they must come from passages that never enter training. Each held-out item needs three fields:

{"id": "qa-000",
 "question": "...",
 "gold": "the correct answer, written out",
 "evidence": "the verbatim sentences from your corpus that prove the gold answer"}
The
evidence
field is not optional. It is what lets your judge grade without needing to know your domain.

Deliverable:
data/
with your cleaned corpus statistics,
train.jsonl
,
heldout.jsonl
, and a short
DATA.md
recording counts at every stage from raw documents to surviving pairs.

Part 2: Fine-tune Gemma 2 2B
Fine-tune
google/gemma-2-2b-it
on your supervised set. QLoRA on a single A100 or L4 is enough, and it is what we used for the Gemma stage. Full fine-tuning is allowed if you have the GPUs.

Required:

Report the exact configuration: rank, alpha, target modules, learning rate, schedule, batch size, sequence length, epochs, and the precision you trained and served in.

Plot training and validation loss. Report final validation perplexity. Ours was 4.26 for the Gemma closed-book stage.

Push the adapter or the merged model to the Hugging Face Hub, public, with a model card that states what it was trained on.

Serve it behind an HTTP endpoint. Modal with
scale-to-zero
keeps this affordable, and the pattern in
modal_qasft_gemma.py
is the one to copy.

One trap worth naming, because it cost us time. If you serve a base model and an adapter from the same process and toggle the adapter per request, concurrent requests will race and you will silently serve the wrong model. Either serve them from separate containers or serialize the requests.

Deliverable: the training script, the loss curves, the Hub link, and a live endpoint URL.

Part 3: Build the retriever and wire it in
Build a real retriever over your corpus. Not a keyword search, and not a toy list of ten passages held in memory.

Embed every chunk. We used
BAAI/bge-small-en-v1.5
, 384 dimensions, normalized so that inner product equals cosine similarity. Any sentence embedding model is fine as long as you say which one and why.

Build a vector index. FAISS is the obvious choice. We used an IVF-SQ8 index with
nlist = 4096
over roughly 11 million chunks. At your corpus size a flat index may be perfectly reasonable, and if so, say that it is and move on.

Expose a
/retrieve
endpoint that takes a question and returns the top k chunks with their scores and their source document.

Wire retrieval into generation. The retrieved passages go into the prompt, and your fine-tuned model answers from them.

Then measure the retriever on its own, separately from the generator. For your held-out questions, report recall@k: how often the passage containing the gold evidence appears in the top k. Do this for k of 1, 3, 5 and 10. If recall@5 is poor, no amount of prompt engineering downstream will save system C, and you will want to know that before you blame the model.

If you use an IVF index, remember that the number of probes you search controls a real accuracy and speed tradeoff. We lost a day to an index that was searching too few cells and quietly returning worse passages than it should have. Report the setting you used.

Deliverable: the indexing script, the retrieval endpoint, and a recall@k table.

Part 4: Evaluate all three systems
Run systems A, B and C over the same held-out questions and grade them with an LLM judge.

The judge design matters more than the judge model. Use ours:

Reference grounded. Every judge call carries the question, the gold answer, and the verbatim evidence. The judge compares, it does not recall. This is what makes the grades reproducible by someone who does not know your domain.

Pointwise and blind. One response per call, no model names, no other candidates in the context. Scoring several candidates in one call introduces position bias and anchors them against each other.

A rubric that sums to 10. Ours: correctness 0 to 5, completeness 0 to 2, groundedness 0 to 2, clarity 0 to 1. Groundedness caps at 0 when the model invents a citation or a figure, however fluent the answer is.

A refusal must beat a confident error. Write this into the rubric explicitly, or your judge will reward bluffing.

Then report, for each system:

mean score with a standard error, and a per category breakdown

a paired significance test between A and B, and between B and C, on the same items

at least three examples where the systems disagree, quoted, with your reading of why

The paired test is what turns "C looks higher" into a claim you can defend. With 60 items, differences under about half a point will usually not separate, and saying so is the correct answer.

Deliverable:
eval/responses.json
,
eval/verdicts.json
,
eval/leaderboard.json
, and the harness that produced them. It should be re-runnable and it should skip work it has already finished.

Part 5: Deploy the site and write the report
The site. Extend the website you already have so that a visitor can type a question and see all three systems answer it side by side, live, against your real endpoints. Show the retrieved passages for system C, because that is the part people do not believe until they see it. Include your leaderboard and your recall@k table on the page. Deploy it to Vercel and make sure it works from a phone.

Do not fake it. No pre-recorded answers, no hardcoded numbers that your evaluation did not produce.

The report. One page. A single PDF, one side of A4, readable at 11pt. This constraint is part of the assignment, so do not attach an appendix and do not shrink the font to 8pt.

Cover, in your own words:

What you built and on what domain, in three or four sentences.

Your headline table: the three systems, their scores, and whether the differences are significant.

The one plot you would show if you had only one.

What you expected before you ran it, and where the result disagreed with you.

The single thing that cost you the most time, and what you would do differently.

Point 4 is the one we will read most closely. "Everything worked" is not a finding.

What to submit
A single repository containing:

data/            DATA.md, train.jsonl, heldout.jsonl, corpus statistics
train/           fine-tuning script, configs, loss curves
rag/             chunking, embedding, index build, retrieval endpoint
eval/            harness, responses, verdicts, leaderboard, recall@k
site/            the deployed frontend
report.pdf       one page
README.md        how to reproduce everything above, in order
Plus, in the README:

the Hugging Face link to your model

the live URL of your site

your three endpoint URLs

what the whole thing cost you in GPU time and API calls

What we will be looking at
whether the counts in
DATA.md
are honest at every stage, including what you threw away

whether your held-out set was really held out, and whether every item has gold and evidence

whether recall@k was measured before you blamed the model for a weak answer

whether the comparison between systems carries a paired significance test

whether the site shows numbers your own evaluation produced, and nothing else

whether the report says what you learned rather than only what you did

Ground rules
Build your own dataset. Do not fine-tune on our checkpoints or reuse our corpus.

Budget roughly 25 dollars of GPU credit. If you are spending more than that, something is wrong with your setup rather than with your ambition.

Log what you spend. Cost per experiment is engineering information, not an afterthought.

Use of coding assistants is expected and fine. You still have to be able to explain every line in a viva.

Reference material from our build
Everything below is live and is the version of this pipeline we ran in class.

Results you can compare yourself against

the 21 models leaderboard: https://slm-arena-21-site.vercel.app/  every size and every training stage on the same held-out set

gemma closed-book against fine-tuned: https://slm-raft-arena.vercel.app/ , the comparison that did not separate

six way rag comparison: https://slm-raft6-arena.vercel.app/ , where retrieval turns out to be the whole win

Models

fine tuned gemma: https://huggingface.co/thesreedath/slm-gemma-2b-qa

base gemma: https://huggingface.co/google/gemma-2-2b-it