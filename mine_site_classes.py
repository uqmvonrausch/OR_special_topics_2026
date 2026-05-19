import math
from dataclasses import dataclass
from enum import Enum


class TruckState(Enum):
    LOADED = 1
    UNLOADED = 2

MINS_PER_HOUR = 60

@dataclass(frozen=True)
class OperatingRules:
    speed_loaded_kph: float
    speed_unloaded_kph: float
    loading_time_min: int
    unloading_time_min: int

    @classmethod
    def from_data(cls, data: dict) -> "OperatingRules":
        return cls(
            speed_loaded_kph=data["speed_loaded_kph"],
            speed_unloaded_kph=data["speed_unloaded_kph"],
            loading_time_min=data["loading_time_min"],
            unloading_time_min=data["unloading_time_min"],
        )


class Shovel:
    def __init__(self, site_id: int, init_trucks: int):
        self.site_id = site_id
        self.init_trucks = init_trucks

    def __eq__(self, other):
        return isinstance(other, Shovel) and self.site_id == other.site_id

    def __hash__(self):
        return hash(('S', self.site_id))

    def __repr__(self):
        return f"Shovel(id={self.site_id})"


class Dump:
    def __init__(self, site_id: int, init_trucks: int, desired_throughput: int):
        self.site_id = site_id
        self.init_trucks = init_trucks
        self.desired_throughput = desired_throughput

    def __eq__(self, other):
        return isinstance(other, Dump) and self.site_id == other.site_id

    def __hash__(self):
        return hash(('D', self.site_id))

    def __repr__(self):
        return f"Dump(id={self.site_id})"


class Job:
    _next_id: int = 0

    def __init__(self, source: Shovel | Dump, destination: Shovel | Dump,
                 truck_state: TruckState, distance: float, rules: OperatingRules):
        self.id = Job._next_id
        Job._next_id += 1
        self.source = source
        self.destination = destination
        self.truck_state = truck_state
        self.distance = distance
        self.duration = self._calc_duration(rules)

    def _calc_duration(self, rules: OperatingRules) -> int:
        if self.truck_state == TruckState.LOADED:
            speed   = rules.speed_loaded_kph
            op_time = rules.unloading_time_min
        else:
            speed   = rules.speed_unloaded_kph
            op_time = rules.loading_time_min
        return math.ceil((self.distance / speed) * MINS_PER_HOUR / 1000 + op_time)

    def __eq__(self, other):
        return isinstance(other, Job) and self.source == other.source and self.destination == other.destination

    def __hash__(self):
        return hash((self.source, self.destination))

    def __repr__(self):
        if self.truck_state == TruckState.LOADED:
            return f"Loaded trip: {self.source} -> {self.destination} [{self.duration} mins]"
        else:
            return f"Unloaded trip: {self.source} -> {self.destination} [{self.duration} mins]"
