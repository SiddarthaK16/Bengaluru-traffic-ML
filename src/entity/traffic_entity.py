from dataclasses import dataclass
from datetime import datetime


@dataclass
class TrafficEntity:

    location: str
    collection_run_id: str

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
