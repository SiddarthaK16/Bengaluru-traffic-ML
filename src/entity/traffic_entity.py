from dataclasses import dataclass
from datetime import datetime


@dataclass
class TrafficEntity:

    latitude: float
    longitude: float

    current_speed: float
    free_flow_speed: float

    current_travel_time: float
    free_flow_travel_time: float

    confidence: float
    road_closure: bool

    frc: str

    timestamp: datetime