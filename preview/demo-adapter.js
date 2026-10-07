'use strict';
// Only precomputed synthetic results. No patient data, source files, tokens or API access.
(function(){
 const copy=v=>JSON.parse(JSON.stringify(v));
 const data=copy(window.INBODY_PREVIEW_DATA);
 const histories=data.histories;
 const error=()=>{throw Error('This visual preview accepts the fixed synthetic sample only. Use the local application for actual imports and corrections.');};
 function detail(pid,rid){const r=histories[pid]?.find(r=>r.id===rid);if(!r)throw Error('Synthetic study not found for this patient.');return r;}
 function trends(pid){
  const series={};
  for(const r of [...histories[pid]].reverse())for(const m of r.measurements){
   if(m.status!=='verified'||m.value===null)continue;
   const key=m.metric+'|'+m.unit;series[key]??={metric:m.metric,unit:m.unit,points:[]};
   series[key].points.push({result_id:r.id,test_timestamp:r.test_timestamp,value:m.value});
  }
  return Object.values(series);
 }
 window.INBODY_PREVIEW={
  prepareImport(pid){
   const r=data.samples[pid];if(!r)return;
   const f=document.getElementById('import-form');
   document.getElementById('encounter').value=r.encounter_id;
   for(const name of ['test_timestamp','source_identifier','device_model']){f.elements[name].value=r[name];f.elements[name].readOnly=true;}
   document.getElementById('source-type').innerHTML='<option value="mock_api">Precomputed synthetic sample</option>';
   document.getElementById('measurements').value=JSON.stringify(r.measurements.map(m=>({metric:m.metric,value:m.value,unit:m.unit})),null,2);
   document.getElementById('measurements').readOnly=true;
   document.getElementById('file-label').hidden=true;document.getElementById('json-label').hidden=false;
   document.getElementById('submit-import').textContent='Load synthetic sample';
  },
  async request(path,options={}){
   const method=options.method||'GET',body=options.body||{};
   if(method==='GET'&&path==='/patients')return copy(data.patients);
   let match=path.match(/^\/patients\/([^/]+)\/encounters$/);
   if(match&&method==='GET')return copy(data.encounters[match[1]]||[]);
   match=path.match(/^\/patients\/([^/]+)\/inbody(?:\/([^/]+))?(?:\/([^/]+))?$/);
   if(!match)return error();
   const [,pid,rid,action]=match;if(!histories[pid])throw Error('Synthetic patient not found.');
   if(method==='GET'&&!rid)return copy(histories[pid]);
   if(method==='GET'&&rid==='trends')return copy(trends(pid));
   if(method==='GET'&&!action)return copy(detail(pid,rid));
   if(method==='POST'&&rid==='import'){
    const sample=data.samples[pid];
    if(body.source_identifier!==sample.source_identifier||body.test_timestamp!==sample.test_timestamp||body.patient_id!==pid||body.encounter_id!==sample.encounter_id||JSON.stringify(body.measurements)!==JSON.stringify(sample.measurements.map(m=>({metric:m.metric,value:m.value,unit:m.unit}))))return error();
    if(histories[pid].some(r=>r.id===sample.id))return {...copy(sample),duplicate:true};
    histories[pid].unshift(copy(sample));return copy(sample);
   }
   if(method==='POST'&&action==='review'){
    const r=detail(pid,rid),a=r.analyses[0];
    if(body.analysis_id!==a.id||body.identity_confirmed!==true||body.status!=='accepted')throw Error('Confirm the current synthetic study.');
    a.review_status='accepted';a.patient_summary.review_status='accepted';a.clinician_summary.review_status='accepted';
    a.reviews??=[];a.reviews.unshift({status:'accepted',actor:'visual-preview-only',note:'Demo action; no clinical record modified.'});return copy(r);
   }
   return error();
  }
 };
 document.addEventListener('DOMContentLoaded',()=>{
  document.getElementById('auth').hidden=true;
  document.getElementById('new-patient').hidden=true;
  document.getElementById('import-button').textContent='＋ Try a synthetic sample';
  const bar=document.createElement('div');bar.className='preview-banner';bar.textContent='Interactive visual preview · Synthetic studies only · Changes reset when you reload';
  document.querySelector('main').prepend(bar);
  document.querySelector('#import-form > p').textContent='Explore one precomputed synthetic study. No files or patient information are uploaded.';
  document.querySelector('#import-form .hint').textContent='The local application supports PDF, screenshot and manual ingestion. This hosted visual preview loads only a fixed synthetic result.';
  document.querySelector('.sidefoot').innerHTML='<span class="statusdot"></span>Visual preview<small>InBodyStage1 / v0.1.1<br>Synthetic demonstration</small>';
  document.querySelector('.barend').innerHTML='<span class="statusdot"></span><span>Synthetic preview</span>';
 });
})();
