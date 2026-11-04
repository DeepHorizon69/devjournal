from __future__ import annotations

from fastapi import APIRouter

from app.models.api_models import TemplatesListResponse
from app.services.template_svc import TemplateService

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("", response_model=TemplatesListResponse)
def list_templates() -> TemplatesListResponse:
    """Return the 5 canonical built-in note creation templates."""
    return TemplateService().list_templates()
