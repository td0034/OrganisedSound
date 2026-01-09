1) Lock the codebook (so every plot has meaning)

Your internal IDs map cleanly to constructs.

Part A (pre-block, 7-point Likert): A_1 … A_7

Satisfaction

Clear intention

Able to steer toward intention

Interface understandable/workable

Useful surprise

Unpredictable/frustrating

Confidence others would find interesting

Part B (post-reveal replay, 7-point Likert): B_1 … B_12

Same underlying process (fusion)

Media balance (equality)

Coherent/legible relationship

Constructive interference

Destructive interference

Perceptual overload

Revealed modality matched expectation

Reveal changed interpretation

Plausible causal story

System autonomy

Relied on visual pattern cues

Relied on Tonnetz/music-theory expectations

Also: param_influence (top 1–3 parameters), aim, strategy, expectation_vs_outcome, interference_notes, plus end-of-session rankings.

This mapping is the backbone of every subsequent figure/table.

2) Primary analysis: within-subject comparisons across conditions

Because every participant does all three blocks, the clean default is repeated-measures:

Recommended statistical approach (robust for small N)

Start with descriptives (median + IQR, mean + SD).

Use Friedman tests (non-parametric repeated measures) per item for A_1–A_7 and B_1–B_12.

Then pairwise Wilcoxon signed-rank tests with Holm correction for a small number of pre-registered “headline” outcomes.

Pre-register (or at least foreground) a small outcome set

For Organised Sound, I’d prioritise:

A_3 steerability (agency under constraint)

B_1 fusion and B_2 equality

B_3 coherence

B_4 vs B_5 interference

B_6 overload

B_11 visual overfitting and B_12 theory overfitting (ties directly to your “Tonnetz misleads productively” argument)

Everything else becomes supporting/contextual.

3) Immediate “quick win” findings you can already report (descriptively)

These are useful because they translate straight into a results narrative + figures:

A) Preference and “most intermedial”

7/8 participants ranked Block C as their overall preferred outcome (end ranking).

Most participants also selected C as “most intermedial.”

That is a clean headline figure.

B) Clear modality signatures that support your theory

Even without external raters, your post-reveal items show strong, interpretable patterns:

B_11 (“Relied on visual pattern cues”) sharply separates conditions:
Visual-only highest, audio-only lowest, audiovisual in between.
This is exactly what you want if your claim is that modality access changes compositional strategy and subsequent interpretation.

B_12 (“Relied on Tonnetz/music-theory expectations”) is not highest in visual-only; it rises when audio is present.
That supports your desired argument: the Tonnetz grid is often treated visually rather than theoretically, creating space for creative “misreadings” (which you can connect to the cognitive/HCI Tonnetz literature you cited).

C) Parameter influence shows modality-dependent steering strategies

From the param-influence selections:

Rate and Scale dominate overall.

Visual-only emphasises density/structure parameters more (e.g., Max Population / neighbour constraints).

Audio-only and audiovisual emphasise Scale most strongly.

This is an excellent bridge between interface manipulation and intermedial outcome.

4) Build two composite indices (optional, but very OS-friendly)

Composites help you avoid dumping 19 Likert plots into the paper.

(i) Intermediality / “Intermedial Space” index (post-reveal)

Example:

IntermedialityIndex = mean(B_1, B_2, B_3, B_4) − mean(B_5, B_6)

Interpretation: perceived fusion/equality/coherence/constructive interference minus destructive/overload.

(ii) Agency / steerability index (pre-block)

Example:

AgencyIndex = mean(A_2, A_3, A_4) − A_6 (or treat A_6 separately)

Interpretation: intention + steerability + usability against frustration.

These indices plot beautifully as three boxplots (A/B/C) and give you an “executive summary” result.

5) Order/learning effects (you should test and either control or report)

You deliberately counterbalanced the 6 permutations, which is good—but with small N, learning still shows up easily.

Recommended checks:

Plot A_4 (interface understandable) by block position (1st/2nd/3rd).

If there is a learning slope, you can:

Include position as a covariate in a simple mixed model later (if you go parametric), or

Report it as a limitation and show the descriptive plot.

This is worth doing because reviewers often ask “is the audiovisual condition preferred just because it was last?”

6) Qualitative analysis: lightweight but defensible thematic coding

Your free-text fields are short but high value. Do this in a structured way:

Coding targets

Expectation mismatch mechanisms (why B_7 is low): “I assumed X, but got Y”

Causal stories (B_9): “lights drive sound”, “sound drives lights”, “hidden system drives both”

Overfitting cues: visual pattern → harmonic inference; Tonnetz theory → pattern expectation

Interference descriptors: masking, reinforcement, contradiction, overload, surprise, narrative shift

Control strategies: “I chased density”, “I chased harmony”, “I stabilised”, “I sought chaos”

Output for the paper

5–8 coded themes

A small table: theme × condition frequency (counts)

3–6 short illustrative excerpts (very short quotes)

This lets you make your “Tonnetz misleads productively” argument with evidence, not assertion.

7) Strongest next step: link survey to artefacts (audio/video features)

This is where the paper becomes unusually compelling.

Even if you don’t have external raters yet, you can compute objective descriptors per clip and correlate them with self-report:

Audio features (even from MIDI logs)

Note density (notes/sec), event rate

Pitch-class entropy / diversity

Tonal centroid movement (very simple proxy)

Polyphony proxy (overlapping note count)

Video features (panel camera)

Mean brightness / contrast

Spatial entropy (how “spread” activations are)

Motion energy (frame-to-frame change)

Then test:

Does B_3 coherence correlate with lower motion energy + moderate note density?

Does B_6 overload correlate with high motion energy + high note density?

Does visual-only composition produce higher spatial entropy than audio-only?

A single “features vs ratings” figure can do a lot of work in OS.

8) Figures that will look “shit hot” and write themselves

If you want a tight OS results section, I’d aim for 6 core figures:

Fig. 1 Preference: stacked bar of rank-1 choices (A/B/C) + “most intermedial” counts

Fig. 2 Agency: A_3 (steerability) + A_6 (frustration) by condition

Fig. 3 Intermedial core: B_1 (fusion), B_2 (equality), B_3 (coherence) by condition

Fig. 4 Interference: B_4, B_5, B_6 by condition

Fig. 5 Overfitting / misreading: B_11 and B_12 by condition (this supports your Besada-adjacent argument)

Fig. 6 Parameter influence: heatmap or grouped bars of “top selected parameters” by condition

Then, if you have time:

Fig. 7 objective features vs ratings (one “hero” scatter/relationship plot)

9) Addendum: how it supports your PhD arc (and strengthens OS)

Use addendum items to connect this OS study to your broader thesis claim (“tools that make it easier…”):

High-value addendum analyses:

Return likelihood vs confidence to recreate (often separates “fun/interesting” from “learnable/repeatable”)

Authorship attribution (user vs system vs shared) as an agency lens

Context of use (gallery/club/home/education) and target user (novice/musician/visual artist) as design implications

Add/remove one thing as a focused roadmap (cluster responses into UI, sound engine, feedback, collaboration)

These are exactly the kinds of “evaluation-to-design” bridges that make prototyping read as a PhD, not a hobbyist build log.

10) TODO: missing elements to resolve before final write-up

- Order/learning effects: block ordering is missing in outputs; identify a reliable timestamp source (e.g., `updated_at` in sections export or external video-clip metadata) and compute block position before plotting A_4 by position.
- Composite indices (Intermediality, Agency): decide whether to include in main text or supplementary; update narrative accordingly.
- Addendum coding: cluster contexts, change requests, authorship attributions, titles; add counts + short quotes; generate clean tables.
- Features vs ratings: compute objective audio/video features and correlate with B_3/B_6 (optional but high-impact).
- Figure numbering: prefer Fig. 1a/1b or combine preference + “most intermedial” into one figure; update captions.
