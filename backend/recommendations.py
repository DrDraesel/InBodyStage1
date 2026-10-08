"""Evidence-linked clinical discussion drafts, never treatment orders."""
from backend.validation import Invalid, age_at

VERSION = 'clinical-discussion-v1.0'
REFERENCES = {
    'activity': {'title': 'CDC adult physical activity overview', 'url': 'https://www.cdc.gov/physical-activity-basics/guidelines/adults.html'},
    'balance': {'title': 'CDC older adult physical activity overview', 'url': 'https://www.cdc.gov/physical-activity-basics/guidelines/older-adults.html'},
    'nutrition': {'title': 'NIDDK choosing a safe weight-management program', 'url': 'https://www.niddk.nih.gov/health-information/weight-management/choosing-a-safe-successful-weight-loss-program'},
    'peptides': {'title': 'FDA bulk substances with potential significant safety risks', 'url': 'https://www.fda.gov/drugs/human-drug-compounding/certain-bulk-drug-substances-use-compounding-may-present-significant-safety-risks'},
    'medications': {'title': 'NIDDK prescription medications for overweight and obesity', 'url': 'https://www.niddk.nih.gov/health-information/weight-management/prescription-medications-treat-overweight-obesity'},
    'device': {'title': 'InBody 380 manual', 'url': 'https://inbodyusa.zendesk.com/hc/en-us/articles/26353282696084-InBody-380-User-s-Manual'},
}


def validate_context(context):
    context = {} if context is None else context
    if not isinstance(context, dict):
        raise Invalid('Recommendation context must be an object')
    allowed = {'goals', 'activity_level', 'pain_present', 'falls_or_balance_concern',
               'pregnancy_or_breastfeeding', 'cardiovascular_symptoms',
               'clinical_history_reviewed', 'medications_reviewed'}
    if set(context) - allowed:
        raise Invalid('Unknown recommendation context field')
    result = {'goals': '', 'activity_level': 'unknown', 'clinical_history_reviewed': False,
              'medications_reviewed': False}
    result.update({key: 'unknown' for key in ('pain_present', 'falls_or_balance_concern',
                                            'pregnancy_or_breastfeeding', 'cardiovascular_symptoms')})
    result.update(context)
    if not isinstance(result['goals'], str) or len(result['goals']) > 500:
        raise Invalid('Goals must be text of at most 500 characters')
    if result['activity_level'] not in ('unknown', 'sedentary', 'some', 'regular'):
        raise Invalid('Invalid activity level')
    for key in ('pain_present', 'falls_or_balance_concern', 'pregnancy_or_breastfeeding', 'cardiovascular_symptoms'):
        if result[key] not in ('unknown', 'yes', 'no'):
            raise Invalid('Context flags must be unknown, yes or no')
    for key in ('clinical_history_reviewed', 'medications_reviewed'):
        if not isinstance(result[key], bool):
            raise Invalid('Review flags must be boolean')
    return result


def build_plan(result, patient, comparison, context=None):
    context = validate_context(context)
    facts = {m['metric']: m for m in result['measurements'] if m['status'] == 'verified' and m['value'] is not None}
    incomplete = any(m['status'] != 'verified' or m['value'] is None for m in result['measurements'])
    age = age_at(patient.get('dob'), result['test_timestamp'])
    domains = []

    def add(key, title, reviewer, rationale, actions, needs, refs, evidence=None, status=None):
        domains.append({'id': key, 'title': title, 'reviewer': reviewer,
                        'status': status or ('source_confirmation_required' if incomplete else 'clinician_discussion'),
                        'rationale': rationale, 'options_to_discuss': actions, 'required_assessment': needs,
                        'evidence_metrics': evidence or [], 'reference_ids': refs,
                        'evidence_level': 'General guidance plus source observations; individualized efficacy not established',
                        'clinician_review_required': True, 'is_treatment_order': False})

    bmi = facts.get('bmi')
    metabolic = 'Review body-composition estimates with the clinical history, waist measurement and cardiometabolic risk; they do not diagnose metabolic disease.'
    if bmi and bmi['unit'] == 'kg/m2' and age is not None and age >= 20:
        metabolic += f" Verified BMI is {bmi['value']:g} kg/m2; interpret muscularity and other risk factors before setting a weight goal."
    add('medical', 'Medical / metabolic review', 'Medical or family-medicine clinician', metabolic,
        ['Review blood pressure, waist circumference, weight trajectory, symptoms and medication effects.',
         'Consider glucose/A1c, lipids and other testing only when history and examination justify them.',
         'Review unintentional weight change or swelling before interpreting a body-composition trend.'],
        ['Medical history, symptoms and examination', 'Existing labs and diagnoses', 'Medication and contraindication review'],
        ['nutrition', 'device'], [k for k in ('weight', 'bmi', 'percent_body_fat', 'ecw_tbw') if k in facts])
    add('nutrition', 'Functional nutrition / recovery', 'Qualified medical clinician and dietitian',
        'Choose nutrition around the patient’s goals and health context. BIA does not identify nutrient deficiencies, endocrine disorders or a supplement requirement.',
        ['Discuss a sustainable food pattern with vegetables, fruit, fiber-rich foods and suitable protein sources.',
         'Individualize energy and protein needs with activity, age, kidney/liver function and nutritional status.',
         'Use symptoms and relevant findings to guide targeted investigations; do not order a blanket functional-lab or supplement panel.'],
        ['Dietary history and goals', 'Kidney/liver status and relevant labs', 'Food access, restrictions and medication interactions'], ['nutrition'],
        [k for k in ('weight', 'skeletal_muscle_mass', 'body_fat_mass') if k in facts])

    segment_pairs = []
    for region in ('arm', 'leg'):
        names = ['right_' + region + '_lean_mass', 'left_' + region + '_lean_mass']
        right, left = [facts.get(name) for name in names]
        observation = None
        if right and left and right['unit'] == left['unit'] and right['unit'] in ('kg', 'lb', 'lbs') and min(right['value'], left['value']) > 0:
            percent = round(abs(right['value'] - left['value']) / max(right['value'], left['value']) * 100, 2)
            observation = {'region': region, 'right': right['value'], 'left': left['value'], 'unit': right['unit'],
                           'difference_percent_of_larger': percent, 'clinical_threshold': None,
                           'interpretation': 'Estimated lean-mass difference; no strength, balance or injury conclusion.'}
            segment_pairs.append(observation)
        reason = (f"Right {region} estimate {right['value']:g} {right['unit']}, left {left['value']:g} {left['unit']}; difference {observation['difference_percent_of_larger']:g}% of the larger estimate. " if observation else 'No comparable, verified left/right segmental lean-mass pair. ')
        reason += 'Confirm the source, then test strength, movement quality and symptoms. More lean mass does not prove greater strength.'
        options = (['After assessment, consider controlled rows, presses and carries within tolerated range.',
                    'Use comparable left/right loads and technique initially; prescribe extra side-specific work only after functional assessment.'] if region == 'arm' else
                   ['After assessment, consider supported sit-to-stand, step-ups, calf raises and progressive leg strengthening.',
                    'Use grip/support and supervision when needed; select unilateral loading only after pain, gait and strength assessment.'])
        add(region + '_training', ('Upper' if region == 'arm' else 'Lower') + '-limb training / symmetry',
            'Chiropractic Physical Medicine / rehabilitation reviewer', reason, options,
            ['Pain and injury history', 'Bilateral strength and range-of-motion testing', 'Movement/task assessment and training tolerance'],
            ['activity', 'device'], names if observation else [], status='assessment_required')

    add('balance', 'Balance / gait / coordination', 'Chiropractic Physical Medicine / neurovestibular reviewer',
        'Body composition does not measure balance or vestibular function. Reported falls or instability require functional assessment before progression.',
        ['Assess gait, sit-to-stand and supported stance as appropriate; route neurological or vestibular symptoms for domain review.',
         'After clearance, consider supervised weight shifts, supported tandem stance and step-control practice.',
         'Progress support, surface and visual challenge only after demonstrated control.'],
        ['Fall history, dizziness and neurological symptoms', 'Balance/gait testing', 'Support requirements and supervision'], ['balance'], status='assessment_required')
    aerobic = 'Discuss a gradual, tolerable activity progression after assessment; an individualized target is not available.'
    if age is not None and age >= 18:
        aerobic = 'For medically suitable adults, discuss building toward 150 minutes of moderate aerobic activity weekly and strength work on at least 2 days; start below this if necessary.'
    add('activity', 'Exercise / conditioning', 'Medical and physical-medicine reviewers',
        'Use goals, baseline capacity and symptoms to choose a starting dose; InBody alone does not establish exercise clearance.',
        [aerobic, 'Consider walking, cycling or another tolerated aerobic option with progressive resistance training.',
         'If cardiovascular symptoms, pain or instability are present, assess first and defer unsupervised progression.'],
        ['Clinical clearance and current activity', 'Cardiovascular symptoms, pain and functional tolerance', 'Age and patient goals'], ['activity', 'balance'])
    add('lifestyle', 'Lifestyle / sleep / adherence', 'Medical / functional-health reviewer',
        'Build a manageable plan around daily routines and preferences; avoid promising longevity or body-composition changes from an isolated metric.',
        ['Review sleep schedule and possible sleep-disordered breathing when symptoms warrant.',
         'Discuss breaking up prolonged sitting, stress management, tobacco exposure and alcohol use.',
         'Choose one or two achievable habits and agree on what will be reassessed.'],
        ['Sleep, work schedule, substance use and stress history', 'Patient priorities and practical barriers'], ['nutrition'])
    add('peptides', 'Peptides / prescription options', 'Licensed prescribing medical clinician',
        'An InBody result is not a peptide indication. No peptide, dose or protocol is selected automatically.',
        ['If clinically indicated, discuss approved prescription weight-management options such as semaglutide or tirzepatide with a prescriber; eligibility and suitability are not established here.',
         'BPC-157, CJC-1295 and ipamorelin: retain as evidence-review topics, not routine recovery, muscle-building or longevity recommendations. FDA identifies safety concerns and limited safety information for these substances.',
         'Verify current indication, evidence, product/regulatory status, interactions, contraindications and monitoring before considering any prescription. Compounded products are not interchangeable with FDA-approved products.'],
        ['Diagnosis and indication confirmed by prescriber', 'Medication, pregnancy and contraindication review',
         'Current product label and regulatory/evidence review', 'Informed discussion and monitoring plan'], ['peptides', 'medications'], status='prescriber_review_required')
    add('reassessment', 'Reassessment / outcomes', 'Treating clinician',
        'Track measurements and functional outcomes together; numerical direction alone does not establish clinical improvement.',
        ['Use consistent device, time of day and testing conditions for repeat measurements.',
         'Reassess strength, gait/balance, patient goals and symptoms alongside body composition.',
         'Choose the follow-up interval clinically; evaluate sooner if new symptoms or injuries arise.'],
        ['Baseline functional tests', 'Patient-defined goals', 'Clinician-selected interval'], ['device'],
        [change['metric'] for change in comparison.get('changes', [])])
    for domain in domains:
        if context['cardiovascular_symptoms'] == 'yes' and domain['id'] in ('medical', 'activity', 'arm_training', 'leg_training', 'balance'):
            domain['status'] = 'assessment_required'
            domain['rationale'] += ' Cardiovascular symptoms were reported; prioritize medical assessment before exercise progression.'
        if context['pain_present'] == 'yes' and domain['id'] in ('activity', 'arm_training', 'leg_training'):
            domain['status'] = 'assessment_required'
            domain['rationale'] += ' Pain or active injury was reported; select and load exercises only after a focused examination.'
        if context['falls_or_balance_concern'] == 'yes' and domain['id'] in ('balance', 'leg_training'):
            domain['rationale'] += ' Falls or balance concerns were reported; assess supervision and support requirements.'
        if context['activity_level'] == 'sedentary' and domain['id'] == 'activity':
            domain['rationale'] += ' A sedentary baseline was reported; start with short, tolerable sessions after assessment and build gradually.'
        if context['pregnancy_or_breastfeeding'] == 'yes' and domain['id'] == 'peptides':
            domain['rationale'] += ' Pregnancy or breastfeeding was reported; defer medication selection until a prescriber reviews product-specific restrictions.'
    missing = [key for key, value in context.items() if value == 'unknown' or value is False or value == '']
    return {'version': VERSION, 'status': 'draft_for_clinician_review', 'is_treatment_order': False,
            'source_result_id': result['id'], 'test_timestamp': result['test_timestamp'],
            'context': context, 'context_source': 'operator-entered; not independently verified',
            'missing_context': missing, 'source_confirmation_required': incomplete,
            'segmental_observations': segment_pairs, 'domains': domains, 'references': REFERENCES,
            'reference_checked_on': '2026-10-08',
            'limitations': ['No autonomous diagnosis or prescription.', 'Drafts are not orders or verified specialist opinions.',
                            'No live AI or external specialist consultation is claimed.',
                            'Context and functional findings are incomplete; source acceptance does not authorize treatment.']}
