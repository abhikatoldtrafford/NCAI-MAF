import json
import ast
from typing import Dict, Any


def jsonify_output(response: Any) -> Dict[str, Any]:
    # Load outer (JSON string or Python literal) into a dict
    if isinstance(response, str):
        try:
            resp = json.loads(response)
        except json.JSONDecodeError:
            resp = ast.literal_eval(response)
    else:
        resp = response

    metadata_keys = ("request_id", "conversation_id", "workflow", "status", "error", "data")
    final: Dict[str, Any] = {k: resp[k] for k in metadata_keys if k in resp and resp[k] is not None}

    # Determine inner payload
    if "response" in resp and resp["response"] is not None:
        inner = resp["response"]
    else:
        inner = {k: v for k, v in resp.items() if k not in metadata_keys}

    if isinstance(inner, str):
        try:
            inner = ast.literal_eval(inner)
        except Exception:
            inner = json.loads(inner)

    # Parse nested query_result if present
    if isinstance(inner, dict):
        nq = inner.get("news_query_response")
        if isinstance(nq, dict):
            qr = nq.get("query_result")
            if isinstance(qr, str):
                try:
                    nq["query_result"] = json.loads(qr)
                except json.JSONDecodeError:
                    nq["query_result"] = ast.literal_eval(qr)

    final["response"] = inner
    final["data"] = inner

    return final
