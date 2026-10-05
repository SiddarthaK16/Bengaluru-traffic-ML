import time
from pathlib import Path
import yaml

from dataclasses import asdict

from src.data_collection.traffic_collector import TrafficCollector
from src.database.mongo_client import MongoDBClient
from src.logging.logger import logging


COLLECTION_INTERVAL = 15 * 60
ROOT = Path(__file__).resolve().parents[1]


def collect_and_store(collector, mongo_client, locations):

    try:
        results = collector.collect_all(locations)

        documents = [asdict(entity) for entity in results]

        mongo_client.insert_many(documents)

        print(
            f"✓ {len(documents)} traffic records inserted"
        )

        logging.info(
            f"Collection cycle completed: {len(documents)} records"
        )

    except Exception as e:
        logging.error("Traffic collection cycle failed")
        print(f"Collection failed: {e}")


if __name__ == "__main__":
    with (ROOT / "src" / "constant" / "locations.yaml").open() as file:
        locations = yaml.safe_load(file)["locations"]

    collector = TrafficCollector()
    mongo_client = MongoDBClient()
    try:
        while True:
            collect_and_store(collector, mongo_client, locations)
            print("Sleeping for 15 minutes...")
            time.sleep(COLLECTION_INTERVAL)
    except KeyboardInterrupt:
        print("Stopping traffic collector...")
    finally:
        mongo_client.close()
