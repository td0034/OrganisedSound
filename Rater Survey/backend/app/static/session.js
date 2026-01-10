const $ = (s) => document.querySelector(s);

const token = window.__TOKEN__;
let clipId = window.__CLIP_ID__; // may be null
let state = null;

let watchedComplete = false;
let maxProgress = 0;
let seekGuard = false;
const consentKey = `consent:${token}`;

const BEST_CONTEXT_OPTIONS = [
  { value: "installation_gallery", label: "Installation / gallery" },
  { value: "live_performance", label: "Live performance" },
  { value: "background_ambience", label: "Background ambience" },
  { value: "workshop_education", label: "Workshop / education" },
  { value: "unsure", label: "Unsure" }
];

function msg(t, kind="info"){
  $("#message").textContent = t || "";
  $("#message").style.color = (kind === "error") ? "var(--warn)" : "var(--muted)";
}

function msgSave(t, kind="info"){
  const el = $("#saveMessage");
  if (!el) return;
  el.textContent = t || "";
  el.style.color = (kind === "error") ? "var(--warn)" : "var(--muted)";
}

function msgEnd(t, kind="info"){
  const el = $("#endMessage");
  if (!el) return;
  el.textContent = t || "";
  el.style.color = (kind === "error") ? "var(--warn)" : "var(--muted)";
}

function hasLocalConsent(){
  try{
    return window.localStorage.getItem(consentKey) === "true";
  }catch(_e){
    return false;
  }
}

function setLocalConsent(){
  try{
    window.localStorage.setItem(consentKey, "true");
  }catch(_e){
    // Ignore storage errors; consent is still stored server-side when available.
  }
}

async function api(path, opts){
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function likertGrid(baseName, statements){
  const header = `<div class="likert"><div></div>${[1,2,3,4,5,6,7].map(n=>`<div class="head">${n}</div>`).join("")}</div>`;
  const rows = statements.map((s, idx) => {
    const name = `${baseName}_${idx+1}`;
    return `<div class="likert">
      <div class="stmt">${s}</div>
      ${[1,2,3,4,5,6,7].map(n=>`<div class="cell"><input type="radio" name="${name}" value="${n}" required></div>`).join("")}
    </div>`;
  }).join("");
  return header + rows;
}

function likertScale(name, required=false){
  const req = required ? "required" : "";
  return `<div class="choice-list">
    ${[1,2,3,4,5,6,7].map(n=>`
      <label class="choice">
        <input type="radio" name="${name}" value="${n}" ${req}>
        <span>${n}</span>
      </label>
    `).join("")}
  </div>`;
}

function buildRatingForm(){
  const statements = [
    "I like this clip.",
    "This clip feels coherent/legible as an audiovisual work.",
    "This clip feels novel/interesting.",
    "Sound and light feel fused (two equals shaping a single experience).",
    "Sound and light reinforce each other (constructive interference).",
    "Sound and light compete or contradict (destructive interference).",
    "The clip feels overwhelming (perceptual overload).",
    "I can infer an underlying structure or process driving both modalities.",
    "The piece feels human-steered rather than purely system-driven."
  ];

  $("#ratingForm").innerHTML = `
    <div class="field">
      <label>Ratings (1=low/strongly disagree, 7=high/strongly agree)</label>
      ${likertGrid("R", statements)}
    </div>

    <div class="field">
      <label>Where does this clip feel most at home?</label>
      <div class="choice-list">
        ${BEST_CONTEXT_OPTIONS.map((o)=>`
          <label class="choice">
            <input type="radio" name="best_context" value="${o.value}">
            <span>${o.label}</span>
          </label>
        `).join("")}
      </div>
    </div>

    <div class="field">
      <label>Which modality dominated your attention?</label>
      <div class="choice-list">
        ${["Mostly sound","Mostly light","Balanced","It varied / unsure"]
          .map(o=>`<label class="choice"><input type="radio" name="attention" value="${o}" required><span>${o}</span></label>`).join("")}
      </div>
    </div>

    <div class="field">
      <label>Which composition condition do you think this clip came from?</label>
      <div class="choice-list">
        ${[
          { value: "audio_only", label: "Audio-only (composer could not see the visuals)" },
          { value: "visual_only", label: "Visual-only (composer could not hear the audio)" },
          { value: "audiovisual", label: "Audiovisual (both available)" },
          { value: "unsure", label: "Unsure" }
        ].map(o=>`<label class="choice"><input type="radio" name="condition_guess" value="${o.value}" required><span>${o.label}</span></label>`).join("")}
      </div>
      <div class="help">Best guess is fine.</div>
    </div>

    <div class="field">
      <label>Comments (optional)</label>
      <textarea name="comments" placeholder="Any brief comments…"></textarea>
    </div>
  `;
}

function buildEndForm(){
  $("#endForm").innerHTML = `
    <div class="field">
      <label>What did you like most about your highest rated clip(s)? (optional)</label>
      <textarea name="highest_rated_notes" placeholder="Short notes…"></textarea>
    </div>
    <div class="field">
      <label>What did you like least about your lowest rated clip(s)? (optional)</label>
      <textarea name="lowest_rated_notes" placeholder="Short notes…"></textarea>
    </div>
    <div class="field">
      <label>Any further comments / remarks? (optional)</label>
      <textarea name="further_comments" placeholder="Short notes…"></textarea>
    </div>
  `;
}

function collectForm(formEl){
  const fd = new FormData(formEl);
  const out = {};
  for (const [k,v] of fd.entries()){
    out[k] = v;
  }
  return out;
}

function resetWatch(){
  watchedComplete = false;
  maxProgress = 0;
  seekGuard = false;
  $("#ratingForm").style.display = "none";
  $("#saveNextBtn").disabled = true;
  $("#saveOnlyBtn").disabled = true;
}

function unlockRatings(){
  $("#ratingForm").style.display = "";
  $("#saveNextBtn").disabled = false;
  $("#saveOnlyBtn").disabled = false;
  msg("Ratings unlocked. You may replay the clip if you wish, then submit your rating.");
}

function currentIndex(){
  if (!state || !state.clip_ids) return -1;
  return state.clip_ids.indexOf(clipId);
}

function navigateTo(idx){
  const id = state.clip_ids[idx];
  window.location.href = `/s/${token}/clip/${id}`;
}

async function loadState(){
  state = await api(`/api/session/${token}/state`);
  const done = (state.done_ids || []).length;
  const progressBadge = $("#progressBadge");
  if (progressBadge){
    progressBadge.textContent = `Progress: ${done}/${state.total}`;
  }
  const clipCount = $("#clipCount");
  if (clipCount){
    clipCount.textContent = String(state.total || "—");
  }

  // pick first unrated clip if clipId not provided
  if (clipId === null || clipId === undefined){
    const remaining = state.clip_ids.filter(id => !(state.done_ids || []).includes(id));
    clipId = remaining.length ? remaining[0] : state.clip_ids[state.clip_ids.length - 1];
  }
}

async function loadClip(){
  buildRatingForm();
  resetWatch();

  const info = await api(`/api/session/${token}/clip/${clipId}`);
  const clipTitle = $("#clipTitle");
  if (clipTitle){
    const idx = currentIndex();
    const displayNum = idx >= 0 ? idx + 1 : info.clip.clip_id;
    const total = state && state.total ? state.total : null;
    clipTitle.textContent = total ? `Clip ${displayNum} of ${total}` : `Clip ${displayNum}`;
  }

  const video = $("#video");
  video.src = `/media/${clipId}`;
  video.currentTime = 0;

  video.ontimeupdate = () => {
    maxProgress = Math.max(maxProgress, video.currentTime);
  };

  video.onseeking = () => {
    if (seekGuard || watchedComplete) return;
    if (video.currentTime > maxProgress + 0.25){
      seekGuard = true;
      video.currentTime = maxProgress;
      msg("Skipping ahead is disabled. Please watch the clip in order.", "error");
      setTimeout(() => { seekGuard = false; }, 0);
    }
  };

  video.onended = () => {
    watchedComplete = true;
    seekGuard = false;
    if (isFinite(video.duration)) {
      maxProgress = Math.max(maxProgress, video.duration);
    }
    unlockRatings();
  };

  msg("Please watch to the end to unlock the rating form.");
  msgSave("");
}

async function saveRating(advance){
  msgSave("");
  const video = $("#video");
  const duration = isFinite(video.duration) ? video.duration : 0;

  if (!watchedComplete){
    msg("Please watch the clip to the end before submitting a rating.", "error");
    return;
  }

  // best-effort anti-skip: require maxProgress very close to duration
  if (duration > 0 && maxProgress < (duration - 0.5)){
    msg("Please watch the full clip (to the end) before submitting.", "error");
    return;
  }

  const payload = collectForm($("#ratingForm"));
  const perceivedAgency = payload.R_9 ? parseInt(payload.R_9, 10) : null;
  const bestContext = payload.best_context || null;

  if (!perceivedAgency){
    msgSave("Please complete all ratings before saving.", "error");
    return;
  }

  delete payload.best_context;

  await api("/api/rating/save", {
    method:"POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({
      token,
      clip_id: clipId,
      watched_complete: true,
      watch_progress_sec: maxProgress,
      duration_sec: duration,
      perceived_agency: perceivedAgency,
      best_context: bestContext,
      payload
    })
  });

  msg("Saved.");
  msgSave("");
  if (advance){
    await loadState();
    const idx = currentIndex();
    const nextIdx = idx + 1;

    // find next in playlist, else show end card
    if (nextIdx < state.clip_ids.length){
      navigateTo(nextIdx);
    } else {
      $("#endCard").style.display = "";
      buildEndForm();
      msgEnd("");
      msg("All clips rated. Optional: complete end notes below.");
    }
  }
}

$("#saveNextBtn").addEventListener("click", async () => {
  try { await saveRating(true); } catch(e){ msg("Save failed: " + e.message, "error"); }
});

$("#saveOnlyBtn").addEventListener("click", async () => {
  try { await saveRating(false); } catch(e){ msg("Save failed: " + e.message, "error"); }
});

$("#prevBtn").addEventListener("click", async () => {
  try{
    await loadState();
    const idx = currentIndex();
    if (idx > 0) navigateTo(idx - 1);
    else msg("This is the first clip.");
  }catch(e){
    msg("Failed to navigate: " + e.message, "error");
  }
});

$("#endSaveBtn").addEventListener("click", async () => {
  try{
    msgEnd("");
    const payload = collectForm($("#endForm"));
    await api("/api/session/end", {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ token, payload })
    });
    msgEnd("End notes saved. Thank you.");
  }catch(e){
    msgEnd("Failed to save end notes: " + e.message, "error");
  }
});

// Boot
(async function init(){
  try{
    await loadState();
    if (state && (state.consent || hasLocalConsent())){
      state.consent = true;
      $("#consentCard").style.display = "none";
      $("#ratingCard").style.display = "";
      await loadClip();
    } else {
      $("#consentCard").style.display = "";
      $("#ratingCard").style.display = "none";
      $("#endCard").style.display = "none";
      msg("Please review the information and provide consent to begin.");
    }
  }catch(e){
    msg("Failed to load session/clip: " + e.message, "error");
  }
})();

$("#consentCheck").addEventListener("change", () => {
  $("#consentBtn").disabled = !$("#consentCheck").checked;
});

$("#consentBtn").addEventListener("click", async () => {
  try{
    await api("/api/session/consent", {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ token, agreed: true })
    });
    setLocalConsent();
    await loadState();
    $("#consentCard").style.display = "none";
    $("#ratingCard").style.display = "";
    await loadClip();
  }catch(e){
    msg("Failed to save consent: " + e.message, "error");
  }
});
