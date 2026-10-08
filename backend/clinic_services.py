"""Website-advertised IMW services; operational capacity and eligibility are not implied."""
from copy import deepcopy

VERSION = 'imw-website-catalog-v1.0'
BASE = 'https://www.innovativemedicalwellness.com/en/'
CATALOG = [
    {'id': 'rehabilitation', 'title': 'Chiropractic and rehabilitation assessment', 'page': 'chiropractic-and-physical-therapy',
     'listed_options': ['Spinal decompression', 'Chiropractic adjustments', 'Postural rehabilitation', 'Shockwave and laser modalities'],
     'needed': 'Pain, injury, mobility and functional examination; modality-specific contraindications.'},
    {'id': 'weight_management', 'title': 'Medical weight-management assessment', 'page': 'weight-loss-programs',
     'listed_options': ['Semaglutide-based care', 'Metabolic assessment', 'Brown-fat activation discussion'],
     'needed': 'Patient goals, metabolic history, medication suitability and a clinician-defined plan. No weight-loss eligibility inferred from InBody alone.'},
    {'id': 'hormone_review', 'title': 'Hormone and longevity consultation', 'page': 'anti-aging-medicine',
     'listed_options': ['Hormone replacement', 'Testosterone assessment', 'NAD+ discussion'],
     'needed': 'Relevant symptoms, diagnosis, labs and prescriber review. Muscle or fat estimates do not diagnose a hormone deficiency.'},
    {'id': 'wellness', 'title': 'Lifestyle and personalized wellness', 'page': 'biohacking-and-optimization',
     'listed_options': ['Red-light modalities', 'Mind-body practices', 'Vagus-nerve stimulation discussion', 'Individual wellness planning'],
     'needed': 'Goals, device-specific assessment and an evidence-informed discussion; website benefit claims are not evidence of efficacy.'},
    {'id': 'joint_review', 'title': 'Joint and musculoskeletal consultation', 'page': 'regenerative-medicine',
     'listed_options': ['Joint injections', 'PRP discussion'],
     'needed': 'Diagnosed condition, examination, product/procedure-specific evidence and medical eligibility.'},
    {'id': 'infusion_review', 'title': 'Infusion assessment', 'page': 'iv-therapy',
     'listed_options': ['Micronutrient infusions', 'NAD+ infusions'],
     'needed': 'Medical indication, relevant labs, renal/cardiac status and interaction review. An InBody result does not establish an infusion requirement.'},
    {'id': 'brain_health', 'title': 'Brain-health evaluation', 'page': 'brain-health',
     'listed_options': ['Clarity Direct Neurofeedback', 'PEMF discussion'],
     'needed': 'Symptoms and domain-specific evaluation; body composition is not a neurofeedback or PEMF indication.'},
    {'id': 'injury_review', 'title': 'Post-injury and concussion review', 'page': 'personal-injury',
     'listed_options': ['Post-collision concussion assessment', 'Medical-legal documentation'],
     'needed': 'Actual injury history, neurological/clinical assessment and appropriate documentation.'},
    {'id': 'aesthetic_review', 'title': 'Hair and aesthetic consultation', 'page': 'aesthetic-treatments',
     'listed_options': ['PRP aesthetics discussion', 'Hair-restoration consultation'],
     'needed': 'Patient-requested goal and dedicated assessment. Educational discussion of transplants on the page does not confirm in-clinic surgical capacity.'},
    {'id': 'pelvic_health', 'title': 'Pelvic-health / VTone consultation', 'page': 'v-tone',
     'listed_options': ['VTone pelvic-floor treatment discussion'],
     'needed': 'Relevant symptoms, pelvic-health assessment and device eligibility. Page contains a [Medspa Name] placeholder; operational details need confirmation.'},
    {'id': 'exomind', 'title': 'ExoMind consultation', 'page': '',
     'listed_options': ['ExoMind brain-stimulation service linked from the clinic homepage'],
     'needed': 'Dedicated medical evaluation, intended-use and contraindication review; not selected from InBody measurements.'},
    {'id': 'exosome_review', 'title': 'Exosome offering — evidence and regulatory review', 'page': 'weight-loss-programs',
     'listed_options': ['The website advertises exosome infusions'],
     'needed': 'Independent evidence and regulatory review. FDA reports no approved exosome products; this is not an automatically recommended weight-loss or recovery intervention.',
     'safety_reference': 'https://www.fda.gov/safety/medical-product-safety-information/public-safety-alert-due-marketing-unapproved-stem-cell-and-exosome-products'},
]
TOPICS = {entry['id'] for entry in CATALOG}


def service_options(context):
    requested = set(context.get('requested_service_topics', []))
    options = deepcopy(CATALOG)
    for entry in options:
        entry['source_url'] = BASE + entry.pop('page')
        entry['website_checked_on'] = '2026-10-08'
        entry['availability_status'] = 'website_advertised; operational_availability_unverified'
        entry['status'] = 'education_requested' if entry['id'] in requested else 'catalog_only'
        entry['relevance_basis'] = 'Patient/operator requested education' if entry['id'] in requested else 'No patient-specific service indication established'
        if entry['id'] == 'rehabilitation' and (context.get('pain_present') == 'yes' or context.get('falls_or_balance_concern') == 'yes'):
            entry['status'] = 'assessment_topic'
            entry['relevance_basis'] = 'Reported pain or balance concern supports discussion of an assessment; a procedure is not selected'
        if entry['id'] == 'exosome_review':
            entry['status'] = 'evidence_regulatory_review_required'
        entry['price'] = None
        entry['clinician_review_required'] = True
        entry['booking_created'] = False
    return options
