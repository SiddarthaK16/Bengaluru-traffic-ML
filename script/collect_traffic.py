import time
import yaml

from dataclasses import asdict

from src.data_collection.traffic_collector import TrafficCollector
from src.database.mongo_client import MongoDBClient
from src.logging.logger import logging


COLLECTION_INTERVAL = 15 * 60


def collect_and_store():

    try:
        with open("src/constant/locations.yaml", "r") as file:
            config = yaml.safe_load(file)

        locations = config["locations"]

        collector = TrafficCollector()
        mongo_client = MongoDBClient()

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

    while True:

        collect_and_store()

        print("Sleeping for 15 minutes...")

        time.sleep(COLLECTION_INTERVAL)