from src.data_collection.location_resolver import LocationResolver


resolver = LocationResolver()

data = resolver.search_location(
    "Silk Board Junction"
)

for result in data.get("results", []):

    print("\n-----------------------------")

    print("Type:", result.get("type"))

    print("Address:")
    print(
        result.get("address", {}).get(
            "freeformAddress"
        )
    )

    print("Position:")
    print(
        result.get("position")
    )