"""Enforce the HA quality rule's >95% line coverage for every source module."""
import json
from pathlib import Path

report = json.loads(Path("coverage.json").read_text())
failures = [name for name, data in report["files"].items()
            if "custom_components/pet_feeder_local/" in name
            and data["summary"]["percent_covered"] <= 95]
if failures:
    raise SystemExit("Insufficient module coverage: " + ", ".join(failures))
print("Every integration module exceeds 95% line coverage")
