from abc import ABC, abstractmethod
from typing import Any, List, Dict, Tuple, Optional
from .models import PeptideData

class IExtractor(ABC):
    @abstractmethod
    def extract(self, driver: Any, wait: Any) -> Any:
        pass

class IStorage(ABC):
    @abstractmethod
    def save(self, data: List[PeptideData]) -> None:
        pass

class IScraper(ABC):
    @abstractmethod
    def scrape(self, url: str) -> Tuple[List[PeptideData], Optional[str]]:
        pass
