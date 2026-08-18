import sys

from src.logging.logger import logging
from src.exception.exception import CustomException
from src.data_collection.traffic_client import TrafficClient
from src.entity.traffic_entity import TrafficEntity


class TrafficCollector:

    def __init__(self):
        try:
            self.traffic_client = TrafficClient()

            logging.info("TrafficCollector initialized successfully")

        except Exception as e:
            
            raise CustomException(e, sys)

    def collect_location(
        self,
        location_name: str,
        latitude: float,
        longitude: float
    ) -> TrafficEntity:

        try:
            data = self.traffic_client.get_traffic(
                latitude=latitude,
                longitude=longitude
            )

            flow_data = data["flowSegmentData"]

            entity = TrafficEntity(
                latitude=latitude,
                longitude=longitude,
                currentSpeed=flow_data["currentSpeed"],
                freeFlowSpeed=flow_data["freeFlowSpeed"],
                currentTravelTime=flow_data["currentTravelTime"],
                freeFlowTravelTime=flow_data["freeFlowTravelTime"],
                confidence=flow_data["confidence"],
                roadClosure=flow_data["roadClosure"],
                frc=flow_data["frc"],
                timestamp=__import__("datetime").datetime.now()
            )

            logging.info(
                f"Traffic collected successfully for {location_name}"
            )

            return entity

        except Exception as e:
            
            raise CustomException(e, sys)

    def collect_all(self, locations: dict):

        try:
            results = []

            for location_name, coordinates in locations.items():

                entity = self.collect_location(
                    location_name=location_name,
                    latitude=coordinates["latitude"],
                    longitude=coordinates["longitude"]
                )

                results.append(entity)

                print(
                    f"{location_name}: "
                    f"{entity.currentSpeed} km/h | "
                    f"Free flow: {entity.freeFlowSpeed} km/h"
                )

            logging.info(
                f"Collected traffic data for {len(results)} locations"
            )

            return results

        except Exception as e:
            
            raise CustomException(e, sys)