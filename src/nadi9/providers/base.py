from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, purpose: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
