from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
MASTERDB = ROOT / "masterdb" / "balbharti" / "sample_ingestion_dataset.json"
PROOF_DIR = ROOT / "review_packets" / "proof_logs"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from governance.constitutional_runtime import ConstitutionalCognitionRuntime
from learning_runtime.learning_intelligence import build_learning_intelligence
from backend.retrieval.retrieval_engine import retrieve_from_masterdb
from memory.constitutional_semantic_memory import stable_hash, utc_now_iso


SCHEMA_VERSION = "UNIGURU_RUNTIME_RESPONSE_CONTRACT_V1"


class RuntimeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    grade: Optional[int] = Field(default=None, ge=1, le=10)
    medium: Optional[str] = None
    subject: Optional[str] = None
    emit_proof: bool = True


app = FastAPI(
    title="UniGuru Unified Constitutional Runtime",
    version="1.0.0",
    description="Canonical query-to-governance runtime contract for UniGuru.",
)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9]+", str(text or "").lower()))


def _load_masterdb() -> List[Dict[str, Any]]:
    if not MASTERDB.exists():
        return []
    loaded = json.loads(MASTERDB.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, list) else []


def _retrieve(query: str, request: RuntimeRequest) -> Dict[str, Any]:
    return retrieve_from_masterdb(
        query=query,
        grade=request.grade,
        medium=request.medium,
        subject=request.subject,
    )


def _interpret(query: str, retrieval: Dict[str, Any]) -> Dict[str, Any]:
    record = retrieval.get("best_record") or {}
    if not record:
        interpretation = {
            "claim_key": "unmatched_curriculum_query",
            "concept_id": "masterdb_unmatched",
            "summary": "No governed MasterDB curriculum record matched the query.",
            "answer": "I do not have a verified Balbharti curriculum record for this query yet.",
            "uncertainty": 0.78,
            "verification_status": "UNVERIFIED",
        }
    else:
        examples = record.get("examples") or []
        questions = record.get("questions") or []
        related_concepts = [related.get("concept") for related in retrieval.get("related_records", []) if related.get("concept")]
        answer_parts = [
            f"{record.get('concept')}: {record.get('definition')}",
            f"Example: {examples[0]}" if examples else "",
            f"Practice: {questions[0]}" if questions else "",
        ]
        interpretation = {
            "claim_key": str(record.get("concept") or "curriculum_concept").lower().replace(" ", "_"),
            "concept_id": str(record.get("record_id")),
            "summary": f"{record.get('medium')} Grade {record.get('grade')} {record.get('subject')} concept.",
            "answer": " ".join(part for part in answer_parts if part),
            "related_concepts": related_concepts,
            "uncertainty": round(1.0 - float(retrieval.get("confidence") or 0.0), 4),
            "verification_status": "PARTIAL_VERIFIED_SAMPLE"
            if (record.get("source_lineage") or {}).get("provenance_status") == "sample_seed"
            else "VERIFIED",
        }
    interpretation["interpretation_hash"] = stable_hash(interpretation)
    return interpretation


def _govern(query: str, retrieval: Dict[str, Any], interpretation: Dict[str, Any]) -> Dict[str, Any]:
    confidence = float(retrieval.get("confidence") or 0.0)
    contradiction_pressure = 0.0 if retrieval.get("best_record") else 0.35
    semantic_event = {
        "trace_id": stable_hash({"query": query})[:16],
        "claim_key": interpretation["claim_key"],
        "confidence": confidence,
        "provenance_weight": 0.42 if retrieval.get("best_record") else 0.0,
        "legitimacy_evidence": 0.34 if retrieval.get("best_record") else 0.0,
        "reinforcement_count": len(retrieval.get("matches") or []),
        "contradiction_pressure": contradiction_pressure,
        "uncertainty": interpretation["uncertainty"],
        "ambiguity_class": "sample_seed_requires_review"
        if interpretation["verification_status"] == "PARTIAL_VERIFIED_SAMPLE"
        else "unmatched_or_unverified",
        "unresolved": interpretation["verification_status"] != "VERIFIED",
    }
    previous_snapshot = {
        "snapshot_version": 1,
        "concepts": [
            {
                "concept_id": "masterdb_curriculum",
                "canonical_name": "MasterDB Curriculum",
                "parent_id": None,
                "truth_level": 3,
                "domain": "curriculum",
                "immutable": False,
            }
        ],
    }
    current_snapshot = previous_snapshot
    ontology_boundaries = {
        interpretation["claim_key"]: {"legitimacy_ceiling": 0.42, "ontology_violation_count": 0},
        "default": {"legitimacy_ceiling": 0.32, "ontology_violation_count": 0},
    }
    disputes = []
    if contradiction_pressure:
        disputes.append(
            {
                "claim_key": interpretation["claim_key"],
                "signal_ids": ["masterdb_lookup", "runtime_boundary"],
                "polarities": ["unmatched", "requires_verified_curriculum"],
                "contradiction_pressure": contradiction_pressure,
            }
        )
    runtime = ConstitutionalCognitionRuntime.execute(
        previous_snapshot=previous_snapshot,
        current_snapshot=current_snapshot,
        semantic_events=[semantic_event],
        ontology_boundaries=ontology_boundaries,
        disputes=disputes,
        arbitrators=[{"node_id": "isha_runtime"}, {"node_id": "vijay_replay"}],
        prior_unresolved={},
        claims=[
            {
                "claim_key": interpretation["claim_key"],
                "concept_id": "masterdb_curriculum",
                "requested_legitimacy": confidence,
                "uncertainty": interpretation["uncertainty"],
                "contradiction_pressure": contradiction_pressure,
            }
        ],
    )
    return {"semantic_event": semantic_event, "runtime": runtime}


def _build_learning_state(query: str, retrieval: Dict[str, Any], interpretation: Dict[str, Any]) -> Dict[str, Any]:
    return build_learning_intelligence(query, retrieval)


def execute_runtime(request: RuntimeRequest) -> Dict[str, Any]:
    query = request.query.strip()
    retrieval = _retrieve(query, request)
    interpretation = _interpret(query, retrieval)
    learning_state = _build_learning_state(query, retrieval, interpretation)
    governed = _govern(query, retrieval, interpretation)
    runtime_trace = governed["runtime"]["runtime_trace"]
    components = governed["runtime"]["components"]
    observability = components["observability"]["semantic_pressure_observability"]
    trust_rows = components["trust_propagation"]["authority_pressure_logs"]
    contradiction = components["contradiction_escalation"]
    ontology = components["ontology_lineage"]

    trace_id = governed["semantic_event"]["trace_id"]
    payload = {
        "response_payload": {
            "answer": interpretation["answer"],
            "matched_record": retrieval.get("best_record"),
            "retrieval_confidence": retrieval["confidence"],
            "source_lineage": (retrieval.get("best_record") or {}).get("source_lineage"),
            "curriculum_mapping": {
                "matched_record_id": (retrieval.get("best_record") or {}).get("record_id"),
                "curriculum_version": (retrieval.get("best_record") or {}).get("curriculum_version"),
                "version": (retrieval.get("best_record") or {}).get("version"),
                "provenance_status": ((retrieval.get("best_record") or {}).get("source_lineage") or {}).get("provenance_status"),
                "chapter_recommendations": retrieval.get("chapter_recommendations"),
                "learning_objectives": retrieval.get("learning_objectives"),
            },
            "learning_state": learning_state,
        },
        "trust_state": {
            "trust_score": trust_rows[0]["trust_ceiling"] if trust_rows else 0.0,
            "authority_pressure_score": trust_rows[0]["authority_pressure_score"] if trust_rows else 0.0,
            "governance_response": trust_rows[0]["governance_response"] if trust_rows else "NO_TRUST_SIGNAL",
        },
        "uncertainty_state": {
            "score": interpretation["uncertainty"],
            "classification": governed["semantic_event"]["ambiguity_class"],
            "preserved": True,
        },
        "contradiction_state": {
            "unresolved_count": len(contradiction.get("unresolved_contradiction_persistence") or []),
            "silent_merge_allowed": contradiction.get("silent_merge_allowed"),
            "arbitration_hash": contradiction.get("arbitration_hash"),
        },
        "ontology_boundary_state": {
            "alert_count": len(ontology.get("semantic_drift_alerts") or []),
            "boundary_state_hash": ontology.get("boundary_state_hash"),
            "canonical_authority_granted": False,
        },
        "constitutional_reasoning_summary": {
            "flow": [
                "query",
                "masterdb_lookup",
                "semantic_interpretation",
                "constitutional_evaluation",
                "trust_contradiction_ontology_evaluation",
                "bounded_response_generation",
                "explanation_layer",
                "replay_artifact_emission",
            ],
            "verification_status": interpretation["verification_status"],
            "observability_state": observability.get("governance_state"),
            "canonical_authority_granted": False,
        },
        "trace_id": trace_id,
        "runtime_hash": runtime_trace["runtime_hash"],
        "schema_version": SCHEMA_VERSION,
    }
    payload["contract_hash"] = stable_hash(payload)
    if request.emit_proof:
        PROOF_DIR.mkdir(parents=True, exist_ok=True)
        proof_path = PROOF_DIR / f"uniguru_runtime_execution_{trace_id}.json"
        proof_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True), encoding="utf-8")
        latest_path = PROOF_DIR / "uniguru_runtime_execution_latest.json"
        latest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True), encoding="utf-8")
    return payload


@app.post("/runtime/execute")
def runtime_execute(request: RuntimeRequest) -> Dict[str, Any]:
    return execute_runtime(request)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the UniGuru unified constitutional runtime.")
    parser.add_argument("query", nargs="?", default="What is a balanced diet in Class 6 Science?")
    parser.add_argument("--grade", type=int, default=None)
    parser.add_argument("--medium", default=None)
    parser.add_argument("--subject", default=None)
    parser.add_argument("--no-proof", action="store_true")
    args = parser.parse_args()
    payload = execute_runtime(
        RuntimeRequest(
            query=args.query,
            grade=args.grade,
            medium=args.medium,
            subject=args.subject,
            emit_proof=not args.no_proof,
        )
    )
    print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
