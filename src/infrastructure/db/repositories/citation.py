"""Citation repository for citation operations."""
from typing import Dict, Any, Optional
from src.infrastructure.db.base_repository import BaseRepository


class CitationRepository(BaseRepository):
    """Repository for citation entity operations."""

    def upsert(self, citation: Dict[str, Any]) -> int:
        """
        Upserts a citation.
        Returns the citation ID.
        """
        title = citation.get("title", "Unknown Citation")
        url = citation.get("url", "")
        abstract = citation.get("abstract", "")
        authors = citation.get("authors", "")
        
        # doi is NOT NULL and UNIQUE in schema, providing placeholder if empty
        doi = citation.get("doi")
        if not doi:
            doi = "none"
        
        with self.get_cursor() as cur:
            # Check by title OR doi to cope with UNIQUE doi constraint
            cur.execute(
                "SELECT id, publication_url, abstract, authors FROM citations WHERE title = %s OR doi = %s", 
                (title, doi)
            )
            existing = cur.fetchone()
            
            if existing:
                citation_id = existing['id']
                updates = {}
                if url and not existing['publication_url']:
                    updates['publication_url'] = url
                if abstract and not existing['abstract']:
                    updates['abstract'] = abstract
                if authors and not existing['authors']:
                    updates['authors'] = authors
                
                if updates:
                    set_clause = ", ".join([f"{col} = %s" for col in updates.keys()])
                    cur.execute(
                        f"UPDATE citations SET {set_clause} WHERE id = %s",
                        list(updates.values()) + [citation_id]
                    )
                    self._commit()
                    self.log_operation("UPDATE_CITATION", "citations", f"(ID: {citation_id})")
                else:
                    self.log_operation("EXIST_CITATION", "citations", f"(ID: {citation_id})")
                return citation_id
            
            cur.execute(
                "INSERT INTO citations (title, publication_url, abstract, doi, authors) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (title, url, abstract, doi, authors)
            )
            new_id = cur.fetchone()['id']
            self._commit()
            self.log_operation("INSERT_CITATION", "citations", f"(ID: {new_id})")
            return new_id

    def get_id_by_title(self, title: str) -> Optional[int]:
        """Get citation ID by title."""
        title = title or "Unknown Citation"
        return self.execute_scalar("SELECT id FROM citations WHERE title = %s", (title,))

    def get_by_id(self, citation_id: int) -> Optional[Dict[str, Any]]:
        """Get citation by ID."""
        return self.execute_one("SELECT * FROM citations WHERE id = %s", (citation_id,))
