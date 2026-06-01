"""
CitationRepositoryV2 — Final version with unique DOI generation.

Handles NOT NULL + UNIQUE constraint on DOI by generating unique placeholders.
"""
import hashlib
from typing import Any, Dict, Optional
from src.infrastructure.db_v2.base_repository import BaseRepositoryV2


class CitationRepositoryV2(BaseRepositoryV2):

    def upsert(self, citation: Dict[str, Any]) -> int:
        """Safe Citation upsert satisfying NOT NULL + UNIQUE DOI constraint."""
        title = (citation.get("title") or "Unknown Citation").strip()
        url = citation.get("url") or ""
        abstract = citation.get("abstract") or ""
        authors = citation.get("authors") or ""
        doi = citation.get("doi") or "none"
        
        # Schema requires DOI to be NOT NULL and UNIQUE.
        # If missing or 'none', we generate a unique placeholder based on the title.
        db_doi = doi
        if not doi or doi.lower() == "none" or doi.strip() == "":
            # Unique stable hash of title
            title_hash = hashlib.md5(title.encode()).hexdigest()[:16]
            db_doi = f"NON-DOI-{title_hash}"

        # 1. Check for existing
        # Try DOI first
        existing = self.execute_one("SELECT id FROM citations WHERE doi = %s", (db_doi,))
        
        if not existing:
            # Try Title
            existing = self.execute_one("SELECT id FROM citations WHERE LOWER(title) = LOWER(%s)", (title,))

        if existing:
            citation_id = existing["id"]
            self.log_op("EXIST_CITATION", "citations", f"'{title[:30]}...' (ID: {citation_id})")
            return citation_id

        # 2. INSERT
        sql = """
            INSERT INTO citations (title, publication_url, abstract, doi, authors)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        citation_id = self.execute_returning(sql, (title, url, abstract, db_doi, authors))
        self.log_op("INSERT_CITATION", "citations", f"'{title[:30]}...' (ID: {citation_id})")
        return citation_id

    def get_id_by_title(self, title: str) -> Optional[int]:
        title = title or "Unknown Citation"
        return self.execute_scalar("SELECT id FROM citations WHERE LOWER(title) = LOWER(%s)", (title,))
