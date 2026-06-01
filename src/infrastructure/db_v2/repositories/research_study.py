"""
ResearchStudyRepositoryV2 — Fixed: research_studies has no UNIQUE(title).

Falls back to SELECT → INSERT inside the caller's single transaction.
"""
from typing import Any, Dict, Optional
from src.infrastructure.db_v2.base_repository import BaseRepositoryV2


class ResearchStudyRepositoryV2(BaseRepositoryV2):

    def upsert(self, study: Dict[str, Any]) -> int:
        title = study.get("title") or "Unknown Study"
        url = study.get("url") or ""
        abstract = study.get("abstract") or ""
        if ".View Study" in abstract:
            abstract = abstract.split(".View Study")[0]

        existing = self.execute_one(
            "SELECT id, url, abstract FROM research_studies WHERE title = %s", (title,)
        )
        if existing:
            study_id = existing["id"]
            updates = {}
            if url and not existing["url"]:
                updates["url"] = url
            if abstract and not existing["abstract"]:
                updates["abstract"] = abstract
            if updates:
                set_clause = ", ".join([f"{col} = %s" for col in updates])
                self.execute_write(
                    f"UPDATE research_studies SET {set_clause} WHERE id = %s",
                    list(updates.values()) + [study_id],
                )
            self.log_op("UPSERT_STUDY", "research_studies", f"'{title}' (ID: {study_id})")
            return study_id

        study_id = self.execute_returning(
            "INSERT INTO research_studies (title, url, abstract) VALUES (%s, %s, %s) RETURNING id",
            (title, url, abstract),
        )
        self.log_op("INSERT_STUDY", "research_studies", f"'{title}' (ID: {study_id})")
        return study_id

    def get_id_by_title(self, title: str) -> Optional[int]:
        return self.execute_scalar(
            "SELECT id FROM research_studies WHERE title = %s", (title or "Unknown Study",)
        )
