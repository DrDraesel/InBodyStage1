from typing import Protocol

class InBodyAdapter(Protocol):
    def normalize(self, payload: dict) -> dict: ...

class MockOfficialAdapter:
    """Internal normalized fixture, NOT an assertion of vendor wire fields."""
    version = 'mock-normalized-v1.0'
    def normalize(self, payload):
        return payload

class LookinBodyAdapter:
    version = 'awaiting-validated-field-map'
    def normalize(self, payload):
        raise NotImplementedError('Live InBody mapping awaits account-specific official response and webhook documentation')
