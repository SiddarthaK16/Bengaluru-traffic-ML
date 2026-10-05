"""Print read-only coverage statistics for the MongoDB traffic collection."""

from collections import defaultdict
from datetime import timedelta
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError


ROOT = Path(__file__).resolve().parents[1]
COLLECTION_NAME = "traffic_data"
DATABASE_NAME = "bengaluru_traffic"
MATCH_TOLERANCE_DEGREES = 0.00001
MAX_CONTIGUOUS_GAP = timedelta(minutes=30)


def load_locations():
    with (ROOT / "src" / "constant" / "locations.yaml").open() as file:
        config = yaml.safe_load(file)
    return config["locations"]


def match_location(latitude, longitude, locations):
    if latitude is None or longitude is None:
        return None

    closest_name = None
    closest_distance = float("inf")
    for name, coordinates in locations.items():
        distance = max(
            abs(latitude - coordinates["latitude"]),
            abs(longitude - coordinates["longitude"]),
        )
        if distance < closest_distance:
            closest_name = name
            closest_distance = distance

    if closest_distance <= MATCH_TOLERANCE_DEGREES:
        return closest_name
    return None


def main():
    load_dotenv(ROOT / ".env")
    mongo_url = os.getenv("MONGO_DB_URL")
    if not mongo_url:
        raise SystemExit("MONGO_DB_URL is missing from the project .env file")

    locations = load_locations()
    readings = defaultdict(list)
    unmatched = 0
    missing_timestamp = 0

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=10000)
    try:
        client.admin.command("ping")
        collection = client[DATABASE_NAME][COLLECTION_NAME]
        total = collection.count_documents({})

        cursor = collection.find(
            {},
            {"_id": 0, "latitude": 1, "longitude": 1, "timestamp": 1},
        )
        for record in cursor:
            name = match_location(
                record.get("latitude"), record.get("longitude"), locations
            )
            if name is None:
                unmatched += 1
                continue

            timestamp = record.get("timestamp")
            if timestamp is None:
                missing_timestamp += 1
                continue
            readings[name].append(timestamp)

        print(f"Total records: {total}")
        print(f"Locations in YAML: {len(locations)}")
        print(f"Records not matched to YAML coordinates: {unmatched}")
        print(f"Matched records with missing timestamps: {missing_timestamp}")
        print("\nPer-location coverage (timestamps shown as stored):")
        for name in locations:
            timestamps = sorted(readings[name])
            if not timestamps:
                print(f"{name}: 0 records")
                continue

            gaps = [
                (right - left).total_seconds() / 60
                for left, right in zip(timestamps, timestamps[1:])
            ]
            over_30_min = sum(minutes > 30 for minutes in gaps)
            median_gap = sorted(gaps)[len(gaps) // 2] if gaps else None
            median_text = f"{median_gap:.1f} min" if median_gap is not None else "n/a"
            print(
                f"{name}: {len(timestamps)} records | "
                f"{timestamps[0]} to {timestamps[-1]} | "
                f"median gap {median_text} | gaps over 30 min: {over_30_min}"
            )

        reference_name = next(iter(locations))
        reference_times = sorted(readings[reference_name])
        segments = []
        current_segment = []
        for timestamp in reference_times:
            if (
                current_segment
                and timestamp - current_segment[-1] > MAX_CONTIGUOUS_GAP
            ):
                segments.append(current_segment)
                current_segment = []
            current_segment.append(timestamp)
        if current_segment:
            segments.append(current_segment)

        print(
            f"\nContinuous collection segments (split at gaps over "
            f"{MAX_CONTIGUOUS_GAP.total_seconds() / 60:.0f} min): "
            f"{len(segments)}"
        )
        print("Potential one-step-ahead windows after removing outage crossings:")
        for lookback in (4, 8, 12, 96):
            count = sum(max(0, len(segment) - lookback) for segment in segments)
            print(f"  lookback {lookback:>2} readings ({lookback * 15:>4} nominal min): {count}")

        aligned_locations = {
            name: sorted(readings[name]) for name in locations
        }
        if all(len(times) == len(reference_times) for times in aligned_locations.values()):
            max_round_spread = max(
                (max(times[index] for times in aligned_locations.values())
                 - min(times[index] for times in aligned_locations.values()))
                for index in range(len(reference_times))
            )
            print(
                "Maximum timestamp spread within an ordinal collection round: "
                f"{max_round_spread}"
            )

        long_gaps = sorted(
            (
                (right - left, left, right)
                for left, right in zip(reference_times, reference_times[1:])
            ),
            reverse=True,
        )
        print(f"\n10 longest gaps for {reference_name}:")
        for duration, left, right in long_gaps[:10]:
            print(f"{duration} | {left} -> {right}")
    except ServerSelectionTimeoutError as error:
        print("Could not connect to MongoDB Atlas (server selection timed out).")
        print("Check that the cluster is running and your current public IP is")
        print("listed under Atlas Project > Network Access > IP Access List.")
        print("Also try connecting to the same cluster from MongoDB Compass.")
        if "SSL handshake failed" in str(error):
            print("The failure happened during TLS setup, before database login.")
        else:
            print(f"Connection detail: {error}")
        raise SystemExit(1) from None
    finally:
        client.close()


if __name__ == "__main__":
    main()
