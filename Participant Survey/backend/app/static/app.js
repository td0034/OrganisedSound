// Minimal SPA wizard that saves each section to /api/save_section (JSONB in Postgres).
// Major sections: meta -> background -> blocks (A/B/C order) -> end -> dyad(optional)

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

const state = {
  participant_id: localStorage.getItem("participant_id") || "",
  order: ["A","B","C"],
  blockIndex: 0,
  dyadEnabled: false,
  sections: [], // computed
  loadedSections: {},
  session_meta: {}
};

function setMessage(text, kind="info"){
  const el = $("#message");
  el.textContent = text || "";
  el.style.color = kind === "error" ? "var(--warn)" : "var(--muted)";
}

function badgeUpdate(){
  $("#pidBadge").textContent = `Participant: ${state.participant_id || "—"}`;
  $("#sectionBadge").textContent = `Section: ${currentSection().key}`;
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

  state.sections = [
    { key: "meta", title: "Session setup", prompt: "Enter participant/session details and the counterbalanced block order.", render: renderMeta },
    { key: "background", title: "Background (pre-session)", prompt: "Please complete these background questions.", render: renderBackground },
    ...blocks,
    { key: "end", title: "End-of-session comparison", prompt: "After completing all three blocks, answer these final questions.", render: renderEnd },
    { key: "dyad_gate", title: "Dyad participation", prompt: "Did you complete the optional dyad condition?", render: renderDyadGate },
    { key: "dyad", title: "Dyad questionnaire", prompt: "Complete this only if you took part in the dyad condition.", render: renderDyad }
  ];

  // Hide dyad section unless enabled
  if (!state.dyadEnabled){
    // dyad is still present but renderDyad will show disabled text unless enabled
  }
}

function normalizeParticipantId(value){
  return (value || "").trim().toUpperCase();
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
  return true;
}

function render(){
  buildSections();
  const sec = currentSection();
  $("#sectionTitle").textContent = sec.title;
  $("#sectionPrompt").textContent = sec.prompt;
  $("#sectionForm").innerHTML = "";
  sec.render();
  prefillSection(sec);
  badgeUpdate();
  setMessage("");
  $("#backBtn").disabled = (state._idx || 0) === 0;
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
      if (data && data.detail) msg = data.detail;
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
    data = state.session_meta || {};
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
  state.loadedSections = {};
  state.session_meta = {};
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
    <div class="row">
      ${field("Date", textInput("date", "auto or enter"), "Optional.")}
      ${field("Session location", textInput("location", "e.g., Studio / Lab"), "Optional.")}
      ${field("Researcher", textInput("researcher", "name/initials"), "Optional.")}
    </div>
    ${field("Condition order (A/B/C)", radioList("order", ["A→B→C","A→C→B","B→A→C","B→C→A","C→A→B","C→B→A"], true),
      "Choose the counterbalanced order you actually used.")}
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
      ${field("Block preset ID / block ID", textInput("preset_id", "e.g., P001_A_01", true),
        "Use the same identifier you use for saved presets / files.")}
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

// ---------- Wiring ----------

$("#saveBtn").addEventListener("click", async () => {
  // Special handling: meta section sets participant_id and order
  const sec = currentSection();
  const payload = collectFormData($("#sectionForm"));

  if (sec.key === "meta"){
    if (!validateMetaPayload(payload)) return;
    state.participant_id = payload.participant_id;
    localStorage.setItem("participant_id", payload.participant_id);
    state.order = ORDER_MAP[payload.order] || ["A","B","C"];
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
  const payload = collectFormData($("#sectionForm"));

  if (sec.key === "meta"){
    if (!validateMetaPayload(payload)) return;
    state.participant_id = payload.participant_id;
    localStorage.setItem("participant_id", payload.participant_id);
    state.order = ORDER_MAP[payload.order] || ["A","B","C"];
  }

  if (sec.key === "dyad_gate"){
    state.dyadEnabled = (payload.dyad_done === "Yes");
  }

  await saveCurrentSection(payload);
});

$("#backBtn").addEventListener("click", () => prevSection());
$("#resetBtn").addEventListener("click", () => resetSurvey());

// init
state._idx = 0;
render();
