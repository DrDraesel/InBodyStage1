import json
from datetime import datetime
from pathlib import Path
from backend.validation import age_at

RULES = json.loads((Path(__file__).resolve().parents[1]/'rules/clinical-v1.json').read_text())
VERSION = 'deterministic-analysis-v1.0'

def apply_rules(measurements, patient, stamp, config=None):
    config = config or RULES
    flags = []
    age = age_at(patient.get('dob'), stamp)
    for m in measurements:
        if m['status'] != 'verified' or m['value'] is None:
            flags.append({'metric':m['metric'],'flag_type':'data_quality','severity':'clinician review',
                'measured_value':m['value'],'reference_value_or_rule':'Human source confirmation required',
                'source':'validation-v1.0','reason':m['quality_note'] or 'Measurement unverified.', 'review_required':True})
            continue
        ref = m.get('device_reference')
        if ref and not ref['low'] <= m['value'] <= ref['high']:
            flags.append({'metric':m['metric'],'flag_type':'outside device reference',
                'severity':'outside device reference','measured_value':m['value'],
                'reference_value_or_rule':ref,'source':ref['source'],'source_version':ref['version'],
                'evidence_category':'source-reported-device-interval',
                'reason':'Outside the reference interval supplied with this test; clinician must verify applicability.',
                'review_required':True})
        fired = []
        for rule in config['rules']:
            if rule['metric'] != m['metric'] or rule['unit'] != m['unit']:
                continue
            if rule.get('min_age') is not None and (age is None or age < rule['min_age']):
                continue
            if rule.get('max_age') is not None and (age is None or age > rule['max_age']):
                continue
            if rule.get('sex') and patient.get('sex') != rule['sex']:
                continue
            passed = {'lt':m['value'] < rule['threshold'], 'gte':m['value'] >= rule['threshold']}[rule['operator']]
            if passed:
                fired.append(rule)
                flags.append({'metric':m['metric'],'flag_type':'clinically relevant',
                    'severity':rule['severity'],'measured_value':m['value'],
                    'reference_value_or_rule':rule, 'source':rule['source'], 'source_version':rule['source_version'],
                    'reason':rule['explanation'], 'review_required':rule['review_required']})
        if ref and fired and ref['low'] <= m['value'] <= ref['high']:
            flags.append({'metric':m['metric'],'flag_type':'conflicting references',
                'severity':'clinician review','measured_value':m['value'],
                'reference_value_or_rule':{'device':ref,'clinical':[r['id'] for r in fired]},
                'source':'reference-conflict-v1.0','reason':'Device interval and population screening rule differ; retain both and review applicability.', 'review_required':True})
        if len(fired)>1:
            flags.append({'metric':m['metric'],'flag_type':'conflicting findings', 'severity':'clinician review',
                'measured_value':m['value'],'reference_value_or_rule':[r['id'] for r in fired],
                'source':'rule-conflict-v1.0','reason':'Multiple configured clinical rules fired; review overlapping criteria.','review_required':True})
    return flags

def compare(current, previous):
    if not previous:
        return {'previous_result_id':None,'interval_days':None,'changes':[], 'note':'No earlier verified comparison available.'}
    days = (datetime.fromisoformat(current['test_timestamp']) - datetime.fromisoformat(previous['test_timestamp'])).total_seconds()/86400
    prior = {m['metric']:m for m in previous['measurements']}
    changes = []
    for m in current['measurements']:
        p = prior.get(m['metric'])
        if not p or p['unit'] != m['unit'] or m['status'] != 'verified' or p['status'] != 'verified' or m['value'] is None or p['value'] is None:
            continue
        delta = m['value'] - p['value']
        # Percent-body-fat changes are percentage points, not relative percentages.
        relative = None if p['value'] == 0 or m['unit'] in ('%','deg','score','level','ratio') else delta/abs(p['value'])*100
        changes.append({'metric':m['metric'],'previous_value':p['value'],'current_value':m['value'],
            'absolute_change':round(delta,6),'percentage_change':None if relative is None else round(relative,4),
            'change_unit':'percentage points' if m['unit']=='%' else m['unit'],
            'direction':'increased' if delta>0 else 'decreased' if delta<0 else 'unchanged',
            'clinical_significance':'not classified — no approved change rule',
            'from':previous['test_timestamp'],'to':current['test_timestamp']})
    return {'previous_result_id':previous['id'],'from':previous['test_timestamp'],
        'to':current['test_timestamp'],'interval_days':round(days,4),'changes':changes,
        'note':'Numerical changes do not by themselves establish improvement or worsening.'}

MEANINGS = {'weight':'Your total body weight.', 'bmi':'A screening number based on your weight and height. It does not tell the whole story about body fat or health.',
 'skeletal_muscle_mass':'An estimate of the muscle that helps you move.',
 'percent_body_fat':'The estimated share of your weight that is fat.',
 'body_fat_mass':'An estimate of how much of your body weight is fat.',
 'total_body_water':'An estimate of the water in your body.',
 'ecw_tbw':'The share of estimated body water outside your cells.',
 'visceral_fat_area':'An estimate of fat around organs in your abdomen.',
 'phase_angle':'An electrical measurement from the test. Its meaning depends on the device and your health context.'}

def summaries(result, flags, comparison):
    verified = [m for m in result['measurements'] if m['status']=='verified' and m['value'] is not None]
    limitations = [m['metric']+': '+(m['quality_note'] or 'unverified') for m in result['measurements'] if m['status']!='verified']
    clinician = {'test_timestamp':result['test_timestamp'],'source_device':result['device_model'],
        'measured_facts':verified,'rule_derived_interpretation':flags,'longitudinal_comparison':comparison,
        'clinical_considerations':['Consider testing conditions, hydration, device consistency, and the clinical history when interpreting bioimpedance estimates.'],
        'data_quality_limitations':limitations,'references':RULES, 'review_status':'pending', 'ai_generated_synthesis':None}
    sentences = ['This test estimates your body composition.']
    for m in verified:
        name = {'bmi':'body mass index','ecw_tbw':'body water ratio'}.get(m['metric'],m['metric'].replace('_',' '))
        units = {'kg':'kilograms','L':'liters','%':'percent','kg/m2':'','ratio':'','deg':'degrees','cm2':'square centimeters','kcal/day':'calories per day'}.get(m['unit'],m['unit'])
        sentences.append(f"Your {name} was {m['value']:g} {units}. {MEANINGS.get(m['metric'], 'Your healthcare professional can explain this measurement.')}")
    for change in comparison['changes']:
        start = datetime.fromisoformat(change['from']).strftime('%B %d, %Y')
        end = datetime.fromisoformat(change['to']).strftime('%B %d, %Y')
        name = {'bmi':'body mass index','ecw_tbw':'body water ratio'}.get(change['metric'],change['metric'].replace('_',' '))
        unit = {'kg':'kilograms','L':'liters','kg/m2':'points','ratio':'','deg':'degrees','cm2':'square centimeters'}.get(change['change_unit'],change['change_unit'])
        sentences.append(f"Between {start} and {end}, your {name} {change['direction']} by {abs(change['absolute_change']):g} {unit}.")
    if not comparison['previous_result_id']:
        sentences.append('There is no earlier test available for comparison.')
    if flags:
        sentences.append('Some measurements need review. Discuss these results with your healthcare professional.')
    if limitations:
        sentences.append('Some values could not be confirmed. They are not used to interpret your results.')
    sentences.append('Changes in numbers alone do not tell us whether your health has improved or worsened.')
    return clinician, {'sentences':sentences, 'review_status':'pending', 'ai_generated_synthesis':None}
