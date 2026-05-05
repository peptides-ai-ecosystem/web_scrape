import json
from typing import Any, Dict, List
from src.mappers.base_mapper import BaseMapper
from src.mappers.peptide_mapper import PeptideMapper
from src.mappers.related_entity_mappers import (
    ProtocolMapper, 
    SideEffectMapper, 
    ReconstitutionMapper,
    AdministrationMethodMapper,
    BenefitMapper,
    ResearchIndicationMapper,
    PeptideInteractionMapper,
    QualityIndicatorMapper,
    ReferenceMapper
)
from src.infrastructure.db_manager import DbManager

class DbImportOrchestrator:
    """
    Orchestrates the conversion of a raw data row into a fully structured dictionary.
    """

    def __init__(self):
        self.peptide_mapper = PeptideMapper()
        self.protocol_mapper = ProtocolMapper()
        self.side_effect_mapper = SideEffectMapper()
        self.reconstitution_mapper = ReconstitutionMapper()
        self.admin_method_mapper = AdministrationMethodMapper()
        self.benefit_mapper = BenefitMapper()
        self.research_indication_mapper = ResearchIndicationMapper()
        self.peptide_interaction_mapper = PeptideInteractionMapper()
        self.quality_indicator_mapper = QualityIndicatorMapper()
        self.reference_mapper = ReferenceMapper()

    def map_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps a single CSV/scraped row into a multi-table insertion payload.
        """
        peptides_payload = self.peptide_mapper.map(row)
        
        # Build relational payload structure
        payload = {
            "peptides": peptides_payload,
            "related_inserts": {
                "protocols": self.protocol_mapper.map(row),
                "side_effects": self.side_effect_mapper.map(row),
                "reconstitution_steps": self.reconstitution_mapper.map(row),
                "administration_methods": self.admin_method_mapper.map(row),
                "benefits": self.benefit_mapper.map(row),
                "research_indications": self.research_indication_mapper.map(row),
                "peptide_interactions": self.peptide_interaction_mapper.map(row),
                "quality_indicators": self.quality_indicator_mapper.map(row),
                "references": self.reference_mapper.map(row)
            }
        }
        return payload

    def map_dataset(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Maps an entire dataset. Useful if passing output from scraper_manager.
        """
        return [self.map_row(row) for row in rows]

    def sync_to_db(self, db_url: str, rows: List[Dict[str, Any]]):
        """
        Main entry point to sync a list of raw rows to the DB.
        """
        db = DbManager(db_url)
        try:
            for row in rows:
                payload = self.map_row(row)
                peptide_id = db.upsert_peptide_fill_nulls(payload['peptides'])
                
                # Sync relations
                self._sync_relations(db, peptide_id, payload['related_inserts'])
        finally:
            db.close()

    def _sync_relations(self, db: DbManager, peptide_id: int, relations: Dict[str, Any]):
        # 1. Administration Methods
        for am in relations.get("administration_methods", []):
            db.insert_lookup("administration_methods", am['name'])

        # 2. Benefits
        for b in relations.get("benefits", []):
            b_id = db.insert_lookup("benefits", b['name'])
            db.link_relation("peptide_benefits", "peptide_id", peptide_id, "benefit_id", b_id)

        # 3. Side Effects
        for se in relations.get("side_effects", []):
            se_id = db.insert_lookup("side_effects", se['name'])
            db.link_relation("peptide_side_effects", "peptide_id", peptide_id, "side_effect_id", se_id)

        # 4. Protocols
        for p in relations.get("protocols", []):
            am_name = p.get("route_name", "").split("(")[0].strip() or "General"
            am_id = db.insert_lookup("administration_methods", am_name)
            
            with db.connect().cursor() as cur:
                cur.execute(
                    "SELECT id FROM peptide_protocols WHERE peptide_id = %s AND administration_method_id = %s AND name = %s",
                    (peptide_id, am_id, p['name'])
                )
                row = cur.fetchone()
                if row:
                    protocol_id = row['id']
                else:
                    cur.execute(
                        "INSERT INTO peptide_protocols (peptide_id, administration_method_id, name, description) VALUES (%s, %s, %s, %s) RETURNING id",
                        (peptide_id, am_id, p['name'], p['description'])
                    )
                    protocol_id = cur.fetchone()['id']
                    db.conn.commit()

                if p.get('expectations'):
                    cur.execute(
                        "UPDATE peptide_protocols SET expectations = %s WHERE id = %s AND (expectations IS NULL OR expectations = '[]'::jsonb)",
                        (json.dumps(p['expectations']), protocol_id)
                    )
                    db.conn.commit()

        # 5. Interactions
        for inter in relations.get("peptide_interactions", []):
            # Check if exists
            with db.connect().cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM peptide_interactions WHERE peptide_id_1 = %s AND peptide_name_2 = %s",
                    (peptide_id, inter['secondary_peptide_name'])
                )
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO peptide_interactions (peptide_id_1, peptide_name_2, interaction_type, description) VALUES (%s, %s, %s, %s)",
                        (peptide_id, inter['secondary_peptide_name'], inter['interaction_type'], inter['description'])
                    )
                    db.conn.commit()

        # 6. Research Indications
        for ind in relations.get("research_indications", []):
            with db.connect().cursor() as cur:
                cur.execute(
                    "SELECT id FROM peptide_research_indications WHERE peptide_id = %s AND indication_title = %s",
                    (peptide_id, ind['indication_title'])
                )
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO peptide_research_indications (peptide_id, indication_title, effectiveness_tag) VALUES (%s, %s, %s)",
                        (peptide_id, ind['indication_title'], ind['effectiveness_tag'])
                    )
                    db.conn.commit()

        # 7. References
        for ref in relations.get("references", []):
            with db.connect().cursor() as cur:
                cur.execute(
                    "SELECT id FROM peptide_references WHERE peptide_id = %s AND title = %s",
                    (peptide_id, ref['title'])
                )
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO peptide_references (peptide_id, reference_type, title, url, abstract) VALUES (%s, %s, %s, %s, %s)",
                        (peptide_id, ref['reference_type'], ref['title'], ref.get('url', ''), ref.get('abstract', ''))
                    )
                    db.conn.commit()
