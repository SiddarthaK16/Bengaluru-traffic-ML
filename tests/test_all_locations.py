import yaml

from src.data_collection.location_resolver import LocationResolver


resolver = LocationResolver()

with open("src/constant/locations.yaml", "r") as file:
    config = yaml.safe_load(file)

locations = config["locations"]


for location in locations:

    print("\n" + "=" * 70)
    print(f"LOCATION: {location}")
    print("=" * 70)

    data = resolver.search_location(location)

    results = data.get("results", [])

    for i, result in enumerate(results, start=1):

        address = result.get("address", {})
        position = result.get("position", {})

        print(f"\n[{i}]")
        print("Type:", result.get("type"))
        print("Address:", result.get("address", {}).get("freeformAddress"))
        print("Lat:", position.get("lat"))
        print("Lon:", position.get("lon"))