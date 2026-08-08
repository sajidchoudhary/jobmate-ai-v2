# Entry point. Decides "search" vs "open_urls" from the query + existing state.
import logging

from graph.state import GraphState

logger = logging.getLogger(__name__)


def classify_intent(state: GraphState) -> GraphState:
    logger.info("classify_intent")
    query = state.get("query", "")
    has_prior_results = bool(state.get("filtered_jobs"))
    intent = "open_urls" if "open" in query.lower() and has_prior_results else "search"
    logger.info("classify_intent: query=%r has_prior_results=%s -> intent=%r", query, has_prior_results, intent)
    return {**state, "intent": intent}
