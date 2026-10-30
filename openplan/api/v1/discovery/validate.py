"""Validate publisher metadata without contacting Azure."""

import argparse
from pathlib import Path
import sys

from pydantic import ValidationError

from openplan.api.v1.discovery.models import DatasetIndex, DatasetManifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("index", "manifest"))
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    model = DatasetIndex if args.kind == "index" else DatasetManifest
    try:
        model.model_validate_json(args.path.read_bytes())
    except (OSError, ValidationError) as exc:
        print(f"Invalid {args.kind}: {exc}", file=sys.stderr)
        return 1
    print(f"Valid {args.kind}: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
