"""Recalculate historical metrics; this does not rerun retrieval or the model."""
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]


def check():
    report = json.loads((ROOT / "evidence/retrieval-record.json").read_text(encoding="utf-8"))
    assert len(report["rows"]) == 144
    results = {}
    for method, recorded in report["summary"].items():
        rows = [r for r in report["rows"] if r["method"] == method]
        assert len(rows) == len({r["id"] for r in rows}) == 24
        supported = [r for r in rows if r["required"]]
        actual = {
            "cases": len(rows), "supported_cases": len(supported),
            "all_required_found_cases": sum(r["required"] == r["recovered"] for r in supported),
            "required_groups": sum(r["required"] for r in rows),
            "recovered_groups": sum(r["recovered"] for r in rows),
            "wrong_scope_cases": sum(r["wrong_scope"] for r in rows),
            "forbidden_attachment_cases": sum(r["forbidden_attachment"] for r in rows),
            "mean_citations_supported": round(statistics.mean(r["citation_count"] for r in supported), 2),
            "median_ms_warm": round(statistics.median(r["seconds"] for r in rows) * 1000, 2),
            "original_validation_failures": sum(not r["valid_originals"] for r in rows),
        }
        for key, value in actual.items():
            assert recorded[key] == value, (method, key, recorded[key], value)
        assert sum(r["required"] == 0 for r in rows) == recorded["negative_cases"] == 6
        results[method] = f'{actual["all_required_found_cases"]}/{actual["supported_cases"]}'
    for shot in json.loads((ROOT / "evidence/screenshots.json").read_text(encoding="utf-8")):
        assert hashlib.sha256((ROOT / shot["file"]).read_bytes()).hexdigest() == shot["sha256"]
    return results


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, indent=2))
