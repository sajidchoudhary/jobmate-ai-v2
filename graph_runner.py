# Thin, UI-agnostic wrapper: graph invocation, thread_id management, result extraction.
import logging
import uuid

from graph.graph_builder import build_graph
from graph.state import GraphState

logger = logging.getLogger(__name__)

_graph = build_graph()


def new_thread_id() -> str:
    return str(uuid.uuid4())


def run_query(query: str, thread_id: str) -> GraphState:
    logger.info("graph_runner.run_query: thread_id=%s query=%r", thread_id, query)
    config = {"configurable": {"thread_id": thread_id}}
    try:
        return _graph.invoke({"query": query}, config=config)
    except Exception as exc:
        logger.error("graph_runner: invoke failed: %s", exc)
        return {
            "intent": None,
            "filtered_jobs": [],
            "status": {"stage": "graph_runner_failed", "errors": [str(exc)]},
        }
