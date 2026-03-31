#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


REQUIRED_SIGNAL_FIELDS = ("id", "deficiency_class", "surface", "description")


def fail(message: str, code: int = 1) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(code)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Extract RDD structural signals from triage chain records.")
    ap.add_argument("chain_path", help="Path to JSONL decision chain")
    ap.add_argument(
        "--out",
        default="out/rdd/signal-index.json",
        help="Output JSON path (default: out/rdd/signal-index.json)",
    )
    return ap.parse_args()


def derive_case_ref(record: dict, line_no: int) -> str:
    originating = record.get("originating_pass_hash")
    if isinstance(originating, str) and originating:
        return originating
    record_hash = record.get("record_hash")
    if isinstance(record_hash, str) and record_hash:
        return record_hash
    fail(
        f"line {line_no}: triage_decision missing case_ref source (originating_pass_hash or record_hash)",
        code=1,
    )


def extract_signals(chain_path: Path) -> list[dict]:
    if not chain_path.exists():
        fail(f"chain path not found: {chain_path}")

    signals: list[dict] = []
    with chain_path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception:
                fail(f"line {line_no}: invalid JSON")

            if record.get("record_type") != "triage_decision":
                continue

            structural_signals = record.get("structural_signals")
            if structural_signals is None:
                continue
            if not isinstance(structural_signals, list):
                fail(f"line {line_no}: structural_signals must be an array")

            case_ref = derive_case_ref(record, line_no)
            for idx, signal in enumerate(structural_signals, start=1):
                if not isinstance(signal, dict):
                    fail(f"line {line_no}: structural_signals[{idx}] must be an object")
                for field in REQUIRED_SIGNAL_FIELDS:
                    value = signal.get(field)
                    if not isinstance(value, str) or not value:
                        fail(
                            f"line {line_no}: structural_signals[{idx}] missing required field '{field}'"
                        )
                signals.append(
                    {
                        "signal_id": signal["id"],
                        "deficiency_class": signal["deficiency_class"],
                        "surface": signal["surface"],
                        "description": signal["description"],
                        "case_ref": case_ref,
                    }
                )

    signals.sort(
        key=lambda item: (
            item["signal_id"],
            item["deficiency_class"],
            item["surface"],
            item["description"],
            item["case_ref"],
        )
    )
    return signals


def write_output(out_path: Path, signals: list[dict]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"signal_index_version": "rdd_signal_index.v1", "signals": signals}
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    out_path.write_text(encoded, encoding="utf-8")


def main() -> None:
    args = parse_args()
    chain_path = Path(args.chain_path)
    out_path = Path(args.out)

    signals = extract_signals(chain_path)
    write_output(out_path, signals)
    print(f"PASS: extracted {len(signals)} structural signals -> {out_path}")


if __name__ == "__main__":
    main()
