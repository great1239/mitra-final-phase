from __future__ import annotations

import re
from typing import Any

from .interaction import build_capability_understanding


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", value.lower())
        if token
        not in {
            "and",
            "for",
            "the",
            "with",
            "that",
            "this",
            "from",
            "into",
            "show",
            "please",
        }
    }


def _schema_fields(schema: dict[str, Any]) -> set[str]:
    properties = schema.get("properties") or {}
    return set(properties) | set(schema.get("required") or [])


def _candidate_text(candidate: dict[str, Any]) -> str:
    metadata = candidate.get("capability_metadata") or {}
    intent_metadata = candidate.get("metadata") or {}
    return " ".join(
        str(item)
        for item in (
            candidate.get("product_id"),
            candidate.get("product_name"),
            candidate.get("capability_id"),
            candidate.get("capability_description"),
            candidate.get("intent_id"),
            candidate.get("description"),
            metadata,
            intent_metadata,
            " ".join(_schema_fields(candidate.get("input_schema") or {})),
        )
        if item
    )


class CapabilityGraphPlanner:
    """Builds dynamic capability graph views from published manifests."""

    def __init__(self, candidates: list[dict[str, Any]]):
        self.candidates = candidates

    def graph(self, *, message: str | None = None) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        product_ids: set[str] = set()
        capability_keys: set[tuple[str, str]] = set()
        message_tokens = _tokens(message or "")

        for candidate in self.candidates:
            product_id = candidate["product_id"]
            capability_id = candidate["capability_id"]
            intent_id = candidate["intent_id"]
            if product_id not in product_ids:
                product_ids.add(product_id)
                nodes.append(
                    {
                        "id": f"product:{product_id}",
                        "kind": "product",
                        "product_id": product_id,
                        "display_name": candidate.get("product_name"),
                        "attachment_state": candidate.get(
                            "attachment_state"
                        ),
                    }
                )
            capability_key = (product_id, capability_id)
            if capability_key not in capability_keys:
                capability_keys.add(capability_key)
                understanding = build_capability_understanding(candidate)
                nodes.append(
                    {
                        "id": f"capability:{product_id}:{capability_id}",
                        "kind": "capability",
                        "product_id": product_id,
                        "capability_id": capability_id,
                        "description": candidate.get(
                            "capability_description"
                        ),
                        "understanding": understanding,
                        "dynamic_tags": sorted(
                            _tokens(_candidate_text(candidate))
                        )[:20],
                    }
                )
                edges.append(
                    {
                        "from": f"product:{product_id}",
                        "to": f"capability:{product_id}:{capability_id}",
                        "relationship": "publishes",
                    }
                )
            intent_node = f"intent:{product_id}:{capability_id}:{intent_id}"
            fit_tokens = _tokens(_candidate_text(candidate))
            nodes.append(
                {
                    "id": intent_node,
                    "kind": "intent",
                    "product_id": product_id,
                    "capability_id": capability_id,
                    "intent_id": intent_id,
                    "description": candidate.get("description"),
                    "required_inputs": sorted(
                        _schema_fields(candidate.get("input_schema") or {})
                    ),
                    "message_overlap": sorted(message_tokens & fit_tokens),
                }
            )
            edges.append(
                {
                    "from": f"capability:{product_id}:{capability_id}",
                    "to": intent_node,
                    "relationship": "exposes-intent",
                }
            )

        self._add_composition_edges(nodes, edges)
        return {
            "graph_type": "published-manifest-capability-graph",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

    def plan(self, *, message: str, max_steps: int = 5) -> dict[str, Any]:
        message_tokens = _tokens(message)
        ranked: list[dict[str, Any]] = []
        for candidate in self.candidates:
            candidate_tokens = _tokens(_candidate_text(candidate))
            overlap = sorted(message_tokens & candidate_tokens)
            schema_fields = _schema_fields(candidate.get("input_schema") or {})
            field_overlap = sorted(message_tokens & schema_fields)
            score = len(overlap) + (len(field_overlap) * 2)
            if score == 0:
                continue
            ranked.append(
                {
                    "candidate": candidate,
                    "score": score,
                    "overlap": overlap,
                    "field_overlap": field_overlap,
                }
            )
        ranked.sort(
            key=lambda item: (
                item["score"],
                item["candidate"]["product_id"],
                item["candidate"]["capability_id"],
                item["candidate"]["intent_id"],
            ),
            reverse=True,
        )
        selected = ranked[:max_steps]
        steps = []
        for index, item in enumerate(selected, start=1):
            candidate = item["candidate"]
            steps.append(
                {
                    "step": index,
                    "product_id": candidate["product_id"],
                    "capability_id": candidate["capability_id"],
                    "intent_id": candidate["intent_id"],
                    "reason": "published metadata matched requested terms",
                    "matched_terms": item["overlap"],
                    "required_inputs": sorted(
                        _schema_fields(candidate.get("input_schema") or {})
                    ),
                    "execution_mode": "planned",
                }
            )
        unique_capabilities = {
            (step["product_id"], step["capability_id"]) for step in steps
        }
        return {
            "plan_type": (
                "multi_capability_candidate_plan"
                if len(unique_capabilities) > 1
                else "single_capability_candidate_plan"
                if steps
                else "no_matching_capability_plan"
            ),
            "composition_status": (
                "planned_not_auto_executed" if len(steps) > 1 else "simple"
            ),
            "message_terms": sorted(message_tokens),
            "step_count": len(steps),
            "steps": steps,
            "boundary": (
                "Mitra can plan across published capabilities. It executes "
                "only explicit dispatches and leaves product logic external."
            ),
        }

    @staticmethod
    def _add_composition_edges(
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> None:
        intent_nodes = [node for node in nodes if node["kind"] == "intent"]
        for source in intent_nodes:
            source_fields = set(source.get("required_inputs") or [])
            for target in intent_nodes:
                if source["id"] == target["id"]:
                    continue
                target_fields = set(target.get("required_inputs") or [])
                shared = sorted(source_fields & target_fields)
                if not shared:
                    continue
                edges.append(
                    {
                        "from": source["id"],
                        "to": target["id"],
                        "relationship": "composable-by-shared-input",
                        "shared_inputs": shared,
                    }
                )
