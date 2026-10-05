"""HTTP endpoints for live monitored traffic and traffic-aware route planning."""

from datetime import datetime, timezone
from functools import lru_cache
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from pymongo.errors import PyMongoError


ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"
DATABASE_NAME = "bengaluru_traffic"
COLLECTION_NAME = "traffic_data"
MATCH_TOLERANCE_DEGREES = 0.00001
BENGALURU_BOUNDS = {
    "min_latitude": 12.70,
    "max_latitude": 13.25,
    "min_longitude": 77.35,
    "max_longitude": 77.85,
}

app = FastAPI(title="Bengaluru Traffic", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def load_locations():
    with (ROOT / "src" / "constant" / "locations.yaml").open() as config_file:
        return yaml.safe_load(config_file)["locations"]


@lru_cache(maxsize=1)
def mongo_client():
    mongo_url = os.getenv("MONGO_DB_URL")
    if not mongo_url:
        raise HTTPException(status_code=503, detail="MONGO_DB_URL is not configured")
    return MongoClient(mongo_url, serverSelectionTimeoutMS=5000)


def match_location(record, locations):
    if record.get("location") in locations:
        return record["location"]
    latitude = record.get("latitude")
    longitude = record.get("longitude")
    if latitude is None or longitude is None:
        return None
    for name, coordinates in locations.items():
        if (
            abs(latitude - coordinates["latitude"]) <= MATCH_TOLERANCE_DEGREES
            and abs(longitude - coordinates["longitude"]) <= MATCH_TOLERANCE_DEGREES
        ):
            return name
    return None


def iso_timestamp(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/locations")
def locations():
    return load_locations()


@app.get("/api/traffic/latest")
def latest_traffic():
    try:
        collection = mongo_client()[DATABASE_NAME][COLLECTION_NAME]
        locations_by_name = load_locations()
        latest = {}
        projection = {
            "_id": 0,
            "location": 1,
            "latitude": 1,
            "longitude": 1,
            "timestamp": 1,
            "currentSpeed": 1,
            "freeFlowSpeed": 1,
            "currentTravelTime": 1,
            "freeFlowTravelTime": 1,
            "confidence": 1,
            "roadClosure": 1,
            "frc": 1,
        }
        cursor = collection.find({}, projection).sort("timestamp", -1)
        for record in cursor:
            location_name = match_location(record, locations_by_name)
            if location_name is None or location_name in latest:
                continue
            current_speed = record.get("currentSpeed")
            free_flow_speed = record.get("freeFlowSpeed")
            ratio = (
                current_speed / free_flow_speed
                if current_speed is not None and free_flow_speed not in (None, 0)
                else None
            )
            latest[location_name] = {
                "location": location_name,
                "latitude": record.get("latitude"),
                "longitude": record.get("longitude"),
                "timestamp": iso_timestamp(record.get("timestamp")),
                "current_speed_kmh": current_speed,
                "free_flow_speed_kmh": free_flow_speed,
                "congestion_ratio": ratio,
                "current_travel_time_seconds": record.get("currentTravelTime"),
                "free_flow_travel_time_seconds": record.get("freeFlowTravelTime"),
                "confidence": record.get("confidence"),
                "road_closure": record.get("roadClosure"),
                "frc": record.get("frc"),
            }
            if len(latest) == len(locations_by_name):
                break
        return {
            "updated_at": max(
                (item["timestamp"] for item in latest.values() if item["timestamp"]),
                default=None,
            ),
            "records": list(latest.values()),
            "expected_locations": len(locations_by_name),
        }
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Traffic database is unavailable") from None


@app.get("/api/route")
def calculate_route(
    origin_lat: float = Query(..., ge=-90, le=90),
    origin_lon: float = Query(..., ge=-180, le=180),
    destination_lat: float = Query(..., ge=-90, le=90),
    destination_lon: float = Query(..., ge=-180, le=180),
    departure_time: datetime | None = None,
):
    for latitude, longitude in (
        (origin_lat, origin_lon),
        (destination_lat, destination_lon),
    ):
        if not (
            BENGALURU_BOUNDS["min_latitude"] <= latitude <= BENGALURU_BOUNDS["max_latitude"]
            and BENGALURU_BOUNDS["min_longitude"] <= longitude <= BENGALURU_BOUNDS["max_longitude"]
        ):
            raise HTTPException(status_code=422, detail="Select points within Bengaluru")

    api_key = os.getenv("TOMTOM_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="TOMTOM_API_KEY is not configured")

    if departure_time is None:
        departure_value = "now"
    else:
        if departure_time.tzinfo is None:
            departure_time = departure_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        if departure_time < datetime.now(timezone.utc).replace(microsecond=0):
            raise HTTPException(status_code=422, detail="Departure time must be in the future")
        departure_value = departure_time.isoformat(timespec="seconds")

    route_url = (
        "https://api.tomtom.com/routing/1/calculateRoute/"
        f"{origin_lat},{origin_lon}:{destination_lat},{destination_lon}/json"
    )
    try:
        response = requests.get(
            route_url,
            params={
                "key": api_key,
                "traffic": "true",
                "departAt": departure_value,
                "computeTravelTimeFor": "all",
                "routeType": "fastest",
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        route = payload["routes"][0]
        summary = route["summary"]
        points = [
            [point["longitude"], point["latitude"]]
            for leg in route.get("legs", [])
            for point in leg.get("points", [])
        ]
        if not points:
            raise KeyError("route geometry")
    except (requests.RequestException, ValueError, KeyError, IndexError):
        raise HTTPException(
            status_code=502,
            detail="Route service could not calculate this trip",
        ) from None

    return {
        "departure_time": summary.get("departureTime", departure_value),
        "arrival_time": summary.get("arrivalTime"),
        "length_meters": summary.get("lengthInMeters"),
        "travel_time_seconds": summary.get("travelTimeInSeconds"),
        "traffic_delay_seconds": summary.get("trafficDelayInSeconds"),
        "no_traffic_travel_time_seconds": summary.get("noTrafficTravelTimeInSeconds"),
        "geometry": {"type": "LineString", "coordinates": points},
        "source": "TomTom Routing API with traffic",
    }


@app.on_event("shutdown")
def close_mongo_client():
    client = mongo_client.cache_info()
    if client.currsize:
        mongo_client().close()
        mongo_client.cache_clear()
