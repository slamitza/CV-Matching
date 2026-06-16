from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from ..models import JobPosting


class JobSource(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def fetch(self) -> Iterable[JobPosting]:
        """Return job postings from the source."""
