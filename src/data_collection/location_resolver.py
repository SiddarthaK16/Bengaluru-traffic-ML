import os
import sys

import requests
from dotenv import load_dotenv

from src.logging.logger import logging
from src.exception.exception import CustomException


load_dotenv()


class LocationResolver:

    def __init__(self):
        try:
            self.api_key = os.getenv("TOMTOM_SEARCH_API_KEY")

            if not self.api_key:
                raise ValueError("TOMTOM_SEARCH_API_KEY is not set")

            self.base_url = (
                "https://api.tomtom.com/search/2/search/"
            )

            logging.info(
                "LocationResolver initialized successfully"
            )

        except Exception as e:
            logging.error(
                "Error while initializing LocationResolver"
            )
            raise CustomException(e, sys)

    def search_location(self, location: str) -> dict:

        try:
            query = location
            
            

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
                f"Successfully searched location: {location}"
            )

            return data

        except Exception as e:

            logging.error(
                f"Error while searching location: {location}"
            )

            raise CustomException(e, sys)