import os
import sys

import requests
from dotenv import load_dotenv

from src.logging.logger import logging
from src.exception.exception import CustomException


load_dotenv()


class GeocodingClient:

    def __init__(self):
        try:
            self.api_key = os.getenv("TOMTOM_GC_API_KEY")

            if not self.api_key:
                raise ValueError("TOMTOM_GC_API_KEY is not set")

            self.base_url = (
                "https://api.tomtom.com/search/2/geocode/"
            )

            logging.info(
                "GeocodingClient initialized successfully"
            )

        except Exception as e:
            logging.error(
                "Error while initializing GeocodingClient"
            )
            raise CustomException(e, sys)

    def _format_location_name(self, location: str) -> str:
        return location.replace("_", " ").title()

    def geocode(self, location: str) -> dict:

        try:
            formatted_location = self._format_location_name(
                location
            )

            query = (
                f"{formatted_location} Junction, "
                "Bengaluru, Karnataka, India"
            )

            url = f"{self.base_url}{query}.json"

            params = {
                "key": self.api_key,
                "limit": 5,
                "countrySet": "IN",
                "language": "en-US",
            }

            response = requests.get(
                url,
                params=params,
                timeout=10,
            )

            response.raise_for_status()

            data = response.json()

            logging.info(
                f"Successfully geocoded: {location}"
            )

            return data

        except Exception as e:

            logging.error(
                f"Error while geocoding: {location}"
            )

            raise CustomException(e, sys)