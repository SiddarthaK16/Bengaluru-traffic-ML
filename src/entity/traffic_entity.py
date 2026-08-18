from dataclasses import dataclass
from datetime import datetime


@dataclass
class TrafficEntity:

    latitude: float
    longitude: float

    currentSpeed: float
    freeFlowSpeed: float

    currentTravelTime: float
    freeFlowTravelTime: float

    confidence: float
    roadClosure: bool

    frc: str

    timestamp: datetime