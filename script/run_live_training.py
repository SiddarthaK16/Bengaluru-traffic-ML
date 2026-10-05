"""Retrain the live traffic forecast when new collection rounds arrive."""

import os
from pathlib import Path
import subprocess
import sys
import time

import yaml
from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
POLL_SECONDS = int(os.getenv("TRAINER_POLL_SECONDS", "60"))
RETRAIN_SECONDS = int(os.getenv("LIVE_RETRAIN_SECONDS", "3600"))
DATABASE_NAME = "bengaluru_traffic"
COLLECTION_NAME = "traffic_data"


def configured_location_count():
    with (ROOT / "src" / "constant" / "locations.yaml").open() as file:
        return len(yaml.safe_load(file)["locations"])


def latest_complete_run(collection, expected_locations):
    record = collection.find_one(
        {"collection_run_id": {"$exists": True}},
        {"_id": 0, "collection_run_id": 1},
        sort=[("timestamp", -1)],
    )
    if record is None:
        return None
    run_id = record["collection_run_id"]
    count = collection.count_documents({"collection_run_id": run_id})
    return run_id if count >= expected_locations else None


def retrain():
    subprocess.run(
        [sys.executable, str(ROOT / "script" / "prepare_traffic_panel.py")],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "script" / "train_catboost_models.py")],
        cwd=ROOT,
        check=True,
    )


def main():
    mongo_url = os.getenv("MONGO_DB_URL")
    if not mongo_url:
        raise SystemExit("MONGO_DB_URL must be configured for live model training")

    expected_locations = configured_location_count()
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=10000)
    collection = client[DATABASE_NAME][COLLECTION_NAME]
    last_trained_run = None
    last_training_time = 0.0
    print(
        f"Live trainer watching collection runs; retrain interval is "
        f"{RETRAIN_SECONDS} seconds.",
        flush=True,
    )
    try:
        while True:
            try:
                run_id = latest_complete_run(collection, expected_locations)
                due = time.time() - last_training_time >= RETRAIN_SECONDS
                if run_id and run_id != last_trained_run and due:
                    print(f"Retraining from latest complete run {run_id}", flush=True)
                    retrain()
                    last_trained_run = run_id
                    last_training_time = time.time()
                    print("Live CatBoost artifacts updated", flush=True)
            except Exception as error:
                print(f"Live training cycle failed: {error}", file=sys.stderr, flush=True)
            time.sleep(POLL_SECONDS)
    finally:
        client.close()


if __name__ == "__main__":
    main()
