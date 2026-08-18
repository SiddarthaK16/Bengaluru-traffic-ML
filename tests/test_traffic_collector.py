import yaml

from src.data_collection.traffic_collector import TrafficCollector


with open("src/constant/locations.yaml", "r") as file:
    config = yaml.safe_load(file)

locations = config["locations"]

collector = TrafficCollector()

results = collector.collect_all(locations)

print("\n" + "=" * 60)
print(f"TOTAL RECORDS COLLECTED: {len(results)}")
print("=" * 60)