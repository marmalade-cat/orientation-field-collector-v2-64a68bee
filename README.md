OrientationFieldCollectorV2

A compact prototype tool for collecting and validating per-module pose/time-series datasets for modular tensegrity experiments.

What it contains
- JSON schema (in-code) and CSV conventions for timestamps (ISO8601), module_id, position (x,y,z), quaternion (qx,qy,qz,qw). Euler allowed if explicitly labeled with convention.
- main.py: converter CSV<->JSON, validator, merger (time-align nearest), diagnostics (coverage, missing-data heatmap text, velocities, angular velocities), example synthetic data, and basic tests. No dependencies.

Quick start
- Run: python3 main.py --help
- Convert CSV to JSON: python3 main.py convert --in examples/synthetic.csv --out out.json
- Validate: python3 main.py validate --in out.json
- Merge: python3 main.py merge --in examples/mod1.csv examples/mod2.csv --out merged.json
- Run tests: python3 main.py test

Data-sharing language (suggested)
Please consider sharing module-level pose time-series in either CSV (columns below) or the JSON schema used in this project. Provide anonymized module IDs and a short metadata object describing coordinate frame, sensor latency, and quaternion convention. Example citation line: "OrientationFieldCollectorV2 synthetic dataset (2026), Marmalade Lab. DOI/URL if provided." 

CSV column conventions
- timestamp: ISO8601 UTC (e.g. 2026-11-05T12:34:56.789Z)
- module_id: string
- x,y,z: floats in meters
- qx,qy,qz,qw: quaternion components (unit expected)
- optional: confidence (0-1), frame: coordinate frame label

License: MIT (simple prototype).