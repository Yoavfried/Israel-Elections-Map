from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class FlowComponent:
    area_ids: tuple[str, ...]
    polling_group_ids: tuple[str, ...]
    eligible_voters: int


@dataclass(frozen=True)
class FlowAnalysis:
    components: tuple[FlowComponent, ...]
    edge_bounds: dict[tuple[str, str], tuple[int, int]]
    forced_zero_edges: tuple[tuple[str, str], ...]


@dataclass
class _Edge:
    target: int
    reverse: int
    capacity: int


class _Dinic:
    def __init__(self, node_count: int) -> None:
        self.graph: list[list[_Edge]] = [[] for _ in range(node_count)]

    def add_edge(self, source: int, target: int, capacity: int) -> None:
        forward = _Edge(target, len(self.graph[target]), capacity)
        reverse = _Edge(source, len(self.graph[source]), 0)
        self.graph[source].append(forward)
        self.graph[target].append(reverse)

    def maximum_flow(self, source: int, sink: int) -> int:
        total = 0
        while True:
            level = [-1] * len(self.graph)
            level[source] = 0
            pending = deque([source])
            while pending:
                current = pending.popleft()
                for edge in self.graph[current]:
                    if edge.capacity > 0 and level[edge.target] < 0:
                        level[edge.target] = level[current] + 1
                        pending.append(edge.target)
            if level[sink] < 0:
                return total

            cursor = [0] * len(self.graph)

            def send(current: int, amount: int) -> int:
                if current == sink:
                    return amount
                while cursor[current] < len(self.graph[current]):
                    edge = self.graph[current][cursor[current]]
                    if edge.capacity > 0 and level[current] + 1 == level[edge.target]:
                        sent = send(edge.target, min(amount, edge.capacity))
                        if sent:
                            edge.capacity -= sent
                            self.graph[edge.target][edge.reverse].capacity += sent
                            return sent
                    cursor[current] += 1
                return 0

            while True:
                sent = send(source, 10**18)
                if not sent:
                    break
                total += sent


def _transport_feasible(
    area_supplies: dict[str, int],
    group_demands: dict[str, int],
    allowed_areas_by_group: dict[str, set[str]],
    *,
    target_edge: tuple[str, str] | None = None,
    lower_bound: int = 0,
    upper_bound: int | None = None,
) -> bool:
    supplies = dict(area_supplies)
    demands = dict(group_demands)
    if target_edge is not None:
        area_id, group_id = target_edge
        if area_id not in allowed_areas_by_group.get(group_id, set()):
            return False
        edge_limit = min(supplies.get(area_id, 0), demands.get(group_id, 0))
        effective_upper = edge_limit if upper_bound is None else upper_bound
        if lower_bound < 0 or effective_upper < lower_bound or effective_upper > edge_limit:
            return False
        supplies[area_id] -= lower_bound
        demands[group_id] -= lower_bound
    else:
        effective_upper = None

    if any(value < 0 for value in supplies.values()) or any(
        value < 0 for value in demands.values()
    ):
        return False
    required = sum(supplies.values())
    if required != sum(demands.values()):
        return False
    if required == 0:
        return True

    area_ids = sorted(supplies)
    group_ids = sorted(demands)
    source = 0
    area_offset = 1
    group_offset = area_offset + len(area_ids)
    sink = group_offset + len(group_ids)
    area_nodes = {
        area_id: area_offset + index for index, area_id in enumerate(area_ids)
    }
    group_nodes = {
        group_id: group_offset + index for index, group_id in enumerate(group_ids)
    }
    flow = _Dinic(sink + 1)
    for area_id, supply in supplies.items():
        flow.add_edge(source, area_nodes[area_id], supply)
    for group_id, demand in demands.items():
        flow.add_edge(group_nodes[group_id], sink, demand)

    for group_id, allowed_areas in allowed_areas_by_group.items():
        if group_id not in group_nodes:
            continue
        for area_id in allowed_areas:
            if area_id not in area_nodes:
                continue
            capacity = required
            if target_edge == (area_id, group_id):
                capacity = int(effective_upper) - lower_bound
            flow.add_edge(area_nodes[area_id], group_nodes[group_id], capacity)
    return flow.maximum_flow(source, sink) == required


def _edge_bounds(
    area_supplies: dict[str, int],
    group_demands: dict[str, int],
    allowed_areas_by_group: dict[str, set[str]],
    edge: tuple[str, str],
) -> tuple[int, int]:
    area_id, group_id = edge
    limit = min(area_supplies[area_id], group_demands[group_id])

    low = 0
    high = limit
    while low < high:
        midpoint = (low + high) // 2
        if _transport_feasible(
            area_supplies,
            group_demands,
            allowed_areas_by_group,
            target_edge=edge,
            upper_bound=midpoint,
        ):
            high = midpoint
        else:
            low = midpoint + 1
    minimum = low

    low = minimum
    high = limit
    while low < high:
        midpoint = (low + high + 1) // 2
        if _transport_feasible(
            area_supplies,
            group_demands,
            allowed_areas_by_group,
            target_edge=edge,
            lower_bound=midpoint,
        ):
            low = midpoint
        else:
            high = midpoint - 1
    return minimum, low


def analyze_exact_flow(
    area_supplies: dict[str, int],
    group_demands: dict[str, int],
    allowed_areas_by_group: dict[str, set[str]],
) -> FlowAnalysis:
    if not area_supplies or not group_demands:
        raise ValueError("Flow analysis requires areas and polling groups")
    if any(value <= 0 for value in area_supplies.values()):
        raise ValueError("Area supplies must be positive")
    if any(value <= 0 for value in group_demands.values()):
        raise ValueError("Polling-group demands must be positive")
    if set(group_demands) != set(allowed_areas_by_group):
        raise ValueError("Every polling group must declare its candidate areas")
    unknown_areas = set().union(*allowed_areas_by_group.values()) - set(area_supplies)
    if unknown_areas:
        raise ValueError(f"Flow candidates reference unknown areas: {sorted(unknown_areas)}")
    if sum(area_supplies.values()) != sum(group_demands.values()):
        raise ValueError("Area supplies and polling-group demands do not balance")
    if not _transport_feasible(
        area_supplies,
        group_demands,
        allowed_areas_by_group,
    ):
        raise ValueError("Polling network has no feasible eligible-voter flow")

    bounds: dict[tuple[str, str], tuple[int, int]] = {}
    for group_id in sorted(group_demands):
        for area_id in sorted(allowed_areas_by_group[group_id]):
            bounds[(area_id, group_id)] = _edge_bounds(
                area_supplies,
                group_demands,
                allowed_areas_by_group,
                (area_id, group_id),
            )

    adjacency: dict[str, set[str]] = defaultdict(set)
    forced_zero: list[tuple[str, str]] = []
    for (area_id, group_id), (_, maximum) in bounds.items():
        area_node = f"area:{area_id}"
        group_node = f"group:{group_id}"
        if maximum == 0:
            forced_zero.append((area_id, group_id))
            continue
        adjacency[area_node].add(group_node)
        adjacency[group_node].add(area_node)

    expected_nodes = {
        *(f"area:{area_id}" for area_id in area_supplies),
        *(f"group:{group_id}" for group_id in group_demands),
    }
    isolated = sorted(expected_nodes - set(adjacency))
    if isolated:
        raise ValueError(f"Positive flow nodes became isolated: {isolated}")

    components: list[FlowComponent] = []
    visited: set[str] = set()
    for start in sorted(expected_nodes):
        if start in visited:
            continue
        pending = [start]
        visited.add(start)
        area_ids: set[str] = set()
        group_ids: set[str] = set()
        while pending:
            current = pending.pop()
            prefix, identifier = current.split(":", 1)
            if prefix == "area":
                area_ids.add(identifier)
            else:
                group_ids.add(identifier)
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    pending.append(neighbor)
        supply = sum(area_supplies[area_id] for area_id in area_ids)
        demand = sum(group_demands[group_id] for group_id in group_ids)
        if supply != demand:
            raise ValueError(
                f"Derived flow component does not balance: {supply} != {demand}"
            )
        components.append(
            FlowComponent(
                area_ids=tuple(sorted(area_ids)),
                polling_group_ids=tuple(sorted(group_ids)),
                eligible_voters=supply,
            )
        )

    return FlowAnalysis(
        components=tuple(
            sorted(
                components,
                key=lambda component: (
                    component.area_ids,
                    component.polling_group_ids,
                ),
            )
        ),
        edge_bounds=bounds,
        forced_zero_edges=tuple(sorted(forced_zero)),
    )
