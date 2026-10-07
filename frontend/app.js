'use strict';
const $=id=>document.getElementById(id);
const state={patient:null,results:[],result:null,trends:[],view:'overview',summary:'patient',compare:null,token:''};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const label=m=>m.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
const date=s=>new Date(s).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});
const number=v=>v===null||v===undefined?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:2});
async function api(path,options={}){
 if(window.INBODY_PREVIEW)return window.INBODY_PREVIEW.request(path,options);
 const headers={Authorization:state.token?'Bearer '+state.token:''};
 if(options.body && !(options.body instanceof FormData)){headers['Content-Type']='application/json';options.body=JSON.stringify(options.body);}
 const response=await fetch(path,{...options,headers:{...headers,...options.headers}});
 const data=await response.json();if(!response.ok)throw Error(data.error||'Request failed');return data;
}
function notify(message){$('notice').textContent=message;}
async function loadPatients(){
 try{const patients=await api('/patients');$('patient').innerHTML=patients.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
 if(!patients.length){$('content').innerHTML='<div class="empty"><h2>No synthetic patients yet</h2><p>Start the server with --seed or add a synthetic patient.</p></div>';return;}
 state.patient=$('patient').value;await loadPatient();
 }catch(e){notify(e.message);if(e.message.includes('Authentication'))$('token-dialog').showModal();}
}
async function loadPatient(){
 state.patient=$('patient').value;state.compare=null;
 const encounters=await api(`/patients/${state.patient}/encounters`);
 $('encounter').innerHTML=encounters.map(e=>`<option value="${esc(e.id)}">${esc(e.label)}</option>`).join('');
 await refresh();
}
async function refresh(rid){
 const [all,trends]=await Promise.all([api(`/patients/${state.patient}/inbody`),api(`/patients/${state.patient}/inbody/trends`)]);
 const superseded=new Set(all.map(r=>r.supersedes).filter(Boolean));state.results=all;state.trends=trends;
 const latest=all.find(r=>!superseded.has(r.id));
 state.result=rid?await api(`/patients/${state.patient}/inbody/${rid}`):latest?await api(`/patients/${state.patient}/inbody/${latest.id}`):null;render();
}
function activeAnalysis(){return state.result?.analyses?.[0];}
function overview(){
 const r=state.result,a=activeAnalysis();if(!r)return '<div class="empty"><h2>A new baseline starts here.</h2><p>Import a completed result to create the first study.</p><button class="primary" data-action="import">Import result</button></div>';
 const c=a?.longitudinal_comparison;
 const chosen=state.results.find(p=>p.id===state.compare);
 const changes=chosen?r.measurements.filter(m=>m.status==='verified'&&m.value!==null).map(m=>{const p=chosen.measurements.find(p=>p.metric===m.metric&&p.unit===m.unit&&p.status==='verified'&&p.value!==null);return p?{metric:m.metric,absolute_change:m.value-p.value,change_unit:m.unit==='%'?'percentage points':m.unit}:null;}).filter(Boolean):c?.changes||[];
 const cards=['weight','skeletal_muscle_mass','percent_body_fat','body_fat_mass'].map(metric=>{
 const m=r.measurements.find(m=>m.metric===metric),change=changes.find(c=>c.metric===metric);
 return `<article class="stat"><small>${label(metric)}</small><div class="statvalue">${number(m?.value)}<span>${esc(m?.unit||'')}</span></div><div class="delta">${m?.status==='unverified'?'Needs source confirmation':change?`${change.absolute_change>0?'+':''}${number(change.absolute_change)} ${esc(change.change_unit)} vs prior`:'No comparison'}</div></article>`;}).join('');
 const flags=a?.rule_findings||[];
 const priorOptions=state.results.filter(p=>p.id!==r.id&&!state.results.some(x=>x.supersedes===p.id));
 return `<div class="sectionhead"><h2>Study overview</h2><div class="study-meta"><small>${date(r.test_timestamp)} · ${esc(new Date(r.test_timestamp).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}))}</small><span class="pill">${esc(a?.review_status||'pending')} review</span></div></div>
 <div class="stats">${cards}</div><div class="two-col"><section class="card"><div class="card-title"><div><h3>The pattern over time</h3><div class="card-sub">Verified measurements · ${state.trends[0]?.points.length||0} studies</div></div><select id="chart-metric" class="chartselect" aria-label="Trend metric">${state.trends.map(t=>`<option value="${esc(t.metric)}">${label(t.metric)}</option>`).join('')}</select></div><div id="trend-chart"></div><p class="hint">Numerical direction only. Clinical improvement is not inferred.</p></section><section class="card"><h3>Findings to review</h3><p class="card-sub">Deterministic rules · ${esc(a?.provenance.rules_version||'')}</p>${flags.length?flags.map(f=>`<div class="finding"><strong>${label(f.metric)} <span class="pill">${esc(f.severity)}</span></strong><p>${esc(f.reason)}</p><small>${esc(f.source)}</small></div>`).join(''):'<div class="finding"><p>No configured rule fired. This does not establish that every result is normal.</p></div>'}</section></div>
 <section class="card spaced"><div class="card-title"><div><h3>Measured facts</h3><p class="card-sub">Missing fields remain missing. Estimates reflect this test.</p></div><select id="comparison" class="chartselect" aria-label="Comparison study"><option value="">Analysis comparison${c?.from?' · '+date(c.from):''}</option>${priorOptions.map(p=>`<option value="${esc(p.id)}" ${state.compare===p.id?'selected':''}>${date(p.test_timestamp)} · ${esc(p.source_identifier)}</option>`).join('')}</select></div><p class="hint">${chosen?`Display comparison: ${esc(chosen.test_timestamp)} → ${esc(r.test_timestamp)}. Stored analysis is unchanged.`:c?.from?`Comparison interval: ${esc(c.from)} → ${esc(c.to)} (${number(c.interval_days)} days).`:esc(c?.note||'')}</p><table><thead><tr><th>Measurement</th><th>Result</th><th>Change</th><th>Validation</th></tr></thead><tbody>${r.measurements.map(m=>{const d=changes.find(c=>c.metric===m.metric);return `<tr><td>${label(m.metric)}</td><td>${number(m.value)} <span class="hint">${esc(m.unit)}</span></td><td>${d?`${d.absolute_change>0?'+':''}${number(d.absolute_change)} ${esc(d.change_unit)}`:'—'}</td><td><span class="pill">${esc(m.status)}</span></td></tr>`;}).join('')}</tbody></table></section>
 <section class="card spaced"><div class="tabs"><button data-summary="patient" class="${state.summary==='patient'?'selected':''}">Patient summary</button><button data-summary="clinician" class="${state.summary==='clinician'?'selected':''}">Clinician interpretation</button><button data-summary="provenance" class="${state.summary==='provenance'?'selected':''}">Source & provenance</button></div><div class="summary">${summary()}</div><div class="reviewbar"><p>${a?.data_quality_passed?'Ready for clinician review. Confirm patient, encounter and actual test timestamp.':'Source confirmation required before acceptance.'}</p><button class="quiet" data-action="correct">Confirm / correct</button><button class="primary" data-action="review">Review study</button></div></section>`;
}
function summary(){
 const r=state.result,a=activeAnalysis();if(!a)return '<p>No analysis available.</p>';
 if(state.summary==='patient')return '<h3>Your body composition, explained</h3>'+a.patient_summary.sentences.map(s=>`<p>${esc(s)}</p>`).join('')+`<p class="hint">Clinician review: ${esc(a.review_status)} · AI: ${esc(a.provenance.ai.status)}</p>`;
 if(state.summary==='clinician')return `<h3>Clinician interpretation</h3><p><strong>Measured facts:</strong> ${a.clinician_summary.measured_facts.map(m=>`${esc(label(m.metric))} ${number(m.value)} ${esc(m.unit)}`).join('; ')||'No verified measurements.'}</p><p><strong>Rule-derived interpretation:</strong> ${a.rule_findings.map(f=>esc(f.reason)).join(' ')||'No configured rule fired.'}</p><p><strong>Clinical considerations:</strong> ${a.clinician_summary.clinical_considerations.map(esc).join(' ')}</p><p><strong>Data limitations:</strong> ${a.clinician_summary.data_quality_limitations.map(esc).join('; ')||'No extraction validation issues. Device and testing-condition limitations still apply.'}</p><p><strong>AI-generated synthesis:</strong> ${a.clinician_summary.ai_generated_synthesis?.map(esc).join(' ')||'No AI synthesis used. Deterministic explanation available.'}</p><p class="hint">AI uses a constrained evidence-selection interface. It cannot introduce measurements, diagnoses or treatment advice.</p>`;
 const pairs={'Result ID':r.id,'Patient / encounter':r.patient_id+' / '+r.encounter_id,'Test performed':r.test_timestamp,'Imported':r.ingested_at,'Source':r.source_type+' / '+r.source_identifier,'Device':r.device_model,'Parser':r.provenance.parser_version,'Analysis':a.provenance.analysis_version,'Rules':a.provenance.rules_version,'Content SHA-256':r.provenance.source_hash,'Original payload':r.source_result.payload_sha256,'Original files':r.source_result.files.map(f=>f.sha256).join(', ')||'No uploaded file','Superseded version':r.supersedes||'None','AI provider / model':(a.provenance.ai.provider||'None')+' / '+(a.provenance.ai.model||'Not used'),'Review':a.review_status};
 return `<h3>A traceable record</h3><dl class="provenance">${Object.entries(pairs).map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>${r.source_result.files.map((f,i)=>`<button class="quiet" data-source="${esc(f.sha256)}">Download source ${i+1}</button>`).join(' ')}<button class="quiet" data-action="export">Export structured result</button>`;
}
function history(){return `<div class="sectionhead"><h2>Study history</h2><small>${state.results.length} immutable versions</small></div><section class="card"><table><thead><tr><th>Test date</th><th>Source</th><th>Device</th><th>Version</th><th></th></tr></thead><tbody>${state.results.map(r=>`<tr class="history-row"><td>${date(r.test_timestamp)}<br><span class="hint">${esc(r.test_timestamp)}</span></td><td>${esc(r.source_type)}</td><td>${esc(r.device_model)}</td><td>${state.results.some(x=>x.supersedes===r.id)?'Superseded':r.supersedes?'Correction':'Original'}</td><td><button class="smallbutton" data-open="${esc(r.id)}">Open study →</button></td></tr>`).join('')}</tbody></table>${state.results.length?'':'<p>No studies yet.</p>'}</section>`;}
function drawChart(metric){
 const target=$('trend-chart');if(!target)return;
 const series=state.trends.find(t=>t.metric===metric)||state.trends[0];
 if(!series){target.innerHTML='<p>No verified measurements available to chart.</p>';return;}
 const pts=series.points,W=620,H=185,pad=32;const vals=pts.map(p=>p.value);
 const min=Math.min(...vals),max=Math.max(...vals),span=max-min||1;
 const times=pts.map(p=>new Date(p.test_timestamp).valueOf()),start=Math.min(...times),elapsed=Math.max(...times)-start||1;
 const xy=pts.map((p,i)=>[pad+(times[i]-start)/elapsed*(W-2*pad),H-pad-(p.value-min)/span*(H-2*pad)]);
 target.innerHTML=`<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label(series.metric))} trend"><title>${esc(label(series.metric))}, ${esc(series.unit)}. ${pts.map(p=>date(p.test_timestamp)+': '+number(p.value)).join('; ')}</title>${[0,1,2].map(i=>`<line x1="${pad}" y1="${pad+i*(H-2*pad)/2}" x2="${W-pad}" y2="${pad+i*(H-2*pad)/2}"/><text x="0" y="${pad+i*(H-2*pad)/2+3}">${number(max-i*(max-min)/2)}</text>`).join('')}<path d="${xy.map((p,i)=>(i?'L':'M')+p.join(',')).join(' ')}"/>${xy.map((p,i)=>`<circle cx="${p[0]}" cy="${p[1]}" r="4"><title>${esc(pts[i].test_timestamp)}: ${number(pts[i].value)} ${esc(series.unit)}</title></circle>${pts.length<=5?`<text x="${p[0]}" y="${H-6}" text-anchor="middle">${esc(date(pts[i].test_timestamp))}</text>`:''}`).join('')}</svg>`;
}
function render(){document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('active',b.dataset.view===state.view));$('content').innerHTML=state.view==='history'?history():overview();drawChart();}
function openImport(){if(window.INBODY_PREVIEW){window.INBODY_PREVIEW.prepareImport(state.patient,$('encounter').value);}if(!state.patient){notify('Select or create a synthetic patient first.');return;}$('import-error').textContent='';$('import-dialog').showModal();}
$('import-button').onclick=openImport;$('close-import').onclick=()=>$('import-dialog').close();
$('auth').onclick=()=>$('token-dialog').showModal();$('close-token').onclick=()=>$('token-dialog').close();
$('token-form').onsubmit=async e=>{e.preventDefault();state.token=$('token').value;$('token').value='';$('token-dialog').close();await loadPatients();};
$('patient').onchange=()=>loadPatient().catch(e=>notify(e.message));
$('source-type').onchange=()=>{const file=['pdf','image'].includes($('source-type').value);$('file-label').hidden=!file;$('json-label').hidden=file;};
$('import-form').onsubmit=async e=>{
 e.preventDefault();$('submit-import').disabled=true;$('submit-import').textContent='Extracting & analyzing…';
 try{const fields=Object.fromEntries(new FormData(e.target));fields.patient_id=state.patient;fields.encounter_id=$('encounter').value;
 let body=fields;if(['pdf','image'].includes(fields.source_type)){const files=$('files').files;if(!files.length)throw Error('Choose source files.');body=new FormData();body.append('metadata',JSON.stringify(fields));for(const f of files)body.append('files',f);}else fields.measurements=JSON.parse($('measurements').value);
 const result=await api(`/patients/${state.patient}/inbody/import`,{method:'POST',body});$('import-dialog').close();state.view='overview';await refresh(result.id);notify(window.INBODY_PREVIEW?'Synthetic sample loaded for this preview. Reload the page to reset.':result.duplicate?'This source was already imported. Existing record opened.':'Result imported, analyzed and preserved in the patient history.');
 }catch(e){$('import-error').textContent=e.message;}finally{$('submit-import').disabled=false;$('submit-import').textContent='Import & analyze';}
};
document.addEventListener('click',async e=>{
 const nav=e.target.closest('[data-view]');if(nav){if(nav.dataset.view==='import'){openImport();return;}state.view=nav.dataset.view;render();}
 const sum=e.target.closest('[data-summary]');if(sum){state.summary=sum.dataset.summary;render();}
 const open=e.target.closest('[data-open]');if(open){state.view='overview';try{await refresh(open.dataset.open);}catch(e){notify(e.message);}}
 const source=e.target.closest('[data-source]');if(source){try{const response=await fetch(`/patients/${state.patient}/inbody/${state.result.id}/sources/${source.dataset.source}`,{headers:{Authorization:state.token?'Bearer '+state.token:''}});if(!response.ok)throw Error('Source download denied');const blob=await response.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=source.dataset.source+(blob.type.includes('pdf')?'.pdf':blob.type.includes('png')?'.png':'.jpg');link.click();URL.revokeObjectURL(url);}catch(e){notify(e.message);}}
 const action=e.target.closest('[data-action]')?.dataset.action;
 if(action==='import')openImport();
 if(action==='correct'){if(window.INBODY_PREVIEW){notify('Source confirmation and corrections are available in the local application. This preview uses fixed synthetic measurements.');return;}const measurements=state.result.measurements.map(m=>({...m,status:'verified',confidence:1,quality_note:''}));$('correction-json').value=JSON.stringify(measurements,null,2);$('correction-confirm').checked=false;$('correction-error').textContent='';$('correction-dialog').showModal();}
 if(action==='review'){
  const a=activeAnalysis();if(!a?.data_quality_passed){notify('Confirm or correct unverified values first.');return;}
  if(!confirm(`Confirm patient ${state.patient}, encounter ${state.result.encounter_id}, test ${state.result.test_timestamp} and original source. Accept this analysis?`))return;
  try{await api(`/patients/${state.patient}/inbody/${state.result.id}/review`,{method:'POST',body:{analysis_id:a.id,status:'accepted',identity_confirmed:true,note:'Source, patient, encounter and test timestamp reviewed.'}});await refresh(state.result.id);notify(window.INBODY_PREVIEW?'Demo review state updated. No clinical record was changed.':'Clinician review recorded.');}catch(e){notify(e.message);}
 }
 if(action==='export'){const blob=new Blob([JSON.stringify(state.result,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=state.result.id+'.json';link.click();URL.revokeObjectURL(url);}
});
document.addEventListener('change',e=>{if(e.target.id==='chart-metric')drawChart(e.target.value);if(e.target.id==='comparison'){state.compare=e.target.value;render();}});
$('close-correction').onclick=()=>$('correction-dialog').close();
$('correction-form').onsubmit=async e=>{e.preventDefault();try{const result=await api(`/patients/${state.patient}/inbody/${state.result.id}/correct`,{method:'POST',body:{measurements:JSON.parse($('correction-json').value),reason:$('correction-reason').value}});$('correction-dialog').close();await refresh(result.id);notify('New version saved. The original source and values remain preserved.');}catch(e){$('correction-error').textContent=e.message;}};
$('new-patient').onclick=async()=>{const id=prompt('Synthetic patient ID (letters, numbers, dash or underscore)');if(!id)return;const name=prompt('Synthetic patient name');if(!name)return;try{await api('/patients',{method:'POST',body:{id,name,synthetic:true,sex:'unknown'}});await api(`/patients/${id}/encounters`,{method:'POST',body:{id:id+'-ASSESSMENT',label:'Assessment'}});await loadPatients();$('patient').value=id;await loadPatient();}catch(e){notify(e.message);}};
loadPatients();
