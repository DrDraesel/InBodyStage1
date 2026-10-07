"""AI returns explanation references only; facts remain deterministic and immutable."""
from typing import Protocol
import json
import os
import urllib.request
from urllib.parse import urlparse

class ModelProvider(Protocol):
    def synthesize(self, evidence: dict) -> dict: ...

class LocalModelProvider(ModelProvider, Protocol):
    """Implement synthesize or use OpenAICompatibleProvider with local Qwen endpoint."""
    pass

class OpenAICompatibleProvider:
    def __init__(self, base_url, key, model):
        self.base_url, self.key, self.model = base_url.rstrip('/'), key, model
        parsed = urlparse(self.base_url)
        if parsed.scheme != 'https' and not (parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1')):
            raise ValueError('AI endpoint must use HTTPS or loopback HTTP')
        if not model:
            raise ValueError('AI_MODEL is required when AI is enabled')

    def synthesize(self, evidence):
        # Only approved sentences can be selected; arbitrary AI prose is not accepted clinically.
        request = {'model':self.model, 'temperature':0, 'response_format':{'type':'json_object'},
            'messages':[{'role':'system','content':'You are an explanation selector. Choose relevant sentence IDs from the supplied deterministic evidence. Do not add facts, numbers, diagnoses, advice, or prose. Return JSON with clinician_sentence_ids and patient_sentence_ids arrays only.'},
                        {'role':'user','content':json.dumps(evidence)}]}
        req = urllib.request.Request(self.base_url+'/chat/completions',
            data=json.dumps(request).encode(),headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=20) as response:
            content = json.loads(response.read(1_000_000))
        selected = json.loads(content['choices'][0]['message']['content'])
        if set(selected) != {'clinician_sentence_ids','patient_sentence_ids'}:
            raise ValueError('Malformed AI response')
        allowed = evidence['sentences']
        for ids in selected.values():
            if not isinstance(ids,list) or len(ids)>100 or not all(isinstance(i,str) and i in allowed for i in ids):
                raise ValueError('AI returned unsupported evidence')
        return {'provider':'openai-compatible','model':self.model,
            'reported_model':content.get('model',self.model),'interface_version':'evidence-selection-v1.0',
            'clinician':[allowed[i] for i in selected['clinician_sentence_ids']],
            'patient':[allowed[i] for i in selected['patient_sentence_ids']]}

def configured_provider():
    if os.getenv('AI_ENABLED','false').lower() != 'true':
        return None
    return OpenAICompatibleProvider(os.getenv('AI_BASE_URL','https://api.openai.com/v1'),
        os.getenv('AI_API_KEY',''),os.getenv('AI_MODEL',''))
