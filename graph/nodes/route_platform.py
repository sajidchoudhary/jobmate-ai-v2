# Placeholder — will pick the target platform (only "naukri" in phase 1).
import logging

from graph.state import GraphState

logger = logging.getLogger(__name__)


def route_platform(state: GraphState) -> GraphState:
    logger.info("route_platform")
    return state
