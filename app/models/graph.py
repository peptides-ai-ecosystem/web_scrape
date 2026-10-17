"""Response models for the PK graph API (``/api/v1/peptides``, ``/api/v1/peptide/{id}/methods``)."""

from pydantic import BaseModel, Field


class PeptideItem(BaseModel):
    id: int = Field(..., description="Peptide database ID.")
    name: str = Field(..., description="Peptide display name.")


class MethodItem(BaseModel):
    id: int = Field(..., description="Administration method database ID.")
    name: str = Field(..., description="Administration method name (e.g. 'Injectable', 'Oral').")
