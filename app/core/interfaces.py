from abc import ABC, abstractmethod
from typing import Any

from .models import PeptideData


class IExtractor(ABC):
    @abstractmethod
    def extract(self, driver: Any, wait: Any) -> Any:
        pass


class IStorage(ABC):
    @abstractmethod
    def save(self, data: list[PeptideData]) -> None:
        pass


class IScraper(ABC):
    @abstractmethod
    def scrape(self, url: str) -> tuple[list[PeptideData], str | None]:
        pass
