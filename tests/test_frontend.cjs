// Isolated view-model smoke check, not a browser layout or accessibility certification.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=__dirname+'/..';
const m={metric:'weight',value:80,unit:'kg',status:'verified'};
const result={id:'result-1',patient_id:'SYN-1',encounter_id:'SYN-1-E',test_timestamp:'2026-10-07T10:00:00-04:00',ingested_at:'2026-10-07T14:01:00+00:00',source_identifier:'test-1',source_type:'mock_api',device_model:'Synthetic fixture',measurements:[m],source_result:{payload_sha256:'a'.repeat(64),files:[]},provenance:{parser_version:'test',source_hash:'b'.repeat(64)},analyses:[{id:'analysis-1',review_status:'pending',data_quality_passed:true,provenance:{rules_version:'test-v1',analysis_version:'test',ai:{status:'disabled'}},rule_findings:[],longitudinal_comparison:{previous_result_id:null,changes:[],note:'No prior study.'},patient_summary:{sentences:['Your weight was 80 kilograms.']},clinician_summary:{measured_facts:[m],clinical_considerations:['Review testing context.'],data_quality_limitations:[]}}]};
const nodes=new Map();const element=id=>{if(!nodes.has(id))nodes.set(id,{value:id==='patient'?'SYN-1':'',innerHTML:'',textContent:'',classList:{toggle(){}},showModal(){},close(){}});return nodes.get(id);};
const endpoints={'/patients':[{id:'SYN-1',name:'Synthetic Patient',dob:'1980-05-16'}],'/patients/SYN-1/encounters':[{id:'SYN-1-E',label:'Assessment'}],'/patients/SYN-1/inbody':[result],'/patients/SYN-1/inbody/trends':[{metric:'weight',unit:'kg',points:[{result_id:'result-1',test_timestamp:result.test_timestamp,value:80}]}],'/patients/SYN-1/inbody/result-1':result};
const sandbox={window:{},console,Map,Set,Date,Number,String,JSON,Error,Object,Promise,FormData:class{},fetch:async path=>{assert.ok(path in endpoints,'Unknown request '+path);return {ok:true,json:async()=>endpoints[path]};},document:{getElementById:element,querySelectorAll:()=>[],addEventListener(){}},confirm:()=>false,prompt:()=>null};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(root+'/frontend/app.js','utf8'),sandbox);
setImmediate(()=>{
 try{
  assert.match(element('patient-identity').textContent,/Synthetic Patient.*1980-05-16/);
  assert.match(element('content').innerHTML,/Measured facts/);assert.match(element('content').innerHTML,/80/);
  assert.match(element('trend-chart').innerHTML,/<svg/);
  assert.match(vm.runInContext("state.summary='clinician';summary()",sandbox),/Measured facts/);
  assert.match(vm.runInContext("state.summary='provenance';summary()",sandbox),/traceable record/);
  assert.match(vm.runInContext('history()',sandbox),/Study history/);
  const demo=JSON.parse(fs.readFileSync(root+'/preview/demo-data.json','utf8'));
  const plan=demo.samples['SYN-001'].analyses[0].recommendation_plan;
  assert.ok(plan,'Synthetic preview includes a recommendation draft');
  sandbox.plan=plan;
  const recommendations=vm.runInContext('recommendationView(plan)',sandbox);
  assert.match(recommendations,/Peptides \/ prescription options/);
  assert.match(recommendations,/Upper-limb training/);
  assert.match(recommendations,/Lower-limb training/);
  assert.match(recommendations,/Needed before individualizing/);
  plan.context.goals='<script>alert(1)</script>';
  assert.ok(!vm.runInContext('recommendationView(plan)',sandbox).includes('<script>'));
  assert.match(vm.runInContext("state.result=null;overview()",sandbox),/new baseline/);
  console.log('Frontend view-model smoke checks passed: overview, trend, summaries, provenance, history, empty state.');
 }catch(e){console.error(e);process.exitCode=1;}
});
