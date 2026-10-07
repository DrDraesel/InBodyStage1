"""Conservative label/value extraction. All extracted fields require human confirmation."""
import io
import re
import subprocess
import tempfile
from pathlib import Path
from backend.validation import UNITS, Invalid

PARSER_VERSION = 'label-parser-v1.0'
ALIASES = {
 'weight': ['weight'], 'bmi':['bmi','body mass index'],
 'skeletal_muscle_mass':['skeletal muscle mass','smm'],
 'body_fat_mass':['body fat mass'], 'percent_body_fat':['percent body fat','pbf'],
 'total_body_water':['total body water','tbw'],
 'intracellular_water':['intracellular water','icw'],
 'extracellular_water':['extracellular water','ecw'], 'ecw_tbw':['ecw/tbw','ecw tbw'],
 'dry_lean_mass':['dry lean mass'], 'lean_body_mass':['lean body mass','fat free mass'],
 'visceral_fat_level':['visceral fat level'], 'visceral_fat_area':['visceral fat area'],
 'basal_metabolic_rate':['basal metabolic rate','bmr'], 'phase_angle':['phase angle'],
 'body_cell_mass':['body cell mass'], 'inbody_score':['inbody score'],
 'target_weight':['target weight'], 'weight_control':['weight control'],
 'fat_control':['fat control'], 'muscle_control':['muscle control'],
 'obesity_degree':['obesity degree'],
}

MAX_BYTES = 10 * 1024 * 1024

def ocr(data):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 20_000_000
    try:
        image = Image.open(io.BytesIO(data))
        if image.width*image.height > 20_000_000:
            raise Invalid('Image exceeds pixel limit')
        if image.format not in ('PNG','JPEG'):
            raise Invalid('Only PNG/JPEG images are accepted')
        image.load()
    except Invalid:
        raise
    except Exception:
        raise Invalid('Unreadable or unsafe image')
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'input.png'
        image.convert('RGB').save(path)
        try:
            result = subprocess.run(['tesseract',str(path),'stdout','--psm','6'],
                capture_output=True, timeout=30, check=True)
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            raise Invalid('OCR unavailable or failed; use manual entry')
        return result.stdout.decode('utf-8', errors='replace')

def extract(data, kind):
    if len(data) > MAX_BYTES:
        raise Invalid('Maximum file size is 10 MiB')
    if kind == 'pdf':
        if not data.startswith(b'%PDF-'):
            raise Invalid('File signature is not PDF')
        import fitz
        try:
            with fitz.open(stream=data, filetype='pdf') as doc:
                if doc.is_encrypted or not 0 < len(doc) <= 10:
                    raise Invalid('PDF must be unencrypted and have 1–10 pages')
                text = '\n'.join(page.get_text() for page in doc)
                if not text.strip():
                    text = '\n'.join(ocr(page.get_pixmap(matrix=fitz.Matrix(1.5,1.5)).tobytes('png')) for page in doc)
        except Invalid:
            raise
        except Exception:
            raise Invalid('Unable to parse PDF')
    elif kind == 'image':
        text = ocr(data)
    else:
        raise Invalid('Unsupported file type')
    return parse_text(text)

def parse_text(text):
    measurements = []
    # Only explicitly labeled values with explicit units; no assumptions from chart placement.
    for metric, aliases in ALIASES.items():
        matches = []
        for line in text.splitlines():
            for alias in aliases:
                pattern = r'^\s*' + re.escape(alias) + r'\s*[:=]?\s*(.*)$'
                match = re.match(pattern, line, re.I)
                if not match:
                    continue
                tail = match[1].strip()
                numeric = re.match(r'^(-?\d+(?:\.\d+)?)\s*([^\d\n]*)$', tail)
                value = float(numeric[1]) if numeric else None
                raw_unit = numeric[2].strip().lower() if numeric else ''
                accepted = {UNITS[metric], 'kg/m²' if metric == 'bmi' else UNITS[metric]}
                if UNITS[metric] == 'kg':
                    accepted |= {'lb','lbs'}
                if raw_unit not in accepted:
                    value = None
                unit = raw_unit if raw_unit in accepted else UNITS[metric]
                if unit == 'kg/m²':
                    unit = 'kg/m2'
                matches.append((value,unit))
                break
        if not matches:
            continue
        conflict = len(set(matches)) > 1
        value,unit = matches[0]
        if conflict:
            value = None
        measurements.append({'metric':metric,'value':value,'unit':unit,
            'confidence':0.80 if value is not None else 0.0,'status':'unverified',
            'quality_note': 'Conflicting source values.' if conflict else 'Confirm against original source; label parser does not validate identity or report layout.'})
    if not measurements:
        raise Invalid('No labeled measurements found. Enter values manually and retain the source document.')
    claimed = re.search(r'^\s*Patient ID\s*:\s*([A-Za-z0-9_-]+)\s*$', text, re.M|re.I)
    return {'measurements':measurements, 'claimed_patient_id':claimed[1] if claimed else None}
