"""Normalized contract. Unknown model-specific metrics remain explicit measurements."""
from datetime import datetime, date
import math
import re

VERSION = 'normalized-v1.0'
UNITS = {
    'weight': 'kg', 'bmi': 'kg/m2', 'skeletal_muscle_mass': 'kg',
    'body_fat_mass': 'kg', 'percent_body_fat': '%', 'total_body_water': 'L',
    'intracellular_water': 'L', 'extracellular_water': 'L', 'ecw_tbw': 'ratio',
    'dry_lean_mass': 'kg', 'lean_body_mass': 'kg', 'visceral_fat_level': 'level',
    'visceral_fat_area': 'cm2', 'basal_metabolic_rate': 'kcal/day',
    'phase_angle': 'deg', 'body_cell_mass': 'kg', 'inbody_score': 'score',
    'target_weight': 'kg', 'weight_control': 'kg', 'fat_control': 'kg',
    'muscle_control': 'kg', 'obesity_degree': '%',
}

class Invalid(ValueError):
    pass

def timestamp(value):
    if not isinstance(value, str):
        raise Invalid('test_timestamp must be an ISO 8601 string with timezone')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise Invalid('Invalid test timestamp')
    if parsed.tzinfo is None:
        raise Invalid('Test timezone is required; never substitute import time')
    return parsed.isoformat()

def safe_id(value, field='identifier'):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value):
        raise Invalid(f'Invalid {field}')
    return value

def normalize(payload):
    if not isinstance(payload, dict):
        raise Invalid('Result must be an object')
    stamp = timestamp(payload.get('test_timestamp'))
    encounter = safe_id(payload.get('encounter_id'), 'encounter_id')
    source_id = payload.get('source_identifier')
    if not isinstance(source_id, str) or not source_id.strip() or len(source_id) > 200:
        raise Invalid('source_identifier is required (maximum 200 characters)')
    items = payload.get('measurements')
    if not isinstance(items, list) or not items or len(items) > 200:
        raise Invalid('Provide 1–200 measurements')
    seen, normalized = set(), []
    for item in items:
        if not isinstance(item, dict):
            raise Invalid('Measurement must be an object')
        metric = safe_id(item.get('metric'), 'metric')
        if metric in seen:
            raise Invalid(f'Duplicate metric: {metric}')
        seen.add(metric)
        unit = item.get('unit')
        if not isinstance(unit, str) or len(unit) > 40 or not unit:
            raise Invalid(f'Explicit unit required for {metric}')
        value = item.get('value')
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
            raise Invalid(f'{metric} must be finite numeric or null')
        confidence = item.get('confidence', 1.0)
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise Invalid('Confidence must be 0–1')
        status = item.get('status', 'verified')
        if status not in ('verified', 'unverified'):
            raise Invalid('Unknown verification status')
        expected = UNITS.get(metric)
        original_value, original_unit = value, unit
        if expected == 'kg' and unit in ('lb', 'lbs'):
            value = None if value is None else round(value * 0.45359237, 6)
            unit = 'kg'
        if expected and unit != expected:
            raise Invalid(f'{metric} expects {expected}; unsupported unit {unit}')
        quality = item.get('quality_note', '')
        if not isinstance(quality, str) or len(quality) > 500:
            raise Invalid('Invalid quality note')
        if value is None or confidence < 0.90:
            status = 'unverified'
        if value is not None and ((metric in ('percent_body_fat', 'inbody_score') and not 0 <= value <= 100)
             or (metric == 'ecw_tbw' and not 0 < value < 1)
             or (metric in UNITS and metric not in ('weight_control','fat_control','muscle_control') and value < 0)):
            status, quality = 'unverified', 'Value fails physical plausibility check; confirm or correct.'
        ref = item.get('device_reference')
        if ref is not None:
            if not isinstance(ref, dict) or not all(k in ref for k in ('low','high','source','version')):
                raise Invalid('Device reference needs low, high, source, version')
            if not all(isinstance(ref[k], (int,float)) and math.isfinite(ref[k]) for k in ('low','high')) or ref['low'] > ref['high']:
                raise Invalid('Invalid reference interval')
            if unit != original_unit:
                raise Invalid('Supply device intervals in normalized units after conversion')
            if not ref['source'] or not ref['version']:
                raise Invalid('Reference source/version required')
        normalized.append({'metric':metric, 'value':value, 'unit':unit,
            'original_value':original_value, 'original_unit':original_unit,
            'confidence':confidence, 'status':status, 'quality_note':quality,
            'device_reference':ref})
    device = payload.get('device_model', 'Unknown')
    if not isinstance(device, str) or len(device) > 100:
        raise Invalid('Invalid device_model')
    return {'encounter_id':encounter, 'test_timestamp':stamp,
            'source_identifier':source_id, 'device_model':device, 'measurements':normalized}

def age_at(dob, stamp):
    if not dob:
        return None
    birth, when = date.fromisoformat(dob), datetime.fromisoformat(stamp).date()
    return when.year - birth.year - ((when.month, when.day) < (birth.month, birth.day))
