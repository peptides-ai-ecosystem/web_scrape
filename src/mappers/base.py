from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseMapper(ABC):
    """
    Abstract base class for all database mappers.
    Ensures a single responsibility for mapping data to a specific schema payload.
    """

    @abstractmethod
    def map(self, row: Dict[str, Any]) -> Any:
        """
        Maps the raw extracted dictionary (or CSV row) to a database table payload.

        Args:
            row: Raw dictionary row parsed from CSV or scraper.

        Returns:
            A dictionary or list of dictionaries ready for DB insertion.
        """
        pass
