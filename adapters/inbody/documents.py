"""Conservative label/value extraction. All extracted fields require human confirmation."""
import io
import re
import subprocess
import tempfile
from pathlib import Path
from backend.validation import UNITS, Invalid

PARSER_VERSION = 'printed-report-parser-v1.1'
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
for segment in ('right_arm','left_arm','trunk','right_leg','left_leg'):
    for field in ('lean_mass','fat_mass','body_water','phase_angle','ecw_tbw'):
        metric = segment+'_'+field
        ALIASES[metric] = [metric.replace('_',' '), field.replace('_',' ')+' '+segment.replace('_',' ')]

def expected_unit(metric):
    return UNITS.get(metric) or ('ratio' if metric.endswith('ecw_tbw') else
        'deg' if metric.endswith('phase_angle') else 'L' if metric.endswith('body_water') else 'kg')

def load_image(data):
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = 20_000_000
    try:
        image = Image.open(io.BytesIO(data))
        if image.width*image.height > 20_000_000 or image.format not in ('PNG','JPEG'):
            raise Invalid('Only PNG/JPEG images up to 20 million pixels are accepted')
        image.load()
        return ImageOps.exif_transpose(image).convert('RGB')
    except Invalid:
        raise
    except Exception:
        raise Invalid('Unreadable or unsafe image')

def decode_codes(data):
    image = load_image(data)
    try:
        import zxingcpp
    except ImportError:
        return [], 'Barcode decoder unavailable; install requirements or use scanner entry.'
    decoded = zxingcpp.read_barcodes(image)
    if len(decoded)>32 or any(len(code.text)>4096 for code in decoded):
        raise Invalid('Barcode count or content exceeds limits')
    # Preserve evidence only. Never follow URLs, run commands or infer patient identity.
    return [{'format':str(code.format),'text':code.text,'status':'unverified',
             'purpose':'unmapped source code; not a verified measurement'} for code in decoded], None

MAX_BYTES = 10 * 1024 * 1024

def ocr(data):
    from PIL import ImageOps
    image = ImageOps.autocontrast(load_image(data).convert('L'))
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'input.png'
        image.convert('RGB').save(path)
        try:
            result = subprocess.run(['tesseract',str(path),'stdout','--psm','6'],
                capture_output=True, timeout=30, check=True)
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            raise Invalid('OCR unavailable or failed; use manual entry')
        return result.stdout.decode('utf-8', errors='replace')

def extract(data, kind, allow_empty=False):
    if len(data) > MAX_BYTES:
        raise Invalid('Maximum file size is 10 MiB')
    pages, codes, warnings = [], [], []
    if kind == 'pdf':
        if not data.startswith(b'%PDF-'):
            raise Invalid('File signature is not PDF')
        import fitz
        try:
            with fitz.open(stream=data, filetype='pdf') as doc:
                if doc.is_encrypted or not 0 < len(doc) <= 10:
                    raise Invalid('PDF must be unencrypted and have 1–10 pages')
                for number, page in enumerate(doc,1):
                    # Every page is inspected: mixed text/scanned PDFs must not lose scanned pages.
                    pixels = page.rect.width*page.rect.height*4
                    if pixels>20_000_000:
                        raise Invalid('PDF page exceeds rendered pixel limit')
                    image = page.get_pixmap(matrix=fitz.Matrix(2,2)).tobytes('png')
                    page_codes, warning = decode_codes(image)
                    codes.extend(dict(code,page=number) for code in page_codes)
                    if warning: warnings.append(warning)
                    page_text = page.get_text(sort=True)
                    method = 'pdf-text'
                    if not page_text.strip():
                        page_text, method = ocr(image), 'ocr'
                    pages.append({'page':number,'method':method,'text':page_text})
        except Invalid:
            raise
        except Exception:
            raise Invalid('Unable to parse PDF')
    elif kind == 'image':
        codes, warning = decode_codes(data)
        if warning: warnings.append(warning)
        pages = [{'page':1,'method':'ocr','text':ocr(data)}]
    else:
        raise Invalid('Unsupported file type')
    text = '\n'.join(page['text'] for page in pages)
    if len(text)>200_000 or len(codes)>32:
        raise Invalid('Extracted evidence exceeds limits')
    parsed = parse_text(text,allow_empty=allow_empty)
    parsed.update({'pages':pages,'raw_text':text,'barcodes':codes,'warnings':list(dict.fromkeys(warnings)),
        'parser_version':PARSER_VERSION,'coverage':'Explicit labeled fields only; full source text is retained. Charts and unsupported layouts require transcription.'})
    return parsed

def parse_text(text, allow_empty=False):
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
                expected = expected_unit(metric)
                # Handle explicit unit headings on printed sheets, including a following value line.
                heading = re.match(r'^\(([^)]+)\)\s*(.*)$',tail)
                if heading:
                    rest = heading[2].strip()
                    if not rest:
                        lines = text.splitlines(); index = lines.index(line)
                        rest = lines[index+1].strip() if index+1<len(lines) else ''
                    tail = rest+' '+heading[1]
                numeric = re.match(r'^(-?\d+(?:\.\d+)?)\s*(.*?)\s*(?:\([\d.\s~–-]+\))?$', tail)
                value = float(numeric[1]) if numeric else None
                raw_unit = numeric[2].strip().lower() if numeric else ''
                accepted = {expected.lower(), 'kg/m²' if metric == 'bmi' else expected.lower()}
                if expected == 'kg':
                    accepted |= {'lb','lbs'}
                if raw_unit not in accepted:
                    value = None
                unit = ('L' if raw_unit=='l' else raw_unit) if raw_unit in accepted else expected
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
    if not measurements and not allow_empty:
        raise Invalid('No labeled measurements found. Enter values manually and retain the source document.')
    claimed = re.search(r'^\s*Patient ID\s*:\s*([A-Za-z0-9_-]+)\s*$', text, re.M|re.I)
    return {'measurements':measurements, 'claimed_patient_id':claimed[1] if claimed else None}
