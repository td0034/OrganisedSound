// Minimal SPA wizard that saves each section to /api/save_section (JSONB in Postgres).
// Major sections: meta -> background -> blocks (A/B/C order) -> end -> dyad(optional) -> addendum

const $ = (sel) => document.querySelector(sel);

const PARTICIPANT_ID_RE = /^\d{4}[A-Za-z]$/;
const ORDER_MAP = {
  "A→B→C": ["A","B","C"],
  "A→C→B": ["A","C","B"],
  "B→A→C": ["B","A","C"],
  "B→C→A": ["B","C","A"],
  "C→A→B": ["C","A","B"],
  "C→B→A": ["C","B","A"]
};

const AUTHORSHIP_OPTIONS = [
  { value: "me", label: "Me" },
  { value: "system", label: "System" },
  { value: "shared", label: "Shared" },
  { value: "unsure", label: "Unsure" }
];

const CONTEXT_OPTIONS = [
  { value: "home_sketching", label: "Home sketching" },
  { value: "studio_production", label: "Studio production" },
  { value: "live_performance", label: "Live performance" },
  { value: "gallery_installation", label: "Gallery installation" },
  { value: "festival_public_space", label: "Festival / public space" },
  { value: "education_workshop", label: "Education / workshop" },
  { value: "wellbeing_relaxation", label: "Wellbeing / relaxation" },
  { value: "other", label: "Other" }
];

const TARGET_USER_OPTIONS = [
  { value: "complete_beginner", label: "Complete beginner" },
  { value: "hobbyist", label: "Hobbyist" },
  { value: "musician_performer", label: "Musician / performer" },
  { value: "composer_producer", label: "Composer / producer" },
  { value: "audience_participant", label: "Audience participant" },
  { value: "educator_facilitator", label: "Educator / facilitator" },
  { value: "other", label: "Other" }
];

const COLLAB_OPTIONS = [
  { value: "easier_visuals", label: "Visuals (image, pattern, motion)" },
  { value: "easier_notes", label: "Notes / harmony (sonic structure)" },
  { value: "about_same", label: "About the same" },
  { value: "not_sure", label: "Not sure" }
];

const SESSION_TYPE_OPTIONS = [
  { value: "solo", label: "Solo session (standard)" },
  { value: "dyad_only", label: "Dyad-only session" }
];

const state = {
  participant_id: localStorage.getItem("participant_id") || "",
  order: ["A","B","C"],
  blockIndex: 0,
  dyadEnabled: false,
  sessionType: "solo",
  sections: [], // computed
  loadedSections: {},
  session_meta: {},
  blockPresetIds: {}
};

function setMessage(text, kind="info"){
  const el = $("#message");
  const msg = (typeof text === "string") ? text : "";
  el.textContent = msg || "";
  el.style.color = kind === "error" ? "var(--warn)" : "var(--muted)";
}

function extractErrorMessage(data){
  if (!data) return "";
  if (typeof data === "string") return data;
  const detail = data.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length){
    const first = detail[0];
    if (typeof first === "string") return first;
    if (first && typeof first.msg === "string") return first.msg;
  }
  return "";
}

function badgeUpdate(){
  const sec = currentSection();
  $("#pidBadge").textContent = `Participant: ${state.participant_id || "—"}`;
  $("#sectionBadge").textContent = `Section: ${sec ? sec.key : "—"}`;
}

function currentSection(){
  return state.sections[state._idx || 0];
}

function buildSections(){
  // order comes from meta
  const blocks = state.order.map((b) => ([
    { key: `block_${b}_pre`, title: `Block ${b} — Part A (Pre-reveal)`, prompt: blockPromptPre(b), render: () => renderBlockPre(b) },
    { key: `block_${b}_post`, title: `Block ${b} — Part B (Post-reveal)`, prompt: blockPromptPost(b), render: () => renderBlockPost(b) }
  ])).flat();

  const isDyadOnly = state.sessionType === "dyad_only";

  const sections = [
    { key: "meta", title: "Session setup", prompt: "Enter participant/session details and the counterbalanced block order.", render: renderMeta },
    { key: "background", title: "Background (pre-session)", prompt: "Please complete these background questions.", render: renderBackground }
  ];

  if (!isDyadOnly){
    sections.push(
      ...blocks,
      { key: "end", title: "End-of-session comparison", prompt: "After completing all three blocks, answer these final questions.", render: renderEnd },
      { key: "dyad_gate", title: "Dyad participation", prompt: "Did you complete the optional dyad condition?", render: renderDyadGate }
    );
  }

  sections.push(
    { key: "dyad", title: "Dyad questionnaire", prompt: "Complete this only if you took part in the dyad condition.", render: renderDyad },
    { key: "addendum", title: "Final reflections (optional)", prompt: "", render: renderAddendum },
    { key: "thank_you", title: "Thank you", prompt: "", render: renderThankYou }
  );

  state.sections = sections;

  // Hide dyad section unless enabled
  if (!state.dyadEnabled){
    // dyad is still present but renderDyad will show disabled text unless enabled
  }
}

function normalizeParticipantId(value){
  return (value || "").trim().toUpperCase();
}

function timestampId(){
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return [
    d.getFullYear(),
    pad(d.getMonth() + 1),
    pad(d.getDate())
  ].join("") + "_" + [
    pad(d.getHours()),
    pad(d.getMinutes()),
    pad(d.getSeconds())
  ].join("");
}

function ensurePresetId(sec, payload){
  const match = sec.key.match(/^block_([ABC])_(pre|post)$/);
  if (!match) return;
  const block = match[1];
  let presetId = state.blockPresetIds[block];
  if (!presetId){
    const existing = state.loadedSections?.[`block_${block}_pre`]?.preset_id;
    presetId = existing || `${state.participant_id}_${block}_${timestampId()}`;
    state.blockPresetIds[block] = presetId;
  }
  payload.preset_id = presetId;
}

function validateMetaPayload(payload){
  const rawId = (payload.participant_id || "").trim();
  if (!rawId){
    setMessage("Please enter the participant ID.", "error");
    return false;
  }
  const normalized = normalizeParticipantId(rawId);
  if (!PARTICIPANT_ID_RE.test(normalized)){
    setMessage("Participant ID must be 4 digits + 1 letter.", "error");
    return false;
  }
  payload.participant_id = normalized;
  if (!payload.session_type){
    payload.session_type = "solo";
  }
  return true;
}

function render(){
  buildSections();
  const sec = currentSection();
  if (!sec){
    setMessage("Section missing. Please return to start.", "error");
    return;
  }
  $("#sectionTitle").textContent = sec.title;
  $("#sectionPrompt").textContent = sec.prompt;
  $("#sectionForm").innerHTML = "";
  sec.render();
  prefillSection(sec);
  badgeUpdate();
  setMessage("");
  $("#backBtn").disabled = (state._idx || 0) === 0;
  updateFooterButtons(sec);
}

function nextSection(){
  state._idx = (state._idx || 0) + 1;
  // Skip dyad if not enabled
  if (currentSection().key === "dyad" && !state.dyadEnabled){
    state._idx += 1;
  }
  render();
}

function prevSection(){
  state._idx = Math.max(0, (state._idx || 0) - 1);
  render();
}

function goToSectionKey(key){
  const idx = state.sections.findIndex((s) => s.key === key);
  if (idx === -1) return;
  state._idx = idx;
  render();
}

function updateFooterButtons(sec){
  const saveBtn = $("#saveBtn");
  const saveOnlyBtn = $("#saveOnlyBtn");
  const skipBtn = $("#skipBtn");
  const backBtn = $("#backBtn");
  const resetBtn = $("#resetBtn");

  if (sec.key === "addendum"){
    saveBtn.textContent = "Save and finish";
    saveBtn.style.display = "";
    saveOnlyBtn.style.display = "none";
    skipBtn.style.display = "";
    backBtn.style.display = "";
    resetBtn.style.display = "";
    return;
  }

  if (sec.key === "thank_you"){
    saveBtn.style.display = "none";
    saveOnlyBtn.style.display = "none";
    skipBtn.style.display = "none";
    backBtn.style.display = "none";
    resetBtn.style.display = "";
    return;
  }

  saveBtn.textContent = "Save & Continue";
  saveBtn.style.display = "";
  saveOnlyBtn.style.display = "";
  skipBtn.style.display = "none";
  backBtn.style.display = "";
  resetBtn.style.display = "";
}

async function saveCurrentSection(payload){
  const sec = currentSection();
  const finalPayload = payload || collectFormData($("#sectionForm"));
  if (!state.participant_id){
    if (sec.key === "meta" && finalPayload.participant_id){
      state.participant_id = finalPayload.participant_id;
    } else {
      setMessage("Participant ID is required before saving.", "error");
      return false;
    }
  }
  ensurePresetId(sec, finalPayload);

  const res = await fetch("/api/save_section", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      participant_id: state.participant_id,
      section_key: sec.key,
      payload: finalPayload
    })
  });

  if (!res.ok){
    let msg = "Save failed. Please try again.";
    try {
      const data = await res.json();
      const extracted = extractErrorMessage(data);
      if (extracted) msg = extracted;
    } catch (err) {
      // ignore non-JSON errors
    }
    setMessage(msg, "error");
    return false;
  }
  state.loadedSections[sec.key] = finalPayload;
  if (sec.key === "meta"){
    state.session_meta = {
      ...(state.session_meta || {}),
      ...finalPayload
    };
  }
  setMessage("Saved.");
  return true;
}

function normalizeAddendumPayload(payload){
  const normalized = { ...(payload || {}) };
  if (normalized.context_of_use !== undefined){
    if (Array.isArray(normalized.context_of_use)){
      normalized.context_of_use = normalized.context_of_use;
    } else if (normalized.context_of_use){
      normalized.context_of_use = [normalized.context_of_use];
    }
  }
  return normalized;
}

function validateAddendumPayload(payload){
  const missing = [];
  if (!payload.piece_title_favourite) missing.push("title");
  if (!payload.authorship_attribution) missing.push("authorship");
  if (!payload.return_likelihood) missing.push("return likelihood");
  if (!payload.context_of_use || (Array.isArray(payload.context_of_use) && payload.context_of_use.length === 0)){
    missing.push("context of use");
  }
  if (!payload.target_user) missing.push("target user");
  if (!payload.collaboration_expectation) missing.push("collaboration expectation");

  if (missing.length){
    setMessage(`Please complete: ${missing.join(", ")}.`, "error");
    return false;
  }

  const contexts = Array.isArray(payload.context_of_use) ? payload.context_of_use : [payload.context_of_use];
  if (contexts.includes("other") && !payload.context_other){
    setMessage("Please specify the other context.", "error");
    return false;
  }
  if (payload.target_user === "other" && !payload.target_user_other){
    setMessage("Please specify the other target user.", "error");
    return false;
  }
  return true;
}

async function saveAddendum(payload){
  const participantId = normalizeParticipantId(state.participant_id);
  if (!participantId || !PARTICIPANT_ID_RE.test(participantId)){
    setMessage("Participant ID is required before saving.", "error");
    return false;
  }
  const sessionId = (state.session_meta && state.session_meta.session_id) ? state.session_meta.session_id : participantId;
  const normalized = normalizeAddendumPayload(payload);
  if (!validateAddendumPayload(normalized)){
    return false;
  }

  const res = await fetch("/api/addendum/save", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      session_id: sessionId,
      participant_code: participantId,
      skipped: false,
      ...normalized
    })
  });

  if (!res.ok){
    let msg = "Save failed. Please try again.";
    try {
      const data = await res.json();
      const extracted = extractErrorMessage(data);
      if (extracted) msg = extracted;
    } catch (err) {
      // ignore non-JSON errors
    }
    setMessage(msg, "error");
    return false;
  }
  return true;
}

async function skipAddendum(){
  const participantId = normalizeParticipantId(state.participant_id);
  if (!participantId || !PARTICIPANT_ID_RE.test(participantId)){
    setMessage("Participant ID is required before skipping.", "error");
    return false;
  }
  const sessionId = (state.session_meta && state.session_meta.session_id) ? state.session_meta.session_id : participantId;

  const res = await fetch("/api/addendum/skip", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      session_id: sessionId,
      participant_code: participantId
    })
  });

  if (!res.ok){
    let msg = "Skip failed. Please try again.";
    try {
      const data = await res.json();
      const extracted = extractErrorMessage(data);
      if (extracted) msg = extracted;
    } catch (err) {
      // ignore non-JSON errors
    }
    setMessage(msg, "error");
    return false;
  }
  return true;
}

function collectFormData(formEl){
  const fd = new FormData(formEl);
  const out = {};

  // Handle multi-value keys (checkbox groups)
  for (const [k, v] of fd.entries()){
    if (out[k] === undefined){
      out[k] = v;
    } else if (Array.isArray(out[k])){
      out[k].push(v);
    } else {
      out[k] = [out[k], v];
    }
  }

  // Add unchecked checkboxes as false (for known boolean fields)
  // (We keep it light: only the ones used.)
  ["color_deficiency","light_sensitivity"].forEach((k) => {
    if (out[k] === undefined){
      const el = formEl.querySelector(`input[name="${k}"]`);
      if (el) out[k] = "0";
    }
  });

  return out;
}

function fillFormData(formEl, data){
  if (!data) return;
  const fields = formEl.querySelectorAll("input, textarea, select");
  const grouped = {};
  fields.forEach((el) => {
    if (!el.name) return;
    if (!grouped[el.name]) grouped[el.name] = [];
    grouped[el.name].push(el);
  });

  Object.entries(grouped).forEach(([name, elements]) => {
    if (data[name] === undefined) return;
    const raw = data[name];
    const values = Array.isArray(raw) ? raw.map(String) : [String(raw)];

    elements.forEach((el) => {
      if (el.type === "radio"){
        el.checked = values.includes(el.value);
      } else if (el.type === "checkbox"){
        const normalized = values.map((v) => v.toLowerCase());
        if (values.includes(el.value)){
          el.checked = true;
        } else if (normalized.length === 1 && ["1","true","yes"].includes(normalized[0]) && el.value === "1"){
          el.checked = true;
        } else {
          el.checked = false;
        }
      } else {
        el.value = values[0];
      }
    });
  });
}

function prefillSection(sec){
  if (!sec) return;
  let data = state.loadedSections[sec.key];
  if (!data && sec.key === "meta"){
    data = { ...(state.session_meta || {}) };
    if (!data.session_type){
      data.session_type = state.sessionType || "solo";
    }
  }
  fillFormData($("#sectionForm"), data);
  const metaPid = data && data.participant_id;
  if (sec.key === "meta" && !metaPid && state.participant_id){
    const pidInput = $("#sectionForm").querySelector('input[name="participant_id"]');
    if (pidInput) pidInput.value = state.participant_id;
  }
}

function resetSurvey(){
  const ok = window.confirm("Return to start and clear the current participant from this device?");
  if (!ok) return;
  state.participant_id = "";
  state.order = ["A","B","C"];
  state.dyadEnabled = false;
  state.sessionType = "solo";
  state.loadedSections = {};
  state.session_meta = {};
  state.blockPresetIds = {};
  state._idx = 0;
  localStorage.removeItem("participant_id");
  render();
  setMessage("Ready for next participant.");
}

function field(label, innerHTML, helpText=""){
  return `
    <div class="field">
      <label>${label}</label>
      ${helpText ? `<div class="help">${helpText}</div>` : ""}
      ${innerHTML}
    </div>
  `;
}

function selectField(name, options, required=false){
  const req = required ? "required" : "";
  const opts = options.map(o => `<option value="${o}">${o}</option>`).join("");
  return `<select name="${name}" ${req}>${opts}</select>`;
}

function radioList(name, options, required=false){
  const req = required ? "required" : "";
  return `<div class="choice-list">
    ${options.map((o,i)=>`
      <label class="choice">
        <input type="radio" name="${name}" value="${o}" ${req}>
        <span>${o}</span>
      </label>
    `).join("")}
  </div>`;
}

function radioListWithLabels(name, options, required=false){
  const req = required ? "required" : "";
  return `<div class="choice-list">
    ${options.map((o)=>`
      <label class="choice">
        <input type="radio" name="${name}" value="${o.value}" ${req}>
        <span>${o.label}</span>
      </label>
    `).join("")}
  </div>`;
}

function checkbox(name, value, label){
  return `<label class="choice">
    <input type="checkbox" name="${name}" value="${value}">
    <span>${label}</span>
  </label>`;
}

function textarea(name, placeholder=""){
  return `<textarea name="${name}" placeholder="${placeholder}"></textarea>`;
}

function textInput(name, placeholder="", required=false){
  return `<input type="text" name="${name}" placeholder="${placeholder}" ${required?"required":""} />`;
}

function likertScale(name, required=false){
  const req = required ? "required" : "";
  return `<div class="choice-list">
    ${[1,2,3,4,5,6,7].map((n)=>`
      <label class="choice">
        <input type="radio" name="${name}" value="${n}" ${req}>
        <span>${n}</span>
      </label>
    `).join("")}
  </div>`;
}

function likertGrid(baseName, statements){
  // 7-point: 1..7
  const header = `<div class="likert">
    <div></div>
    ${[1,2,3,4,5,6,7].map(n=>`<div class="head">${n}</div>`).join("")}
  </div>`;

  const rows = statements.map((s, idx) => {
    const name = `${baseName}_${idx+1}`;
    return `<div class="likert">
      <div class="stmt">${s}</div>
      ${[1,2,3,4,5,6,7].map(n=>`
        <div class="cell">
          <input type="radio" name="${name}" value="${n}" required>
        </div>
      `).join("")}
    </div>`;
  }).join("");

  return header + rows;
}

// ---------- Section renders ----------

function renderMeta(){
  const f = $("#sectionForm");

  f.innerHTML = `
    <div class="row">
      ${field("Participant ID", textInput("participant_id", "e.g., 9746T", true), "Enter the last 4 digits of your mobile followed by your first name initial.")}
    </div>
    ${field("Condition order (A/B/C)", radioList("order", ["A→B→C","A→C→B","B→A→C","B→C→A","C→A→B","C→B→A"], true),
      "Choose the counterbalanced order you actually used.")}
    ${field("Session type", radioListWithLabels("session_type", SESSION_TYPE_OPTIONS, true),
      "Choose dyad-only if the participant did not do the solo blocks.")}
    ${field("Notes (optional)", textarea("meta_notes", "Any session notes…"))}
  `;
}

function renderBackground(){
  const f = $("#sectionForm");
  f.innerHTML = `
    ${field("Age range", radioList("age_range", ["18–24","25–34","35–44","45–54","55–64","65+","Prefer not to say"], true))}
    ${field("Musical experience", radioList("musical_experience", ["None","Some (informal)","Moderate (regular practice)","High (advanced/degree/pro)","Prefer not to say"], true))}
    ${field("Music theory / harmony familiarity", radioList("theory_familiarity", ["None","Basic","Moderate","High","Prefer not to say"], true))}
    ${field("Generative / algorithmic music or audiovisual systems experience", radioList("generative_experience", ["No","Yes (a little)","Yes (moderate)","Yes (a lot)"], true))}
    ${field("Tonnetz familiarity", radioList("tonnetz_familiarity", ["No","Heard of it","Used it before (some)","Used it before (a lot)"], true))}
    ${field("Perceptual notes (optional)", `
      <div class="choice-list">
        <label class="choice"><input type="checkbox" name="color_deficiency" value="1"> <span>I have colour vision deficiency.</span></label>
        <label class="choice"><input type="checkbox" name="light_sensitivity" value="1"> <span>I have sensitivity to flashing lights.</span></label>
      </div>
      ${textarea("perceptual_comments", "Other comments…")}
    `)}
  `;
}

function blockPromptPre(b){
  if (b === "A") return "Visual-only composition. Complete Part A immediately after capture (before reveal replay).";
  if (b === "B") return "Audio-only composition. Complete Part A immediately after capture (before reveal replay).";
  return "Audiovisual composition. Complete Part A immediately after capture (before reveal replay).";
}
function blockPromptPost(b){
  return "After the reveal replay (sound + light), complete Part B.";
}

function renderBlockMeta(b){
  return `
    <div class="row">
      ${field("Task focus (quick check)", radioList("aim", ["Stability/clarity","Complexity/energy","A mix / unsure"], true))}
    </div>
    ${field("Strategy (brief)", textarea("strategy", "1–3 sentences…"))}
  `;
}

function renderBlockPre(b){
  const f = $("#sectionForm");
  const statementsA = [
    "I am satisfied with the outcome I achieved for this block’s task.",
    "I had a clear intention for what I was trying to achieve.",
    "I felt able to steer the system toward my intention.",
    "The parameter interface felt understandable and workable.",
    "The system surprised me in useful/interesting ways.",
    "The system behaved unpredictably in a frustrating way.",
    "I would be confident that others would find this result interesting (even without me explaining it)."
  ];

  f.innerHTML = `
    ${renderBlockMeta(b)}
    ${field("Part A — ratings (1=Strongly disagree, 7=Strongly agree)", likertGrid("A", statementsA))}
  `;
}

function renderBlockPost(b){
  const f = $("#sectionForm");
  const statementsB = [
    "The revealed audio and light felt like two views of the same underlying process.",
    "Sound and light felt balanced (neither dominated as the ‘real’ carrier of form).",
    "The relationship between sound and light felt coherent/legible.",
    "Sound and light reinforced each other (constructive interference).",
    "Sound and light competed or contradicted each other (destructive interference).",
    "The combined result felt overwhelming (perceptual overload).",
    "The revealed modality (the one I did not have during composition) matched what I expected.",
    "The revealed modality changed my interpretation of what I had made.",
    "I can describe a plausible causal story of how the system produced the result.",
    "I felt that the system had strong autonomy (it ‘wanted’ to do its own thing).",
    "I relied on visual pattern cues to make decisions in this block.",
    "I relied on Tonnetz/music-theory expectations (e.g., triads, neighbourhood relations) to make decisions in this block."
  ];

  const paramChoices = [
    "Max Population","Min Population","Rate","Neighbourhood (Local/Extended)",
    "Min Neighbours","Max Neighbours","Loop On/Off","Loop Length","Life Length","Scale"
  ];

  f.innerHTML = `
    ${field("Expectation vs outcome (free text)", textarea("expectation_vs_outcome", "What did you expect the missing modality to be like, and what was it actually like?"))}
    ${field("Part B — ratings (1=Strongly disagree, 7=Strongly agree)", likertGrid("B", statementsB))}
    ${field("Parameter influence (tick up to 3)", `
      <div class="choice-list">
        ${paramChoices.map(p => `<label class="choice"><input type="checkbox" name="param_influence" value="${p}"><span>${p}</span></label>`).join("")}
      </div>
      <div class="help">If more than 3, that’s fine—aim for the most influential.</div>
      ${textInput("param_other", "Other (optional)") }
    `)}
    ${field("Interference notes (optional)", textarea("interference_notes", "Any moments where visuals felt misleading (or creatively suggestive) relative to the sound, or vice versa?"))}
  `;
}

function renderEnd(){
  const f = $("#sectionForm");
  f.innerHTML = `
    ${field("Rank your three outputs (1=best, 3=least)", `
      <div class="row">
        ${field("Visual-only (A)", textInput("rank_A", "1/2/3", true))}
        ${field("Audio-only (B)", textInput("rank_B", "1/2/3", true))}
        ${field("Audiovisual (C)", textInput("rank_C", "1/2/3", true))}
      </div>
    `)}
    ${field("Which block felt most intermedial (fusion/equality)?", radioList("most_intermedial", ["A","B","C","Unsure"], true))}
    ${field("Which block had the biggest expectation–outcome mismatch at reveal?", radioList("biggest_mismatch", ["A","B","C","None/unsure"], true))}
    ${field("Reflection (4–8 sentences)", textarea("reflection", "What did you learn about the relationship between sound and light in this system?"))}
    ${field("One change to improve media equality", textarea("one_change", "If you could change one thing about the interface or mappings, what would it be?"))}
  `;
}

function renderDyadGate(){
  const f = $("#sectionForm");
  f.innerHTML = `
    ${field("Did you take part in the dyad condition?", radioList("dyad_done", ["No","Yes"], true),
      "If Yes, you will be taken to the dyad questionnaire next.")}
  `;
}

function renderDyad(){
  const f = $("#sectionForm");
  if (!state.dyadEnabled){
    f.innerHTML = `
      <div class="field">
        <label>Dyad questionnaire</label>
        <div class="help">Dyad not selected. If this is wrong, go back one step and choose “Yes”.</div>
      </div>
    `;
    return;
  }

  const statementsD = [
    "We were able to communicate effectively about what we wanted.",
    "We could establish shared reference points (e.g., ‘brighter’, ‘busier’, ‘more stable’, ‘more sparse’).",
    "The split of sensory access (one hears, one sees) helped coordination.",
    "The split of sensory access made coordination harder.",
    "We reached a result that felt jointly owned.",
    "The final result felt balanced between sound and light (media equality).",
    "The final result felt coherent as an audiovisual whole.",
    "I think this dyad output would be preferred over my solo outputs."
  ];

  f.innerHTML = `
    <div class="row">
      ${field("Dyad ID", textInput("dyad_id", "e.g., D01", true))}
      ${field("Your role", radioList("role", ["Audio-role (headphones)","Visual-role (panel)"], true))}
    </div>
    ${field("Dyad block preset ID", textInput("dyad_preset_id", "e.g., P001_D_01", true))}
    ${field("Dyad ratings (1=Strongly disagree, 7=Strongly agree)", likertGrid("D", statementsD))}
    ${field("Communication notes", textarea("communication_notes", "What was most useful for communicating?"))}
    ${field("Disagreements (optional)", textarea("disagreements", "If you disagreed, what was it about and how resolved?"))}
  `;
}

function renderAddendum(){
  const f = $("#sectionForm");
  f.innerHTML = `
    ${field(
      "What title would you give your favourite piece from today?",
      textInput("piece_title_favourite", "e.g., Rising Echoes", true),
      "This can be literal or poetic."
    )}
    ${field(
      "In one sentence, what does it feel like / evoke?",
      textarea("piece_description_one_line", "One sentence...")
    )}
    ${field(
      "Who do you feel authored the outcome most?",
      radioListWithLabels("authorship_attribution", AUTHORSHIP_OPTIONS, true),
      "There's no right answer."
    )}
    ${field("Briefly, why?", textarea("authorship_reason", "Short reason..."))}
    ${field(
      "I would like to use this instrument again in a future session.",
      likertScale("return_likelihood", true)
    )}
    ${field("What would make you more likely to return?", textarea("return_conditions", "Optional..."))}
    ${field(
      "Where could you imagine using something like this?",
      `
        <div class="choice-list">
          ${CONTEXT_OPTIONS.map((o) => checkbox("context_of_use", o.value, o.label)).join("")}
        </div>
      `
    )}
    ${field("Other context (if selected)", textInput("context_other", "If other, specify"))}
    ${field(
      "Who do you think this is most suited to?",
      radioListWithLabels("target_user", TARGET_USER_OPTIONS, true)
    )}
    ${field("Other target user (if selected)", textInput("target_user_other", "If other, specify"))}
    ${field(
      "If you could remove one thing (control, behaviour, or constraint), what would it be?",
      textarea("remove_one_thing", "Optional...")
    )}
    ${field("If you could add one thing, what would it be?", textarea("add_one_thing", "Optional..."))}
    ${field(
      "If two people worked together, what do you think would be easier to negotiate?",
      radioListWithLabels("collaboration_expectation", COLLAB_OPTIONS, true)
    )}
    ${field("Why?", textarea("collaboration_reason", "Optional..."))}
    ${field(
      "I feel confident I could recreate something similar tomorrow.",
      likertScale("confidence_recreate_tomorrow", false)
    )}
  `;
}

function renderThankYou(){
  const f = $("#sectionForm");
  f.innerHTML = `
    <div class="field">
      <label>Thank you</label>
      <div class="help">Your responses have been saved.</div>
    </div>
  `;
}

// ---------- Wiring ----------

$("#saveBtn").addEventListener("click", async () => {
  // Special handling: meta section sets participant_id and order
  const sec = currentSection();
  const payload = collectFormData($("#sectionForm"));

  if (sec.key === "addendum"){
    const ok = await saveAddendum(payload);
    if (ok){
      setMessage("Saved. Thank you.");
      goToSectionKey("thank_you");
    }
    return;
  }

  if (sec.key === "meta"){
    if (!validateMetaPayload(payload)) return;
    const prevId = state.participant_id;
    state.participant_id = payload.participant_id;
    localStorage.setItem("participant_id", payload.participant_id);
    if (prevId && prevId !== state.participant_id){
      state.blockPresetIds = {};
    }
    state.order = ORDER_MAP[payload.order] || ["A","B","C"];
    state.sessionType = payload.session_type || "solo";
    if (state.sessionType === "dyad_only"){
      state.dyadEnabled = true;
    } else {
      state.dyadEnabled = false;
    }
  }

  if (sec.key === "dyad_gate"){
    state.dyadEnabled = (payload.dyad_done === "Yes");
  }

  const ok = await saveCurrentSection(payload);
  if (ok){
    // Prompting the next activity
    if (sec.key.endsWith("_pre")){
      setMessage("Saved. Next: reveal replay, then complete Part B.");
    } else if (sec.key.endsWith("_post")){
      setMessage("Saved. Next: proceed to the next block.");
    } else {
      setMessage("Saved. Continue.");
    }
    nextSection();
  }
});

$("#saveOnlyBtn").addEventListener("click", async () => {
  const sec = currentSection();
  if (sec.key === "addendum" || sec.key === "thank_you") return;
  const payload = collectFormData($("#sectionForm"));

  if (sec.key === "meta"){
    if (!validateMetaPayload(payload)) return;
    const prevId = state.participant_id;
    state.participant_id = payload.participant_id;
    localStorage.setItem("participant_id", payload.participant_id);
    if (prevId && prevId !== state.participant_id){
      state.blockPresetIds = {};
    }
    state.order = ORDER_MAP[payload.order] || ["A","B","C"];
    state.sessionType = payload.session_type || "solo";
    if (state.sessionType === "dyad_only"){
      state.dyadEnabled = true;
    } else {
      state.dyadEnabled = false;
    }
  }

  if (sec.key === "dyad_gate"){
    state.dyadEnabled = (payload.dyad_done === "Yes");
  }

  await saveCurrentSection(payload);
});

$("#backBtn").addEventListener("click", () => prevSection());
$("#resetBtn").addEventListener("click", () => resetSurvey());

$("#skipBtn").addEventListener("click", async () => {
  const sec = currentSection();
  if (sec.key !== "addendum") return;
  const ok = await skipAddendum();
  if (ok){
    setMessage("Skipped. Thank you.");
    goToSectionKey("thank_you");
  }
});

// init
state._idx = 0;
render();
