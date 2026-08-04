from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polling_group_ownership import solve_polling_group_ownership


CONNECTED_STATUS = "connected_solution"
USABLE_STATUSES = {
    CONNECTED_STATUS,
    "solution_requires_disconnected_geometry",
}


@dataclass(frozen=True)
class PartitionUnit:
    group_ids: tuple[str, ...]
    area_ids: tuple[str, ...]
    score: float
    exact: bool
    precision_by_model: dict[str, float]
    recall_by_model: dict[str, float]


def _positive_weights(group: dict[str, Any]) -> dict[str, float]:
    return {
        str(area_id): float(value)
        for area_id, value in group["weights"].items()
        if float(value) > 0
    }


def _cluster_id(group_ids: set[str]) -> str:
    return "+".join(sorted(group_ids))


def _cluster_inputs(
    clusters: list[set[str]], groups: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for group_ids in clusters:
        weights: dict[str, float] = {}
        for group_id in group_ids:
            for area_id, value in _positive_weights(groups[group_id]).items():
                weights[area_id] = weights.get(area_id, 0.0) + value
        output[_cluster_id(group_ids)] = {
            "area_ids": set(weights),
            "weights": weights,
            "planned": round(sum(weights.values())),
        }
    return output


def _edge_models(
    groups: dict[str, dict[str, Any]],
) -> dict[str, dict[tuple[str, str], float]]:
    models = {"planned": {}, "final_actual": {}, "final_eligible": {}}
    for group_id, group in groups.items():
        weights = _positive_weights(group)
        total = sum(weights.values())
        if total <= 0:
            continue
        actual = float(group.get("actual_voters", 0) or 0)
        eligible = float(group.get("final_eligible", 0) or 0)
        for area_id, weight in weights.items():
            key = (group_id, area_id)
            models["planned"][key] = weight
            models["final_actual"][key] = actual * weight / total
            models["final_eligible"][key] = eligible * weight / total
    return models


def _evaluate(
    clusters: list[set[str]],
    ownership: dict[str, tuple[str, ...]],
    groups: dict[str, dict[str, Any]],
) -> list[PartitionUnit]:
    models = _edge_models(groups)
    units: list[PartitionUnit] = []
    all_group_ids = set(groups)
    for group_ids in clusters:
        cluster_id = _cluster_id(group_ids)
        area_ids = set(ownership[cluster_id])
        precision_by_model: dict[str, float] = {}
        recall_by_model: dict[str, float] = {}
        crossing_weight = 0.0
        for model_name, edges in models.items():
            internal = sum(
                value
                for (group_id, area_id), value in edges.items()
                if group_id in group_ids and area_id in area_ids
            )
            group_total = sum(
                value
                for (group_id, _area_id), value in edges.items()
                if group_id in group_ids
            )
            area_total = sum(
                value
                for (_group_id, area_id), value in edges.items()
                if area_id in area_ids
            )
            precision_by_model[model_name] = (
                internal / group_total if group_total else 0.0
            )
            recall_by_model[model_name] = (
                internal / area_total if area_total else 0.0
            )
            if model_name == "planned":
                crossing_weight = sum(
                    value
                    for (group_id, area_id), value in edges.items()
                    if (group_id in group_ids) != (area_id in area_ids)
                )
        score = min(
            [*precision_by_model.values(), *recall_by_model.values()]
        )
        units.append(
            PartitionUnit(
                group_ids=tuple(sorted(group_ids)),
                area_ids=tuple(sorted(area_ids)),
                score=score,
                exact=crossing_weight <= 1e-9,
                precision_by_model=precision_by_model,
                recall_by_model=recall_by_model,
            )
        )
    if set().union(*(set(unit.group_ids) for unit in units)) != all_group_ids:
        raise ValueError("Polling-group partition lost a source group")
    return sorted(units, key=lambda unit: (unit.area_ids, unit.group_ids))


def _coupling(
    left: PartitionUnit,
    right: PartitionUnit,
    edges: dict[tuple[str, str], float],
) -> float:
    left_groups = set(left.group_ids)
    right_groups = set(right.group_ids)
    left_areas = set(left.area_ids)
    right_areas = set(right.area_ids)
    return sum(
        value
        for (group_id, area_id), value in edges.items()
        if (group_id in left_groups and area_id in right_areas)
        or (group_id in right_groups and area_id in left_areas)
    )


def _candidate_overlap(
    left: set[str],
    right: set[str],
    groups: dict[str, dict[str, Any]],
) -> float:
    left_weights: dict[str, float] = {}
    right_weights: dict[str, float] = {}
    for group_id in left:
        for area_id, value in _positive_weights(groups[group_id]).items():
            left_weights[area_id] = left_weights.get(area_id, 0.0) + value
    for group_id in right:
        for area_id, value in _positive_weights(groups[group_id]).items():
            right_weights[area_id] = right_weights.get(area_id, 0.0) + value
    return sum(
        min(left_weights.get(area_id, 0.0), right_weights.get(area_id, 0.0))
        for area_id in set(left_weights) | set(right_weights)
    )


def _merge_pair(
    clusters: list[set[str]], left_index: int, right_index: int
) -> list[set[str]]:
    merged = clusters[left_index] | clusters[right_index]
    return [
        cluster
        for index, cluster in enumerate(clusters)
        if index not in {left_index, right_index}
    ] + [merged]


def _best_overlap_pair(
    clusters: list[set[str]], groups: dict[str, dict[str, Any]]
) -> tuple[int, int]:
    candidates = [
        (
            _candidate_overlap(left, right, groups),
            _cluster_id(left),
            _cluster_id(right),
            left_index,
            right_index,
        )
        for left_index, left in enumerate(clusters)
        for right_index, right in enumerate(clusters[left_index + 1 :], left_index + 1)
    ]
    _score, _left_id, _right_id, left_index, right_index = max(candidates)
    return left_index, right_index


def _best_coupled_pair(
    units: list[PartitionUnit],
    weakest: PartitionUnit | None,
    groups: dict[str, dict[str, Any]],
) -> tuple[set[str], set[str]]:
    actual_edges = _edge_models(groups)["final_actual"]
    candidates: list[tuple[float, str, str, PartitionUnit, PartitionUnit]] = []
    for left_index, left in enumerate(units):
        for right in units[left_index + 1 :]:
            if weakest is not None and left != weakest and right != weakest:
                continue
            candidates.append(
                (
                    _coupling(left, right, actual_edges),
                    _cluster_id(set(left.group_ids)),
                    _cluster_id(set(right.group_ids)),
                    left,
                    right,
                )
            )
    if not candidates:
        raise ValueError("No polling-group clusters remain to merge")
    _score, _left_id, _right_id, left, right = max(candidates)
    return set(left.group_ids), set(right.group_ids)


def solve_polling_group_partition(
    area_ids: list[str],
    groups: dict[str, dict[str, Any]],
    geometry_by_id: dict[str, Any],
    *,
    metric_crs: str,
    tolerance_meters: float,
    robust_threshold: float = 0.5,
) -> dict[str, Any]:
    """Find the most detailed mutually-majority polling-group partition.

    Planned eligible counts define edge proportions only. Final actual and
    eligible totals are projected over those proportions as separate stress
    tests; they are never treated as conserved planned totals.
    """

    if not area_ids or not groups:
        return {"status": "empty_component", "units": []}
    unknown_areas = {
        area_id
        for group in groups.values()
        for area_id in _positive_weights(group)
        if area_id not in set(area_ids)
    }
    if unknown_areas:
        raise ValueError(f"Group weights reference unknown areas: {unknown_areas}")
    if any(not _positive_weights(group) for group in groups.values()):
        return {"status": "group_without_weights", "units": []}

    clusters = [{group_id} for group_id in sorted(groups)]
    initial_units: list[PartitionUnit] = []
    initial_ownership_status = ""
    merge_steps: list[dict[str, Any]] = []

    while clusters:
        cluster_inputs = _cluster_inputs(clusters, groups)
        ownership_result = solve_polling_group_ownership(
            area_ids,
            cluster_inputs,
            geometry_by_id,
            metric_crs=metric_crs,
            tolerance_meters=tolerance_meters,
        )
        ownership_status = str(ownership_result["status"])
        if ownership_status not in USABLE_STATUSES:
            if len(clusters) == 1:
                return {
                    "status": ownership_status,
                    "units": [],
                    "initial_units": initial_units,
                    "merge_steps": merge_steps,
                }
            left_index, right_index = _best_overlap_pair(clusters, groups)
            left = set(clusters[left_index])
            right = set(clusters[right_index])
            merge_steps.append(
                {
                    "reason": ownership_status,
                    "left_group_ids": sorted(left),
                    "right_group_ids": sorted(right),
                }
            )
            clusters = _merge_pair(clusters, left_index, right_index)
            continue

        units = _evaluate(
            clusters,
            ownership_result["ownership"],
            groups,
        )
        if not initial_units:
            initial_units = units
            initial_ownership_status = ownership_status
        minimum_score = min(unit.score for unit in units)
        if len(units) == 1:
            return {
                "status": "exact_component",
                "units": units,
                "initial_units": initial_units,
                "initial_ownership_status": initial_ownership_status,
                "ownership_status": ownership_status,
                "minimum_score": minimum_score,
                "merge_steps": merge_steps,
                "robust_threshold": robust_threshold,
            }
        if minimum_score >= robust_threshold:
            return {
                "status": (
                    "robust_partition"
                    if ownership_status == CONNECTED_STATUS
                    else "robust_partition_disconnected"
                ),
                "units": units,
                "initial_units": initial_units,
                "initial_ownership_status": initial_ownership_status,
                "ownership_status": ownership_status,
                "minimum_score": minimum_score,
                "merge_steps": merge_steps,
                "robust_threshold": robust_threshold,
            }

        weakest = min(units, key=lambda unit: (unit.score, unit.group_ids))
        left_groups, right_groups = _best_coupled_pair(
            units, weakest, groups
        )
        left_index = next(
            index
            for index, cluster in enumerate(clusters)
            if cluster == left_groups
        )
        right_index = next(
            index
            for index, cluster in enumerate(clusters)
            if cluster == right_groups
        )
        merge_steps.append(
            {
                "reason": (
                    "below_mutual_majority"
                ),
                "left_group_ids": sorted(left_groups),
                "right_group_ids": sorted(right_groups),
                "minimum_score_before_merge": minimum_score,
            }
        )
        clusters = _merge_pair(clusters, left_index, right_index)

    raise AssertionError("Polling-group partition loop exhausted unexpectedly")
