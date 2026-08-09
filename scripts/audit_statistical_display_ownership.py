from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GEOGRAPHY_DIR = ROOT / "data" / "processed" / "geographies"
AUDIT_DIR = ROOT / "data" / "processed" / "audits"
MANUAL_DIR = ROOT / "data" / "manual"

RESULT_AGGREGATE_PATH = (
    GEOGRAPHY_DIR / "statistical_area_result_aggregates.metadata.csv"
)
POLLING_DISPLAY_PATH = (
    GEOGRAPHY_DIR / "statistical_area_polling_group_displays.metadata.csv"
)
MANUAL_DISPLAY_GROUP_PATH = MANUAL_DIR / "statistical_area_display_groups.csv"

OUTPUT_PATH = AUDIT_DIR / "statistical_display_component_ownership.csv"
SUMMARY_PATH = AUDIT_DIR / "statistical_display_component_ownership_summary.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def split_pipe(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split("|") if part.strip()]


def claims_from_rows(
    rows: list[dict[str, str]], source_name: str
) -> list[dict[str, str]]:
    claims: list[dict[str, str]] = []
    for row in rows:
        owner_id = str(row.get("display_geography_id") or "").strip()
        elections = split_pipe(row.get("elections") or row.get("election"))
        component_ids = split_pipe(row.get("component_stat_area_ids"))
        component_ids.extend(split_pipe(row.get("component_stat_area_id")))
        if not owner_id or not elections or not component_ids:
            raise ValueError(f"Invalid {source_name} display ownership row: {row}")
        for election in elections:
            for component_id in dict.fromkeys(component_ids):
                claims.append(
                    {
                        "election": election,
                        "stat_area_id": component_id,
                        "display_geography_id": owner_id,
                        "ownership_source": source_name,
                    }
                )
    return claims


def main() -> None:
    claims = [
        *claims_from_rows(read_csv(RESULT_AGGREGATE_PATH), "result_aggregate"),
        *claims_from_rows(read_csv(POLLING_DISPLAY_PATH), "polling_group_display"),
        *claims_from_rows(read_csv(MANUAL_DISPLAY_GROUP_PATH), "manual_display_group"),
    ]
    owners_by_component: dict[tuple[str, str], set[str]] = defaultdict(set)
    for claim in claims:
        owners_by_component[(claim["election"], claim["stat_area_id"])].add(
            claim["display_geography_id"]
        )

    output_rows: list[dict[str, Any]] = []
    for claim in claims:
        owners = sorted(
            owners_by_component[(claim["election"], claim["stat_area_id"])]
        )
        output_rows.append(
            {
                **claim,
                "owner_count": len(owners),
                "ownership_status": "unique" if len(owners) == 1 else "conflict",
                "all_display_owners": "|".join(owners),
            }
        )
    output_rows.sort(
        key=lambda row: (
            int(str(row["election"])[1:]),
            row["stat_area_id"],
            row["display_geography_id"],
        )
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    conflicting_components = {
        key: owners for key, owners in owners_by_component.items() if len(owners) > 1
    }
    summary = {
        "definition": (
            "Every statistical-area polygon may be owned by at most one result "
            "aggregate or polling-group display in an election."
        ),
        "claim_rows": len(output_rows),
        "unique_area_election_components": len(owners_by_component),
        "conflicting_area_election_components": len(conflicting_components),
        "claims_by_source": dict(
            sorted(Counter(row["ownership_source"] for row in output_rows).items())
        ),
        "conflicts_by_election": dict(
            sorted(Counter(election for election, _ in conflicting_components).items())
        ),
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if conflicting_components:
        examples = ", ".join(
            f"{election}/{area_id}"
            for election, area_id in sorted(conflicting_components)[:10]
        )
        raise SystemExit(f"Statistical display ownership conflicts remain: {examples}")


if __name__ == "__main__":
    main()
