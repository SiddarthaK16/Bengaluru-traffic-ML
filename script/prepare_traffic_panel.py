"""Export a synchronized, outage-aware traffic feature table from MongoDB."""

from collections import defaultdict
from datetime import datetime, timedelta
import csv
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError


ROOT = Path(__file__).resolve().parents[1]
DATABASE_NAME = "bengaluru_traffic"
COLLECTION_NAME = "traffic_data"
MATCH_TOLERANCE_DEGREES = 0.00001
MAX_ROUND_SPREAD = timedelta(minutes=2)
MAX_CONTIGUOUS_GAP = timedelta(minutes=30)
OUTPUT_PATH = ROOT / "data" / "processed" / "traffic_panel.csv"


def load_locations():
    with (ROOT / "src" / "constant" / "locations.yaml").open() as file:
        return yaml.safe_load(file)["locations"]


def match_location(record, locations):
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


def load_records(collection, locations):
    by_location = defaultdict(list)
    unmatched = 0
    missing_timestamp = 0
    projection = {
        "_id": 0,
        "latitude": 1,
        "longitude": 1,
        "timestamp": 1,
        "currentSpeed": 1,
        "freeFlowSpeed": 1,
    }

    for record in collection.find({}, projection):
        name = match_location(record, locations)
        if name is None:
            unmatched += 1
            continue
        if record.get("timestamp") is None:
            missing_timestamp += 1
            continue
        by_location[name].append(record)

    for records in by_location.values():
        records.sort(key=lambda record: record["timestamp"])
    return by_location, unmatched, missing_timestamp


def main():
    load_dotenv(ROOT / ".env")
    mongo_url = os.getenv("MONGO_DB_URL")
    if not mongo_url:
        raise SystemExit("MONGO_DB_URL is missing from the project .env file")

    locations = load_locations()
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=10000)
    try:
        client.admin.command("ping")
        collection = client[DATABASE_NAME][COLLECTION_NAME]
        by_location, unmatched, missing_timestamp = load_records(collection, locations)
    except ServerSelectionTimeoutError as error:
        print("Could not connect to MongoDB Atlas. Check that the cluster is running")
        print("and your current public IP is on the Atlas IP Access List.")
        if "SSL handshake failed" in str(error):
            print("The failure happened during TLS setup, before database login.")
        else:
            print(f"Connection detail: {error}")
        raise SystemExit(1) from None
    finally:
        client.close()

    # New records share an explicit collection_run_id. Older records have no
    # run ID, so retain the original timestamp-ordered alignment for that data.
    runs = defaultdict(dict)
    legacy = {name: [] for name in locations}
    for name in locations:
        for record in by_location[name]:
            run_id = record.get("collection_run_id")
            if run_id:
                runs[run_id][name] = record
            else:
                legacy[name].append(record)

    rounds = [
        records for records in runs.values()
        if len(records) == len(locations)
    ]
    incomplete_runs = sum(
        len(records) != len(locations) for records in runs.values()
    )
    legacy_counts = {len(records) for records in legacy.values()}
    if legacy_counts and legacy_counts != {0}:
        if len(legacy_counts) != 1:
            counts = {name: len(legacy[name]) for name in locations}
            raise SystemExit(
                "Legacy location record counts differ; cannot safely align "
                f"rounds: {counts}. New records are aligned by collection_run_id."
            )
        legacy_count = next(iter(legacy_counts))
        rounds.extend(
            {name: legacy[name][index] for name in locations}
            for index in range(legacy_count)
        )

    if not rounds:
        raise SystemExit("No complete collection rounds found for all locations.")

    rounds.sort(
        key=lambda records: min(record["timestamp"] for record in records.values())
    )
    rows = []
    invalid_ratios = 0
    max_spread = timedelta(0)
    for index, records_by_location in enumerate(rounds):
        round_records = [records_by_location[name] for name in locations]
        timestamps = [record["timestamp"] for record in round_records]
        spread = max(timestamps) - min(timestamps)
        max_spread = max(max_spread, spread)
        if spread > MAX_ROUND_SPREAD:
            raise SystemExit(
                f"Round {index} spans {spread}, exceeding the "
                f"{MAX_ROUND_SPREAD} alignment limit."
            )

        # The midpoint is a representative timestamp for the sequential API calls.
        timestamp = min(timestamps) + spread / 2
        row = {
            "timestamp": timestamp.isoformat(sep=" "),
            "collection_run_id": round_records[0].get("collection_run_id") or "legacy",
        }
        for name, record in zip(locations, round_records):
            current_speed = record.get("currentSpeed")
            free_flow_speed = record.get("freeFlowSpeed")
            if current_speed is None or free_flow_speed in (None, 0):
                row[f"congestion_ratio_{name}"] = ""
                invalid_ratios += 1
            else:
                row[f"congestion_ratio_{name}"] = current_speed / free_flow_speed
        rows.append(row)

    segment_id = 0
    previous_timestamp = None
    for row in rows:
        timestamp = datetime.fromisoformat(row["timestamp"])
        if (
            previous_timestamp is not None
            and timestamp - previous_timestamp > MAX_CONTIGUOUS_GAP
        ):
            segment_id += 1
        row["segment_id"] = segment_id
        previous_timestamp = timestamp

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["timestamp", "segment_id", "collection_run_id"] + [
        f"congestion_ratio_{name}" for name in locations
    ]
    with OUTPUT_PATH.open("w", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Prepared rows: {len(rows)}")
    print(f"Incomplete identified rounds omitted: {incomplete_runs}")
    print(f"Locations/features: {len(locations)} congestion ratios")
    print(f"Unmatched source records: {unmatched}")
    print(f"Matched records missing timestamps: {missing_timestamp}")
    print(f"Invalid ratios (missing/zero free-flow speed): {invalid_ratios}")
    print(f"Maximum timestamp spread within a round: {max_spread}")
    print(f"Continuous segments: {segment_id + 1}")
    print(f"Saved panel: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
