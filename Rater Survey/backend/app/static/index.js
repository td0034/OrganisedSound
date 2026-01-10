const $ = (s) => document.querySelector(s);

function msg(t, kind="info"){
  $("#message").textContent = t || "";
  $("#message").style.color = (kind === "error") ? "var(--warn)" : "var(--muted)";
}

async function api(path, opts){
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

$("#createBtn").addEventListener("click", async () => {
  try{
    const label = ($("#raterLabel").value || "").trim();
    if (!label){
      msg("Please enter a rater label before creating a session.", "error");
      return;
    }
    const r = await api("/api/session/create", {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ rater_label: label })
    });

    const full = location.origin + r.share_url;
    $("#sessionLink").value = full;
    $("#openLink").href = r.share_url;
    $("#result").style.display = "";
    msg(`Session created (${r.total} clips).`);
  }catch(e){
    msg("Failed to create session. Ensure clips exist in the mounted clips folder and wait for scan.", "error");
  }
});

$("#copyBtn").addEventListener("click", async () => {
  try{
    await navigator.clipboard.writeText($("#sessionLink").value);
    msg("Copied.");
  }catch{
    msg("Copy failed. Select and copy manually.", "error");
  }
});
