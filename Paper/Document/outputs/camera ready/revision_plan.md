# OS_Didiot — Revision Plan (Camera Ready)

**Manuscript:** OSO-2026-0019 — "Evaluating Media Equality in Generative Audiovisual Composition Using Modality Constraint and Replay-Based Reveal"
**Decision:** Minor revision
**Editor:** Dr Antonino Chiaramonte
**Deadline:** 20 May 2026 (≈ 2.5 weeks from today, 4 May 2026)
**Source of truth for edits:** `OS_Didiot_inline.md` (this folder). Rebuild PDF/DOCX from the markdown when the text is settled.

---

## 1. Workflow

1. Edit `OS_Didiot_inline.md` in this folder. Treat run_006 as the frozen submitted version.
2. Track changes in a "Response to Reviewers" letter as we go (draft below in §6) — each reviewer concern → what was changed → page/section reference. The OS portal gives a free-text box for this; reviewers expect it.
3. After all textual edits are in, regenerate `OS_Didiot_inline.pdf` via `build_pdf.py`, then export DOCX (Pandoc or via Pages).
4. Commit at meaningful checkpoints (e.g. "abstract rewrite", "related work expansion", "spelling pass") so the revision history is legible if Tom needs to roll back.

---

## 2. Mapping — reviewer concerns → actions

### 2.1 Abstract rewrite (both reviewers)
**Problem:** Reads technically/machine-generated; does not communicate gist (what / how / what it offers) in broad strokes.
**Action:**
- Rewrite as a 4-move structure:
  1. The aspiration and the problem (parity in AV practice; why it doesn't come for free).
  2. What this study explores and why it matters (research question in plain language; why a coupled generative instrument is a useful case).
  3. How (the modality-constraint + replay protocol — described in plain language, not as a list of variables).
  4. What it offers (a method other researchers/practitioners can adopt; a vocabulary for cue-conflict and rebinding).
- Strip jargon-density: keep "intermedial", "media equality", but unpack on first use. Cut bracketed parentheticals like "(constructive and destructive interactions between media features)" — move definition to body.
- Avoid ChatGPT-tells: "this article evaluates", "we propose a lightweight evaluation template", parallel "while X, Y" constructions, three-item lists with rhythmic phrasing.
- Defer N=9 to later in the abstract or omit; mention sample-size caveat once explicitly.
- Target ≈ 200–250 words (current is ~220).

### 2.2 Theoretical framing — opening claim needs support (both reviewers)
**Problem:** §1 ¶1 — "Electroacoustic audiovisual composition is often discussed through models that implicitly privilege one medium…" — no examples, no refs.
**Action:**
- Add 2–3 supporting citations for each side of the privilege claim:
  - Sound-led / image-as-illustration: visual-music tradition framed through musical structure (e.g. Hyde, Garro, McDonnell).
  - Image-led / sound-as-enhancement: film-sound tradition where score/foley supports diegesis (Chion already cited; Cook 1998 contest model already cited — make use of it explicitly here).
- Add a counter-citation showing the field has critiqued these defaults (Hill, Harris, Coulter).
- ~3 sentences expansion, not a full paragraph — this is intro framing, not survey.

### 2.3 Theoretical framing — Related Work breadth (Reviewer 1, primary)
**Problem:** §2 leans heavily on Chion + media-theory scaffolding (Rajewsky, Elleström). Reviewer wants a wider net of *critical frameworks for encountering AV compositions*.
**Action:** Add one focused paragraph (or extend existing one) integrating:
- **Hill (2013/2019)** — interpretation framework for electroacoustic AV music (audience-encounter focus; fit reviewer's "frameworks for encountering").
- **Harris (2021)** — *Composing Audiovisually*; contemporary monograph on AV composition practice and parity.
- **Garro** — composer's reflections on AV parity and visual-music defaults.
- **Coulter (2010, OS 15(1))** — "media pairing" typology — direct framework for sound-image relations.
- **Cohen** — Congruence-Association Model (CAM) — psychology-of-AV-perception framework, complements Chion.
- Optionally **Hyde (2012, OS)** for visual-music-in-OS context.
- Frame as: "Beyond Chion's audio-vision, several frameworks have been developed specifically for encountering and composing AV works…"
- Aim ≈ 150–250 words added; do not balloon §2.

### 2.4 RQ1 — define "meaning" (Reviewer 2)
**Problem:** RQ1 uses "meaning" without definition; not addressed in body.
**Action:**
- In §1.1 (or early §1.2 right before RQs), insert a short clarifier:
  > In this study we use *meaning* in a deliberately limited sense: the perceived content and significance that participants attribute to the audiovisual output — what the work seems to be "about" or "doing" experientially — rather than semantic reference. RQ1 therefore asks whether sound and light are experienced as *contributing comparably* to that perceived content, not whether either carries semantic content in isolation.
- Cross-reference this in §4.5 / §5.1 where attentional hierarchy and "negotiated practice" are discussed — these are where "meaning-contribution" actually surfaces in results, but it is currently implicit.
- Alternative, lighter touch: replace "meaning" in RQ1 with "the perceived audiovisual experience" if Tom prefers to dodge the term entirely. **Decision needed from Tom.**

### 2.5 Cite Chiaramonte for "intermedial interference" (Reviewer 2)
**Problem:** Reviewer says "p.3 penultimate paragraph — just reference Chiaramonte". Currently §1.1 ¶1 *uses* the term but doesn't cite at point of definition; the citation appears earlier in §1 ¶1 and again in §2 ¶4. Reviewer didn't notice / wants it at point of definition.
**Action:** Add `(Chiaramonte 2024)` at the end of the first sentence of §1.1: "Intermedial interference is used here, following Chiaramonte (2024), to denote…" — explicit attribution at point of use, even if redundant with earlier cite. Costs nothing, eliminates the concern.

### 2.6 "Visually salient geometric regularities" — clarify (Reviewer 2)
**Location:** §2 last paragraph (Besada et al. cite).
**Action:** Replace with plainer phrasing: "where visible patterns and shapes within the lattice (for example, neighbouring pitch classes forming familiar triangular or row-like groupings) can bias harmonic expectation". Keep the Besada cite.

### 2.7 Sample size framing (Reviewer 1)
**Problem:** §5.4 ("Limits and scope") acknowledges this but reviewer wants it foregrounded and reframed positively as foundational research.
**Action:**
- Strengthen §5.4: explicitly say "N = 9 supports analytic, not statistical, generalisation"; position as **foundational / pilot work that establishes a method larger studies can adopt**.
- Add one sentence in §6 (Conclusion) reinforcing this framing — currently the conclusion does not flag scope at all.
- Optionally add a single sentence near the end of the abstract: "We position this as foundational practice-based research, with the method ready for larger-scale follow-up." — makes the framing visible to reviewers/readers up-front.

### 2.8 Machine-generated phrasing pass (Reviewer 2)
**Problem:** Abstract, intro, body have stretches that read AI-written.
**Action:** Targeted prose-edit pass for these tells:
- Three-item parallel lists with rhythmic phrasing ("retain practice-based validity, produce analysable evidence within realistic artistic development timelines, connect participant experience…")
- "It treats X not only as Y, but as Z" / "X is not only A, it is also B"
- Hedge-stacks ("This article takes a design-and-evaluation position on that prompt.")
- Empty connectives ("In such systems, the compositional site shifts away from…")
- Repeated "lightweight evaluation template/method" — pick one phrasing.
- Acknowledgement already declares ChatGPT use — that's good; no need to remove the disclosure, but the prose itself needs Tom's voice.
- **Approach:** I'll do a first pass targeting the worst offenders (abstract, §1, §1.1, §1.2, §5.1) and Tom does a read-through. Avoid editing results quotes or method specifics.

### 2.9 Spelling errors (Reviewer 2)
**Confirmed errors I spotted:**
- L335: "didnt" → "didn't"
- L335: "intersting" → "interesting"
- L337: "perfomance" → "performance"
- L501: "audiovisuallly" (triple l) → "audiovisually"
- Need full proofread pass for the rest.
**Action:** Full proofread after substantive edits are done.

---

## 3. Reference sourcing — strategy and shortlist

### 3.1 Strategy
1. Verify each candidate exists and is accessible (DOI, OS volume/issue, publisher).
2. Read enough of each to write a defensible 1-line characterisation — no citing-from-the-abstract.
3. Prefer Organised Sound and adjacent journals (CMJ, JNMR, Leonardo Music Journal) where possible — fits the audience.
4. Anything not verifiable in the time available is dropped, not approximated.

### 3.2 Shortlist (priority order)

**Tier A — strong fit, near-certain useful:**
- **Hill, A. (2013).** *Interpreting Electroacoustic Audio-Visual Music* (PhD, De Montfort). Direct framework for AV interpretation; addresses reviewer's "frameworks for encountering" concern head-on. Also possibly Hill's later journal articles in OS or eContact!.
- **Harris, L. (2021).** *Composing Audiovisually: Perspectives on Audiovisual Practice and Composition.* Routledge. Recent monograph; directly engages parity, hierarchy, and compositional process.
- **Coulter, J. (2010).** "Electroacoustic music with moving images: the art of media pairing." *Organised Sound* 15(1): 26–34. Typology of sound-image pairings — within-journal precedent.

**Tier B — likely useful, depends on argument fit:**
- **Garro, D. (2012).** "From Sonic Art to Visual Music: Divergences, convergences, intersections." *Organised Sound* 17(2): 103–113. Or "A Glow on Pythagoras' Curtain". Composer's perspective on AV parity and visual-music traditions.
- **Hyde, J. (2012).** "Musique concrète thinking in visual music practice." *Organised Sound* 17(2): 170–178. Visual-music side of the privilege claim.
- **McDonnell, M. (2020 or related).** Visual music articles in OS. Historical critical perspective.
- **Cohen, A. J. (2013).** "Congruence-Association Model of music and multimedia" (in *Psychology of Music in Multimedia*, OUP). Perception framework complementing Chion.

**Tier C — only if needed for specific claims:**
- Spielmann, Y. *Video: The Reflexive Medium* (2008) — intermedial.
- Battey, B. — AV mapping CMJ articles.
- Whitelaw, M. *Metacreation* (2004) — for generative-art context if needed.

### 3.3 What to verify first
Tom should confirm:
- **Library access:** does Tom have access to *Organised Sound*, CMJ, OUP books? (If at Bristol, yes.)
- **Existing relationship to literature:** has Tom read Harris (2021) or Hill (2013)? If yes, the citation is honest; if not, we need real reading time, not skim-citing.

---

## 4. Execution order (proposed)

1. **Reference sourcing first** (parallel to other work) — without verified refs the framing edits are blocked. Aim: shortlist verified within 2–3 days.
2. **Abstract** — rewrite from scratch using the 4-move structure. This is the highest-visibility change and benefits from being done early so other prose can echo its tone.
3. **Intro §1 ¶1 + framing** — add the supporting citations once Tier A refs are in hand.
4. **§1.1 + §1.2** — RQ1 "meaning" definition; Chiaramonte cite at point of use; minor prose edits.
5. **§2 Related Work** — the broader-frameworks paragraph; Besada clarification.
6. **§5.4 + §6** — sample-size reframing.
7. **Whole-paper machine-phrasing edit pass** — targeted, not blanket.
8. **Full spelling/proofread pass.**
9. **Rebuild PDF/DOCX**, export, sanity-check figures and refs.
10. **Response-to-reviewers letter** — finalise (drafted in parallel from step 2 onward).
11. **Submit** via Manuscript Central.

---

## 5. Open questions for Tom

1. **RQ1 wording:** keep "meaning" + add a definition (Option A), or replace with "perceived audiovisual experience" (Option B)? See §2.4. *I'd lean Option A — defining "meaning" is more substantive and addresses the reviewer's concern at face value. Option B is safer but reads as side-stepping.*
2. **Library access** for Hill PhD, Harris (2021 Routledge), Coulter (OS 2010) — do you have these to hand or shall I see what I can pull from open sources?
3. **Voice:** how aggressive on the AI-phrasing pass? My instinct is to rewrite the worst offenders and leave already-fine prose alone — but if you want me to make the whole thing read more like your earlier writing, it'd help to point me at one paragraph you wrote yourself end-to-end as a voice anchor.
4. **Author response letter — tone:** brief and bulleted, or longer/explanatory? OS reviewers usually expect concise point-by-point.
5. **DOCX rebuild path:** the submitted DOCX likely went through Pages — do you want me to keep that path (md → Pages → DOCX) or switch to Pandoc (md → DOCX directly) to avoid manual reformatting?

---

## 6. Response-to-reviewers letter — draft skeleton

To be filled in as edits are made. Structure:

> **Editor's overall comments**
> - Theoretical framing → addressed by [refs added in §1 ¶1 and §2; see pp. X–Y]
> - Abstract → rewritten in full; see new abstract on p. 1
> - "meaning" in RQ1 → defined in §1.1 (p. X) and threaded through §4.5 / §5.1
> - Chiaramonte cite for intermedial interference → added at point-of-definition in §1.1
> - Spelling errors → full proofread completed
> - Machine-generated phrasing → revised across abstract, §1, §1.1, §1.2, §5.1
> - Sample-size framing → strengthened in §5.4 and §6 (and noted in abstract)

> **Reviewer 1**
> - [quote concern] → [response + page]

> **Reviewer 2**
> - [quote concern] → [response + page]

Keep responses concrete: quote the concern, describe the change in 1–2 sentences, point to the page/section.

---

## 7. What I will *not* change without Tom's say-so

- Method (§3) — no reviewer flagged it; leave alone.
- Results (§4) — quotes, figures, numbers. Only spelling fixes inside quoted participant text (with `[sic]` if substantive).
- Title — reviewers did not flag; leaving as submitted.
- ChatGPT acknowledgement — keep the disclosure; reviewers raised the prose tone, not the disclosure itself.
- Figures — no figure changes flagged.
