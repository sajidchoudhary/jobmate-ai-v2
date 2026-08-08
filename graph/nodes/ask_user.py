# Human-in-the-loop confirmation before opening URLs. Uses interrupt() to pause the graph
# and wait for a Command(resume=...) from the caller — this is real (not placeholder) plumbing
# since the pause/resume behavior is structural, but it does not yet interpret the response.
import logging

from langgraph.types import interrupt

from graph.state import GraphState

logger = logging.getLogger(__name__)


def ask_user(state: GraphState) -> GraphState:
    logger.info("ask_user: pausing for confirmation before opening URLs")
    interrupt({"question": "Open these job URLs?"})
    logger.info("ask_user: resumed")
    return state
