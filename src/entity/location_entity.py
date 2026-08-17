from dataclasses import dataclass


@dataclass
class LocationEntity:

    name: str
    latitude: float
    longitude: float