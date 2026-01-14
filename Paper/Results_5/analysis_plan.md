# TZ5 Intermediality Study — Reproducible Quant+Qual Analysis and Figure Pipeline (Organised Sound submission)

1) Purpose and success criteria

Build a single, reproducible Python analysis pipeline that:

- Ingests the master study export (sections_plus_transcriptions.json) containing per-participant, per-block pre/post Likert responses, end-of-session choices, qualitative responses, and parameter influence nominations.

- Outputs publication-ready tables and figures aligned with Organised Sound expectations (EPS/PDF + high-res PNG/TIFF).

- Replaces the current spaghetti/paired-line plots in Results Figures 2–4 with higher-readability graphics, specifically:

  - Multi-panel diverging stacked Likert bars (6/9/12 panels as agreed)
  - Parameter influence heatmap
  - Parameter influence split into 3 condition-specific plots

- Produces audit artifacts (merged block-level dataset, missingness report, log).

Primary acceptance criteria

- Running one command regenerates all outputs deterministically.
- Figures are readable at single/double column widths.
- Output filenames are stable and match the paper’s figure/table numbering plan.
- Table 2 and Table 3 resolve reviewer questions about what is being summarised and how composites are coded.

2) Study model to encode (must match the PDF)

Conditions (within-subject):

- A = Visual-only
- B = Audio-only
- C = Audiovisual

Measures:

- Part A (pre-reveal): A1–A7 (satisfaction, intention clarity, steerability, etc.)

- Part B (post-reveal): B1–B12 (same-process, balance, coherence, constructive/destructive interference, overload, autonomy, cue reliance, etc.)

- End-of-session categorical: rankings, “most intermedial”, “biggest mismatch”

- Parameter influence nominations: up to three per block, analysed by condition

Composite already implied by the manuscript:

- Intermediality Index: B1–B6 with reversals applied (at minimum reverse-code B5 and B6).

3) Inputs and canonical “tidy” data products

Inputs

- sections_plus_transcriptions.json (canonical master source)
- Optional: additional exports (if present) but do not depend on them.

Pipeline must output these canonical intermediate CSVs

- tables/Audit_blocks_long.csv

Columns: participant_id, condition, phase (pre/post/end), item, value, item_label, is_reverse, construct, block_position, timestamps.

- tables/Audit_blocks_wide.csv

One row per participant-condition, with columns A_1..A_7, B_1..B_12, param lists, etc.

- tables/Audit_missingness_report.csv

Per participant, per block, per item missingness and totals.

This “tidy-first” approach is the single biggest enabler of clean multi-panel plots and tables.

4) Required tables (publication + audit)

Table 1: Participant overview (main text)

Goal: contextualise sample + counterbalancing. (You reference this already.)

Contents (as available): participant ID, musical experience, theory familiarity, generative familiarity, Tonnetz familiarity, perceptual notes (colour deficiency, light sensitivity), block order/counterbalance key.

Table 2: Likert descriptive summary by condition (main text or appendix)

Goal: medians [IQR] for A/B/C, with n.

Two-tier strategy (recommended):

Table 2a (main text): a curated subset supporting the main claims (e.g., A3 steerability; A1 satisfaction; A5 useful surprise; A6 frustrating unpredictability; B1 same-process; B3 coherence; B4/B5 interference; B6 overload; B10 autonomy).

Table 2b (appendix/supplement): full A1–A7 and B1–B12.

Table 3: Construct mapping + coding (main text)

Goal: define composites and reversals clearly.

Must include at least:

- Intermediality Index (items, reversals, formula, interpretation)
- Optionally include:

  - Mismatch Index (if you use B7/B8-derived logic)

  - Agency Index (if you use A2–A4 minus A6)

Audit tables (not for the paper, but for robustness)

- Full per-item descriptives (mean, SD, median, IQR) for internal checking.
- Parameter influence counts by condition (raw counts + percentages).

5) Required figures (this is the “new figure plan”)

Figure 1: End-of-session categorical outcomes by condition

Keep the current intent: preference rank, “most intermedial”, “biggest mismatch”.

Improve readability:

- Use horizontal bars or grouped dot/interval plot (counts with labels).
- Ensure consistent condition order A → B → C.

Figure 2 (replacement): Multi-panel diverging stacked Likert bars — Part A (pre-reveal)

Replace the current paired-line A3 spaghetti plot with a panel of diverging stacked Likert bars (6 or 9 panels).

Recommended panel (9):

- A1 satisfaction
- A2 intention clarity
- A3 steerability
- A4 interface workable
- A5 useful surprise
- A6 frustrating unpredictability (mark as negative-direction)
- A7 others would find interesting

(optional) add one “key” qualitative-coded binary if it exists; otherwise omit

Spec:

For each item: one diverging stacked bar per condition (A/B/C), centred on neutral (4).

Show % (or counts) per Likert category.

Figure 3 (replacement): Multi-panel diverging stacked Likert bars — Part B (post-reveal)

Replace the intermediality-index spaghetti plot view with a panel (9 or 12 panels).

Recommended panel (12):

- B1 same-process
- B2 balanced modalities
- B3 coherent/legible relationship
- B4 constructive interference
- B5 destructive interference (negative-direction)
- B6 overload (negative-direction)
- B7 expectation match
- B8 interpretation change
- B9 plausible causal story
- B10 system autonomy
- B11 relied on visual cues
- B12 relied on theory cues

Figure 4 (new): Estimation plot for 2–3 primary contrasts (optional but high value)

If space allows, add one figure with paired-difference estimation (Gardner–Altman style) for your headline claims:

- A3: C−A, C−B, B−A
- Intermediality Index: same contrasts
- B6 overload: same contrasts (or omit if it’s uniformly low)

This turns “a bunch of Likert responses” into effect magnitude + uncertainty, without p-value dependency.

Figure 5 (new): Parameter influence heatmap by condition

Replace/augment the stacked bars with a heatmap:

- Rows: parameters (sorted by overall mentions)
- Columns: A/B/C
- Cell: count or % of participants mentioning that parameter in that condition

Figure 6a/6b/6c (new): Parameter influence split into 3 condition-specific plots

As you requested: three separate plots, one per condition:

- Horizontal bars, sorted descending
- Consistent x-axis scale across all three (for comparability)
- Consider “Top N + Other” if too many parameters

6) Implementation requirements (how the script should be structured)

6.1 One consolidated CLI entry point

Example:
python run_analysis.py --input sections_plus_transcriptions.json --outdir outputs --paper-mode

6.2 A “figure manifest” driving reproducible generation

Create a figures_manifest.json like:

id, title, plot_type, items, input_df, output_basename, size (single/double column), caption_stub.

The script loops over the manifest to generate all figures consistently.

6.3 Modular code layout (recommended)

- io_ingest.py — schema-robust JSON parsing, latest-record selection
- transform.py — long/wide dataframes, reverse-coding, composites
- tables.py — Table 1/2/3 + audit tables
- plots_likert.py — diverging stacked Likert panels
- plots_params.py — heatmap + split condition bars
- plots_outcomes.py — end-of-session categorical figure
- export.py — EPS/PDF/PNG/TIFF export, size presets, naming

6.4 Export formats and sizing

- EPS for submission workflows, plus PDF (vector) for proofing.
- PNG 300 dpi, TIFF 600 dpi where needed.
- Provide single-column and double-column presets and enforce them via the manifest.

6.5 Reversal/coding policy must be explicit and centralised

A single config mapping:

- item → label
- item → direction (positive/negative)
- construct → items + reversals + formula

This feeds Table 3, the composite computations, and correct legend/caption text.

7) QA, validation, and logging

The pipeline must automatically produce:

- A completeness check: expected 9 participants × 3 conditions = 27 blocks, and item-level missingness verification (your manuscript claims 0% missing).

- A stable “analysis fingerprint”: hash of input JSON + git commit hash (if available) written into outputs/log.txt.

Warnings (not crashes) for:

- unknown parameter names in influence lists
- unexpected condition codes
- non-numeric Likert entries

8) Notes for Organised Sound presentation quality

- Avoid dense legends; favour direct labels and consistent ordering.
- Keep condition naming consistent with the manuscript: A visual-only, B audio-only, C audiovisual.
- Multi-panel figures must maintain legibility: large enough fonts, minimal gridlines, and consistent scales.
