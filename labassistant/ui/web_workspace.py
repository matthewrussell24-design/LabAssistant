"""Self-contained presentation document for the native AppKit workspace."""

WORKSPACE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {
  --canvas:#f4f6f8; --surface:#fff; --muted:#667085; --text:#172033;
  --border:#e6eaf0; --accent:#3867e8; --accent-soft:#eef3ff;
  --success:#16805c; --success-soft:#eaf7f1; --warning:#a85b00; --warning-soft:#fff4df;
}
* { box-sizing:border-box; }
body { margin:0; background:var(--canvas); color:var(--text); font:14px -apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",sans-serif; }
button { font:inherit; }
.app { min-height:100vh; padding:26px 30px 30px; }
.header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:20px; }
.eyebrow { color:var(--accent); font-size:11px; letter-spacing:1.2px; font-weight:750; }
h1 { font-size:28px; line-height:1.08; margin:5px 0 3px; letter-spacing:-.6px; }
.subtitle,.muted { color:var(--muted); }
.brand-badge,.badge { border-radius:999px; padding:5px 10px; font-size:11px; font-weight:700; }
.brand-badge { color:var(--accent); background:var(--accent-soft); }
.badge.warning { color:var(--warning); background:var(--warning-soft); }
.badge.success { color:var(--success); background:var(--success-soft); }
.layout { display:grid; grid-template-columns:270px minmax(580px,1fr) 270px; gap:18px; min-height:720px; }
.center { display:grid; grid-template-rows:minmax(330px,1.04fr) minmax(350px,.96fr); gap:18px; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:16px; padding:20px; box-shadow:0 8px 28px rgba(26,39,64,.08); overflow:hidden; }
.card h2 { font-size:16px; margin:0 0 6px; }
.workspace,.history { display:flex; flex-direction:column; }
.actions { display:grid; gap:8px; margin-top:14px; }
.action { border:1px solid var(--border); background:#f8fafc; color:#263249; border-radius:11px; padding:11px 13px; text-align:left; cursor:pointer; transition:.16s ease; }
.action:hover { transform:translateY(-1px); color:var(--accent); border-color:#c9d6fa; background:#f3f6ff; }
.action.primary { color:white; border-color:var(--accent); background:var(--accent); }
.action.primary:hover { background:#2f5cd4; }
.action[disabled] { color:#a3abb8; background:#fafbfc; border-color:#eef0f3; cursor:not-allowed; transform:none; }
.action strong,.action span { display:block; }
.action span { margin-top:3px; font-size:12px; font-weight:450; opacity:.88; }
.workspace-foot,.history-foot { margin-top:auto; padding-top:18px; color:var(--muted); font-size:12px; line-height:1.35; }
.experiment { position:relative; }
.empty { height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:24px; }
.empty-icon { width:58px; height:58px; display:grid; place-items:center; border-radius:50%; color:var(--accent); background:var(--accent-soft); font-size:25px; }
.empty h2 { margin:14px 0 6px; font-size:18px; }
.empty p { max-width:520px; line-height:1.45; }
.experiment-head { display:flex; justify-content:space-between; gap:14px; }
.experiment-head h2 { margin-bottom:7px; }
.metrics { display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin:17px 0; }
.metric,.section,.measurement,.history-item { background:#f8fafc; border:1px solid #edf0f4; border-radius:12px; }
.metric { padding:12px 14px; }
.metric-value { font-size:22px; font-weight:750; letter-spacing:-.3px; }
.metric-label { margin-top:4px; color:var(--muted); font-size:10px; font-weight:700; letter-spacing:.5px; }
.section-label { color:var(--muted); font-size:10px; font-weight:750; letter-spacing:.6px; margin-bottom:8px; }
.measurement { display:flex; align-items:center; justify-content:space-between; padding:12px 14px; }
.measurement strong { display:block; margin-bottom:5px; }
.analysis-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px; }
.section { padding:14px 15px; min-height:112px; }
.section h3 { margin:0 0 9px; font-size:13px; }
.section ul { margin:0; padding-left:18px; color:var(--muted); line-height:1.38; }
.section li+li { margin-top:6px; }
.history-list { display:grid; gap:8px; margin-top:14px; }
.history-item { padding:11px 12px; cursor:pointer; transition:.16s ease; }
.history-item:hover { color:var(--accent); border-color:#c9d6fa; background:#f3f6ff; transform:translateY(-1px); }
.history-item strong,.history-item span { display:block; }
.history-item span { color:var(--muted); font-size:12px; margin-top:4px; }
.fade { animation:fade .26s cubic-bezier(.2,.8,.2,1); }
@keyframes fade { from { opacity:.18; transform:translateY(4px); } to { opacity:1; transform:none; } }
@media(max-width:1120px) { .layout { grid-template-columns:235px minmax(520px,1fr) 235px; } .metrics { grid-template-columns:repeat(3,1fr); } }
</style>
</head>
<body>
<main class="app">
  <header class="header"><div><div class="eyebrow">LABORATORY INTELLIGENCE</div><h1>LabAssistant</h1><div class="subtitle">The future of discovery, grounded in your evidence.</div></div><div class="brand-badge">LOCAL WORKSPACE</div></header>
  <div class="layout">
    <section class="card workspace"><h2>Workspace</h2><div class="muted">Start with an experiment, then bring in evidence.</div><div class="actions">
      <button class="action" onclick="newExperiment()"><strong>New Experiment</strong><span>Clear the active workspace</span></button>
      <button class="action primary" onclick="importDLS()"><strong>Import DLS Dataset</strong><span>Analyze supported local files</span></button>
      <button class="action" disabled><strong>Import Chromatography</strong><span>Future workflow</span></button>
      <button class="action" disabled><strong>Import CSV</strong><span>Generic import planned</span></button>
      <button class="action" id="open-existing" onclick="openExisting()" disabled><strong>Open Existing Experiment</strong><span>Reopen your most recent saved experiment</span></button>
    </div><div class="workspace-foot">Scientific logic remains in the shared LabAssistant core.</div></section>
    <div class="center"><section class="card experiment" id="experiment"></section><section class="card analysis"><h2>Analysis</h2><div class="muted">Evidence-aware guidance from the current experiment.</div><div class="analysis-grid" id="analysis"></div></section></div>
    <section class="card history"><h2>History</h2><div class="muted">Session work and saved experiments.</div><div class="history-list" id="history"></div><div class="history-foot">Saved experiments restore through the application boundary.</div></section>
  </div>
</main>
<script>
const state={history:[],persisted:[],current:null};
const esc=v=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const metric=(label,value)=>`<div class="metric"><div class="metric-value">${esc(value??'—')}</div><div class="metric-label">${esc(label).toUpperCase()}</div></div>`;
const section=(title,items)=>`<div class="section"><h3>${esc(title)}</h3><ul>${(items?.length?items:['No analysis available yet.']).map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`;
function empty(){document.getElementById('experiment').innerHTML=`<div class="empty fade"><div class="empty-icon">✦</div><h2>Your current experiment will live here</h2><p class="muted">Import a supported DLS dataset to assemble measurements, surface observations, and begin an evidence-grounded review.</p><button class="action primary" onclick="importDLS()"><strong>Import DLS Dataset</strong><span>Select summary, intensity, and correlogram files</span></button></div>`;document.getElementById('analysis').innerHTML=['Summary','Evidence','Possible Causes','Suggested Next Steps'].map(x=>section(x,[])).join('');}
function render(data){state.current=data;const e=data.experiment,m=data.measurements||[],first=m[0]||{};document.getElementById('experiment').innerHTML=`<div class="fade"><div class="experiment-head"><div><h2>${esc(e.label)}</h2><div class="muted">${esc(e.technique||'Unknown')} &nbsp;·&nbsp; ${data.source_files.length} source file${data.source_files.length===1?'':'s'}</div></div><div class="badge ${esc(data.status.tone)}">${esc(data.status.label)}</div></div><div class="metrics">${metric('Measurements',e.measurement_count)}${metric('Observations',e.observation_count)}${metric('Primary peak',first.primary_peak)}${metric('PDI',first.pdi)}${metric('Quality',first.quality_score)}</div><div class="section-label">MEASUREMENT OVERVIEW</div>${m.map(x=>`<div class="measurement"><div><strong>${esc(x.sample_name)}</strong><span class="muted">Z-average ${esc(x.z_average)} &nbsp;·&nbsp; D50 ${esc(x.d50)}</span></div><div class="badge ${x.warnings.length?'warning':'success'}">${esc(x.status)}</div></div>`).join('')}</div>`;const a=data.analysis;document.getElementById('analysis').innerHTML=section('Summary',a.summary)+section('Evidence',a.evidence)+section('Possible Causes',a.possible_causes)+section('Suggested Next Steps',a.next_steps);}
function history(){const el=document.getElementById('history');const parts=[];if(state.history.length){parts.push('<div class="section-label">THIS SESSION</div>');parts.push(state.history.map((x,i)=>`<div class="history-item" onclick="restore(${i})"><strong>${esc(x.experiment.label)}</strong><span>Just now &nbsp;·&nbsp; ${x.experiment.measurement_count} measurement${x.experiment.measurement_count===1?'':'s'}</span></div>`).join(''));}if(state.persisted.length){parts.push(`<div class="section-label"${state.history.length?' style="margin-top:14px"':''}>SAVED EXPERIMENTS</div>`);parts.push(state.persisted.map(x=>`<div class="history-item" onclick="openPersisted('${esc(x.record_id)}')"><strong>${esc(x.label)}</strong><span>${esc(x.saved_display)} &nbsp;·&nbsp; ${x.measurement_count} measurement${x.measurement_count===1?'':'s'}</span></div>`).join(''));}el.innerHTML=parts.length?parts.join(''):'<div class="muted" style="margin-top:14px">No experiments yet.<br>Imported analyses will appear here.</div>';}
function newExperiment(){state.current=null;empty();}
function restore(i){render(state.history[i]);}
function importDLS(){window.webkit.messageHandlers.labassistant.postMessage({action:'import_dls'});}
function openPersisted(id){window.webkit.messageHandlers.labassistant.postMessage({action:'open_experiment',record_id:id});}
function openExisting(){if(state.persisted.length)openPersisted(state.persisted[0].record_id);}
window.labassistantAddResult=data=>{state.history.unshift(data);render(data);history();};
window.labassistantSetPersistedHistory=list=>{state.persisted=Array.isArray(list)?list:[];const b=document.getElementById('open-existing');if(b)b.disabled=!state.persisted.length;history();};
window.labassistantShowError=message=>alert(message);
empty();history();
</script>
</body></html>"""
