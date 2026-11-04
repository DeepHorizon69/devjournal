from __future__ import annotations

from app.models.api_models import TemplateItem, TemplatesListResponse
from app.services.vault_storage import InvalidInputError

BUILTIN_TEMPLATES: tuple[TemplateItem, ...] = (
    TemplateItem(
        id="general",
        name="General Note",
        note_type="note",
        default_status=None,
        folder="10-Notes",
        body="## Overview\n\n## Key Concepts\n\n## References\n",
    ),
    TemplateItem(
        id="experiment",
        name="Experiment",
        note_type="experiment",
        default_status="active",
        folder="30-Experiments",
        body=(
            "## Objective\n\n"
            "## Environment & Setup\n\n"
            "## Procedure\n\n"
            "## Observations & Metrics\n\n"
            "## Conclusion\n"
        ),
    ),
    TemplateItem(
        id="troubleshooting",
        name="Troubleshooting",
        note_type="troubleshooting",
        default_status="investigating",
        folder="40-Troubleshooting",
        body=(
            "## Problem Statement\n\n"
            "## Symptoms & Logs\n\n"
            "## Root Cause Analysis\n\n"
            "## Resolution & Verification\n"
        ),
    ),
    TemplateItem(
        id="project",
        name="Project",
        note_type="project",
        default_status="active",
        folder="20-Projects",
        body=(
            "## Project Overview\n\n"
            "## Architecture & Goals\n\n"
            "## Milestones & Tasks\n\n"
            "## Decisions & Trade-offs\n"
        ),
    ),
    TemplateItem(
        id="daily",
        name="Daily Journal",
        note_type="daily",
        default_status="active",
        folder="90-Daily",
        body=(
            "## Daily Focus\n\n"
            "## Engineering Log\n\n"
            "## Problems Solved & Learnings\n\n"
            "## Follow-ups\n"
        ),
    ),
)

_TEMPLATES_BY_ID: dict[str, TemplateItem] = {t.id: t for t in BUILTIN_TEMPLATES}


class TemplateService:
    """Provides access to the 5 canonical built-in DevJournal note templates."""

    def list_templates(self) -> TemplatesListResponse:
        return TemplatesListResponse(templates=list(BUILTIN_TEMPLATES))

    def get_template(self, template_id: str) -> TemplateItem:
        tpl = _TEMPLATES_BY_ID.get(template_id)
        if tpl is None:
            raise InvalidInputError(
                "INVALID_TEMPLATE",
                f"Unknown template_id: {template_id!r}",
                details={"valid_templates": list(_TEMPLATES_BY_ID.keys())},
            )
        return tpl
