"""Pipeline agents for content processing."""
from pipeline.agents.editor_agent import EditorAgent, EditResult, EditChange
from pipeline.agents.conciseness_agent import ConcisenessAgent, ConcisenessResult

__all__ = [
    "EditorAgent",
    "EditResult",
    "EditChange",
    "ConcisenessAgent",
    "ConcisenessResult",
]
