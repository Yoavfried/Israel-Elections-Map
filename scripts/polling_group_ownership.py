from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import geopandas as gpd


EPSILON = 1e-12


@dataclass(frozen=True)
class OwnershipSearchStats:
    visited_nodes: int
    pruned_by_coverage: int
    pruned_by_connectivity: int
    pruned_by_objective: int
    search_limit_reached: bool


def build_area_adjacency(
    area_ids: list[str],
    geometry_by_id: dict[str, Any],
    *,
    metric_crs: str,
    tolerance_meters: float,
) -> dict[str, frozenset[str]]:
    missing = sorted(set(area_ids) - set(geometry_by_id))
    if missing:
        raise ValueError(f"Ownership solver lacks geometry for areas: {missing}")

    ordered_ids = sorted(set(area_ids))
    projected = gpd.GeoSeries(
        [geometry_by_id[area_id] for area_id in ordered_ids],
        index=ordered_ids,
        crs="EPSG:4326",
    ).to_crs(metric_crs)
    adjacency: dict[str, set[str]] = {
        area_id: {area_id} for area_id in ordered_ids
    }
    for left_index, left_id in enumerate(ordered_ids):
        left = projected.loc[left_id]
        for right_id in ordered_ids[left_index + 1 :]:
            if left.distance(projected.loc[right_id]) <= tolerance_meters:
                adjacency[left_id].add(right_id)
                adjacency[right_id].add(left_id)
    return {
        area_id: frozenset(neighbors)
        for area_id, neighbors in adjacency.items()
    }


def is_connected_area_set(
    area_ids: set[str] | frozenset[str],
    adjacency: dict[str, frozenset[str]],
) -> bool:
    if len(area_ids) < 2:
        return True
    pending = [min(area_ids)]
    visited: set[str] = set()
    while pending:
        area_id = pending.pop()
        if area_id in visited:
            continue
        visited.add(area_id)
        pending.extend(
            neighbor
            for neighbor in adjacency[area_id]
            if neighbor in area_ids and neighbor not in visited
        )
    return len(visited) == len(area_ids)


def _score(
    owned: dict[str, set[str]],
    represented: dict[str, int],
    planned: dict[str, int],
) -> tuple[float, int, float]:
    shares = [
        represented[group_id] / planned[group_id]
        if planned[group_id]
        else 0.0
        for group_id in sorted(owned)
    ]
    return min(shares), sum(represented.values()), sum(shares)


def _score_better(
    candidate: tuple[float, int, float],
    current: tuple[float, int, float] | None,
) -> bool:
    if current is None:
        return True
    if candidate[0] > current[0] + EPSILON:
        return True
    if candidate[0] < current[0] - EPSILON:
        return False
    if candidate[1] != current[1]:
        return candidate[1] > current[1]
    return candidate[2] > current[2] + EPSILON


def _score_equal(
    left: tuple[float, int, float],
    right: tuple[float, int, float],
) -> bool:
    return (
        abs(left[0] - right[0]) <= EPSILON
        and left[1] == right[1]
        and abs(left[2] - right[2]) <= EPSILON
    )


def solve_polling_group_ownership(
    area_ids: list[str],
    groups: dict[str, dict[str, Any]],
    geometry_by_id: dict[str, Any],
    *,
    metric_crs: str,
    tolerance_meters: float,
    max_search_nodes: int = 2_000_000,
) -> dict[str, Any]:
    """
    Assign every candidate polygon to one polling group.

    The exact lexicographic objective is:
    1. every group owns at least one polygon;
    2. prefer a solution in which every group's owned polygons are connected;
    3. maximize the weakest group's represented planned-electorate share;
    4. maximize total represented planned electorate;
    5. maximize the sum of represented shares;
    6. choose the lexicographically smallest stable assignment.

    Search runs only over genuinely shared polygons. Forced single-owner
    polygons are applied before branching, and coverage, connectivity, and
    objective upper bounds prune the remaining search.
    """

    ordered_areas = sorted(set(area_ids))
    ordered_groups = sorted(groups)
    if not ordered_areas or not ordered_groups:
        return {"status": "empty_network"}
    if len(ordered_areas) < len(ordered_groups):
        return {"status": "fewer_polygons_than_polling_groups"}

    candidate_owners: dict[str, tuple[str, ...]] = {}
    weights: dict[str, dict[str, int]] = {}
    planned: dict[str, int] = {}
    for group_id in ordered_groups:
        group_area_ids = {
            str(area_id).strip()
            for area_id in groups[group_id]["area_ids"]
            if str(area_id).strip()
        }
        weights[group_id] = {
            str(area_id).strip(): int(value)
            for area_id, value in groups[group_id]["weights"].items()
            if str(area_id).strip()
        }
        planned[group_id] = int(groups[group_id]["planned"])
        if planned[group_id] <= 0:
            return {
                "status": "group_without_planned_electorate",
                "group_id": group_id,
            }
        groups[group_id]["area_ids"] = group_area_ids

    for area_id in ordered_areas:
        owners = tuple(
            group_id
            for group_id in ordered_groups
            if area_id in groups[group_id]["area_ids"]
        )
        if not owners:
            return {"status": "area_without_candidate_group", "area_id": area_id}
        candidate_owners[area_id] = owners

    adjacency = build_area_adjacency(
        ordered_areas,
        geometry_by_id,
        metric_crs=metric_crs,
        tolerance_meters=tolerance_meters,
    )
    owned: dict[str, set[str]] = {group_id: set() for group_id in ordered_groups}
    represented = {group_id: 0 for group_id in ordered_groups}
    assignment: dict[str, str] = {}
    unassigned = set(ordered_areas)

    for area_id in ordered_areas:
        owners = candidate_owners[area_id]
        if len(owners) != 1:
            continue
        owner = owners[0]
        assignment[area_id] = owner
        owned[owner].add(area_id)
        represented[owner] += weights[owner].get(area_id, 0)
        unassigned.remove(area_id)

    coverage_cache: dict[tuple[tuple[str, ...], tuple[str, ...]], bool] = {}

    def can_cover_unowned_groups() -> bool:
        unowned_groups = tuple(
            group_id for group_id in ordered_groups if not owned[group_id]
        )
        if not unowned_groups:
            return True
        remaining_areas = tuple(sorted(unassigned))
        cache_key = (unowned_groups, remaining_areas)
        cached = coverage_cache.get(cache_key)
        if cached is not None:
            return cached

        matched_group_by_area: dict[str, str] = {}

        def augment(group_id: str, seen: set[str]) -> bool:
            candidates = sorted(
                (
                    area_id
                    for area_id in remaining_areas
                    if group_id in candidate_owners[area_id]
                ),
                key=lambda area_id: (
                    -weights[group_id].get(area_id, 0),
                    area_id,
                ),
            )
            for area_id in candidates:
                if area_id in seen:
                    continue
                seen.add(area_id)
                previous = matched_group_by_area.get(area_id)
                if previous is None or augment(previous, seen):
                    matched_group_by_area[area_id] = group_id
                    return True
            return False

        result = all(
            augment(group_id, set())
            for group_id in sorted(
                unowned_groups,
                key=lambda candidate: (
                    sum(
                        candidate in candidate_owners[area_id]
                        for area_id in remaining_areas
                    ),
                    candidate,
                ),
            )
        )
        coverage_cache[cache_key] = result
        return result

    def connectivity_still_possible() -> bool:
        for group_id in ordered_groups:
            current = owned[group_id]
            if not current:
                continue
            allowed = current | {
                area_id
                for area_id in unassigned
                if group_id in candidate_owners[area_id]
            }
            pending = [min(current)]
            reachable: set[str] = set()
            while pending:
                area_id = pending.pop()
                if area_id in reachable:
                    continue
                reachable.add(area_id)
                pending.extend(
                    neighbor
                    for neighbor in adjacency[area_id]
                    if neighbor in allowed and neighbor not in reachable
                )
            if not current.issubset(reachable):
                return False
        return True

    def objective_upper_bound() -> tuple[float, int, float]:
        upper_represented = dict(represented)
        total_upper = sum(represented.values())
        for area_id in unassigned:
            area_weights = [
                weights[group_id].get(area_id, 0)
                for group_id in candidate_owners[area_id]
            ]
            total_upper += max(area_weights)
            for group_id in candidate_owners[area_id]:
                upper_represented[group_id] += weights[group_id].get(area_id, 0)
        upper_shares = [
            upper_represented[group_id] / planned[group_id]
            for group_id in ordered_groups
        ]
        return min(upper_shares), total_upper, sum(upper_shares)

    def canonical_key() -> tuple[str, ...]:
        return tuple(assignment[area_id] for area_id in ordered_areas)

    best_any_score: tuple[float, int, float] | None = None
    best_any_key: tuple[str, ...] | None = None
    best_any_assignment: dict[str, str] | None = None
    best_connected_score: tuple[float, int, float] | None = None
    best_connected_key: tuple[str, ...] | None = None
    best_connected_assignment: dict[str, str] | None = None
    visited_nodes = 0
    pruned_by_coverage = 0
    pruned_by_connectivity = 0
    pruned_by_objective = 0
    search_limit_reached = False

    def record_solution() -> None:
        nonlocal best_any_score
        nonlocal best_any_key
        nonlocal best_any_assignment
        nonlocal best_connected_score
        nonlocal best_connected_key
        nonlocal best_connected_assignment

        score = _score(owned, represented, planned)
        key = canonical_key()
        if _score_better(score, best_any_score) or (
            best_any_score is not None
            and _score_equal(score, best_any_score)
            and (best_any_key is None or key < best_any_key)
        ):
            best_any_score = score
            best_any_key = key
            best_any_assignment = dict(assignment)

        connected = all(
            is_connected_area_set(owned[group_id], adjacency)
            for group_id in ordered_groups
        )
        if not connected:
            return
        if _score_better(score, best_connected_score) or (
            best_connected_score is not None
            and _score_equal(score, best_connected_score)
            and (best_connected_key is None or key < best_connected_key)
        ):
            best_connected_score = score
            best_connected_key = key
            best_connected_assignment = dict(assignment)

    def upper_bound_cannot_beat(
        upper: tuple[float, int, float],
        best: tuple[float, int, float] | None,
    ) -> bool:
        if best is None:
            return False
        if upper[0] < best[0] - EPSILON:
            return True
        if abs(upper[0] - best[0]) <= EPSILON and upper[1] < best[1]:
            return True
        return (
            abs(upper[0] - best[0]) <= EPSILON
            and upper[1] == best[1]
            and upper[2] < best[2] - EPSILON
        )

    def select_next_area() -> tuple[str, str | None]:
        forced_group: str | None = None
        forced_area: str | None = None
        for group_id in ordered_groups:
            if owned[group_id]:
                continue
            candidates = [
                area_id
                for area_id in unassigned
                if group_id in candidate_owners[area_id]
            ]
            if len(candidates) == 1:
                forced_group = group_id
                forced_area = candidates[0]
                break
        if forced_area is not None:
            return forced_area, forced_group

        area_id = min(
            unassigned,
            key=lambda candidate: (
                len(candidate_owners[candidate]),
                -max(
                    weights[group_id].get(candidate, 0) / planned[group_id]
                    for group_id in candidate_owners[candidate]
                ),
                candidate,
            ),
        )
        return area_id, None

    def owner_order(area_id: str, forced_group: str | None) -> list[str]:
        if forced_group is not None:
            return [forced_group]
        current_shares = {
            group_id: represented[group_id] / planned[group_id]
            for group_id in ordered_groups
        }
        return sorted(
            candidate_owners[area_id],
            key=lambda group_id: (
                current_shares[group_id],
                -weights[group_id].get(area_id, 0) / planned[group_id],
                -weights[group_id].get(area_id, 0),
                group_id,
            ),
        )

    def search(*, require_connectivity: bool) -> None:
        nonlocal visited_nodes
        nonlocal pruned_by_coverage
        nonlocal pruned_by_connectivity
        nonlocal pruned_by_objective
        nonlocal search_limit_reached

        if visited_nodes >= max_search_nodes:
            search_limit_reached = True
            return
        visited_nodes += 1

        if not can_cover_unowned_groups():
            pruned_by_coverage += 1
            return
        if require_connectivity and not connectivity_still_possible():
            pruned_by_connectivity += 1
            return

        best_score = best_connected_score if require_connectivity else best_any_score
        if upper_bound_cannot_beat(objective_upper_bound(), best_score):
            pruned_by_objective += 1
            return

        if not unassigned:
            if all(owned[group_id] for group_id in ordered_groups):
                record_solution()
            return

        area_id, forced_group = select_next_area()
        for group_id in owner_order(area_id, forced_group):
            assignment[area_id] = group_id
            owned[group_id].add(area_id)
            represented[group_id] += weights[group_id].get(area_id, 0)
            unassigned.remove(area_id)
            search(require_connectivity=require_connectivity)
            unassigned.add(area_id)
            represented[group_id] -= weights[group_id].get(area_id, 0)
            owned[group_id].remove(area_id)
            del assignment[area_id]
            if search_limit_reached:
                return

    search(require_connectivity=True)
    if best_connected_assignment is None and not search_limit_reached:
        search(require_connectivity=False)

    chosen_assignment = best_connected_assignment or best_any_assignment
    chosen_score = best_connected_score or best_any_score
    if chosen_assignment is None or chosen_score is None:
        status = (
            "search_limit_without_solution"
            if search_limit_reached
            else "no_every-group-owns-polygon_solution"
        )
        return {
            "status": status,
            "search": OwnershipSearchStats(
                visited_nodes=visited_nodes,
                pruned_by_coverage=pruned_by_coverage,
                pruned_by_connectivity=pruned_by_connectivity,
                pruned_by_objective=pruned_by_objective,
                search_limit_reached=search_limit_reached,
            ),
        }

    ownership: dict[str, tuple[str, ...]] = {
        group_id: tuple(
            area_id
            for area_id in ordered_areas
            if chosen_assignment[area_id] == group_id
        )
        for group_id in ordered_groups
    }
    represented_shares = {
        group_id: (
            sum(weights[group_id].get(area_id, 0) for area_id in owned_ids)
            / planned[group_id]
        )
        for group_id, owned_ids in ownership.items()
    }
    connected = best_connected_assignment is not None
    if search_limit_reached:
        status = (
            "connected_solution_search_limited"
            if connected
            else "disconnected_solution_search_limited"
        )
    else:
        status = (
            "connected_solution"
            if connected
            else "solution_requires_disconnected_geometry"
        )
    return {
        "status": status,
        "minimum_represented_share": chosen_score[0],
        "total_represented_planned_eligible": chosen_score[1],
        "mean_represented_share": chosen_score[2] / len(ordered_groups),
        "ownership": ownership,
        "represented_shares": represented_shares,
        "search": OwnershipSearchStats(
            visited_nodes=visited_nodes,
            pruned_by_coverage=pruned_by_coverage,
            pruned_by_connectivity=pruned_by_connectivity,
            pruned_by_objective=pruned_by_objective,
            search_limit_reached=search_limit_reached,
        ),
    }
