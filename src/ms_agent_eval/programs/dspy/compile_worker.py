from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import dspy

from .engine import create_program, load_state_json, save_state_json


def main() -> int:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise TypeError("compile request must be a JSON object")
    train_payload = payload.get("train")
    development_payload = payload.get("development")
    if not isinstance(train_payload, list) or not isinstance(development_payload, list):
        raise TypeError("compile request must contain train and development arrays")
    with tempfile.TemporaryDirectory() as directory:
        base_path = Path(directory) / "base.json"
        base_path.write_text(
            json.dumps(payload["base_state"], ensure_ascii=False), encoding="utf-8"
        )
        base = create_program()
        load_state_json(base, base_path)
        train = [
            dspy.Example(**item).with_inputs(
                "global_context", "instruction_context", "task"
            )
            for item in train_payload
        ]
        k = payload.get("k")
        if not isinstance(k, int) or isinstance(k, bool) or k < 1:
            raise ValueError("k must be a positive integer")
        compiled = dspy.LabeledFewShot(k=k).compile(base, trainset=train)
        state_path = Path(directory) / "compiled.json"
        state = save_state_json(compiled, state_path)
    json.dump(
        {
            "schema_version": 1,
            "worker_pid": os.getpid(),
            "development_case_count": len(development_payload),
            "compiled_state": state,
        },
        sys.stdout,
        ensure_ascii=False,
        sort_keys=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
