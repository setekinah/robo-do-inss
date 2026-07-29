"""Motor simples de triagem baseado em arvores de decisao."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TriageState:
    flow_id: str
    current_node_id: str | None
    history: list[dict[str, str]]
    result_key: str | None = None


def create_state(flow_id: str, flow: dict[str, Any]) -> TriageState:
    return TriageState(flow_id=flow_id, current_node_id=flow["start"], history=[])


def get_current_node(state: TriageState, flow: dict[str, Any]) -> dict[str, Any] | None:
    if state.current_node_id is None:
        return None
    return flow["nodes"][state.current_node_id]


def answer_current_question(
    state: TriageState, flow: dict[str, Any], option_label: str
) -> tuple[TriageState, dict[str, Any] | None]:
    node = get_current_node(state, flow)
    if node is None:
        return state, get_result(state, flow)

    selected = next(option for option in node["options"] if option["label"] == option_label)
    new_history = [
        *state.history,
        {
            "node_id": node["id"],
            "node_code": node["code"],
            "question": node["title"],
            "answer": selected["label"],
        },
    ]

    if "next" in selected:
        return (
            TriageState(
                flow_id=state.flow_id,
                current_node_id=selected["next"],
                history=new_history,
                result_key=None,
            ),
            None,
        )

    return (
        TriageState(
            flow_id=state.flow_id,
            current_node_id=None,
            history=new_history,
            result_key=selected["result"],
        ),
        flow["results"][selected["result"]],
    )


def step_back(state: TriageState, flow: dict[str, Any]) -> TriageState:
    if not state.history:
        return create_state(state.flow_id, flow)

    last_answer = state.history[-1]
    return TriageState(
        flow_id=state.flow_id,
        current_node_id=last_answer["node_id"],
        history=state.history[:-1],
        result_key=None,
    )


def get_result(state: TriageState, flow: dict[str, Any]) -> dict[str, Any] | None:
    if not state.result_key:
        return None
    return flow["results"][state.result_key]
