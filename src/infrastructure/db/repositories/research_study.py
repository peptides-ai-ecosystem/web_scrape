"""Research study repository for research study operations."""
from typing import Dict, Any, Optional
from src.infrastructure.db.base_repository import BaseRepository


class ResearchStudyRepository(BaseRepository):
    """Repository for research study entity operations."""

    def upsert(self, study: Dict[str, Any]) -> int:
        """
        Upserts a research study.
        Returns the study ID.
        """
        title = study.get("title", "Unknown Study")
        url = study.get("url", "")
        abstract = study.get("abstract", "")
        
        with self.get_cursor() as cur:
            cur.execute("SELECT id, url, abstract FROM research_studies WHERE title = %s", (title,))
            existing = cur.fetchone()
            
            if existing:
                study_id = existing['id']
                updates = {}
                if url and not existing['url']:
                    updates['url'] = url
                if abstract and not existing['abstract']:
                    # Process abstract, remove rest text from .View Study
                    if ".View Study" in abstract:
                        abstract = abstract.split(".View Study")[0]
                    updates['abstract'] = abstract
                
                if updates:
                    set_clause = ", ".join([f"{col} = %s" for col in updates.keys()])
                    cur.execute(
                        f"UPDATE research_studies SET {set_clause} WHERE id = %s",
                        list(updates.values()) + [study_id]
                    )
                    self._commit()
                    self.log_operation("UPDATE_STUDY", "research_studies", f"'{title}' (ID: {study_id})")
                else:
                    self.log_operation("EXIST_STUDY", "research_studies", f"'{title}' (ID: {study_id})")
                return study_id
            
            cur.execute(
                "INSERT INTO research_studies (title, url, abstract) VALUES (%s, %s, %s) RETURNING id",
                (title, url, abstract)
            )
            new_id = cur.fetchone()['id']
            self._commit()
            self.log_operation("INSERT_STUDY", "research_studies", f"'{title}' (ID: {new_id})")
            return new_id

    def get_id_by_title(self, title: str) -> Optional[int]:
        """Get study ID by title."""
        title = title or "Unknown Study"
        return self.execute_scalar("SELECT id FROM research_studies WHERE title = %s", (title,))

    def get_by_id(self, study_id: int) -> Optional[Dict[str, Any]]:
        """Get study by ID."""
        return self.execute_one("SELECT * FROM research_studies WHERE id = %s", (study_id,))
