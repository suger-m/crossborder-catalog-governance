from __future__ import annotations

from typing import Any

from camel.agents import ChatAgent
from camel.messages import BaseMessage
from .toolkits import (
    CatalogToolkit,
    ComplianceToolkit,
    GovernanceToolkit,
    ListingToolkit,
    ProjectContextToolkit,
)
from .prompts import BUSINESS_AGENT_PROMPT


PROJECT_TOOLS = {
    "catalog_steward_agent": ("list_project_resources", "inspect_task_materials"),
    "compliance_specialist_agent": (
        "list_project_resources", "summarize_canonical_products", "list_pending_approvals",
    ),
    "listing_operations_agent": ("list_project_resources", "summarize_canonical_products"),
    "governance_reviewer_agent": (
        "list_project_resources", "summarize_canonical_products", "summarize_listing_drafts",
        "read_artifact_text", "list_pending_approvals",
    ),
}

DOMAIN_TOOLKITS = {
    "catalog_steward_agent": CatalogToolkit,
    "compliance_specialist_agent": ComplianceToolkit,
    "listing_operations_agent": ListingToolkit,
    "governance_reviewer_agent": GovernanceToolkit,
}


def create_business_agent(app: Any, platform_task_id: str, business: Any) -> ChatAgent:
    del platform_task_id
    metadata = app.workers.get(business.name).metadata
    skill_toolkit = app.skills.toolkit(business.name, metadata.get("skills") or [])
    tools = list(skill_toolkit.get_tools())
    tools.extend(ProjectContextToolkit(app, business.name).get_tools(PROJECT_TOOLS[business.name]))
    tools.extend(DOMAIN_TOOLKITS[business.name](app, business.name).get_tools())
    return ChatAgent(
        system_message=BaseMessage.make_assistant_message(
            role_name=business.name,
            content=BUSINESS_AGENT_PROMPT.format(
                role_name=business.name, role_description=business.description,
            ),
        ),
        model=app.model_runtime.camel_model("worker"),
        tools=tools,
        agent_id=business.name,
        max_iteration=12,
        tool_execution_timeout=300,
    )
