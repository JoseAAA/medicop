from datetime import datetime

from pydantic import BaseModel, Field


class GuidelineRead(BaseModel):
    id: str
    title: str
    institution: str
    year: int
    category: str
    applicable_areas: list[str] = Field(default_factory=list)
    is_demo: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


class GuidelineDetail(GuidelineRead):
    """Igual que GuidelineRead pero incluye el contenido completo (Markdown)."""

    content: str
