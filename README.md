# 🚦 Bengaluru Traffic ML

An end-to-end Machine Learning project for collecting, storing, analyzing, and eventually predicting traffic conditions across major traffic hotspots in Bengaluru.

The project is being built from scratch with a focus on **modular architecture, real-world data collection, API integration, data engineering, and Machine Learning deployment**.

> 🚧 **Status:** In Development

---

## 📌 Project Overview

Traffic congestion in Bengaluru varies significantly based on:

- Location
- Time of day
- Day of the week
- Traffic speed
- Free-flow speed
- Travel time
- Road conditions
- Weather conditions

Instead of relying on an existing dataset, this project aims to **build a custom Bengaluru traffic dataset from live external data sources**.

The system will periodically collect traffic observations from selected Bengaluru hotspots, store them in MongoDB Atlas, process the collected data, and eventually train an ML model to predict traffic conditions.

---

## 🎯 Objectives

- Collect real-world traffic data from Bengaluru
- Integrate external APIs for traffic and location data
- Build a reusable data collection pipeline
- Store collected observations in MongoDB Atlas
- Perform data validation and preprocessing
- Engineer meaningful traffic-related features
- Train and evaluate Machine Learning models
- Build an end-to-end ML pipeline
- Containerize the application using Docker
- Eventually expose predictions through an API

---

## 🗺️ Data Collection

The project currently focuses on traffic hotspots distributed across Bengaluru.

### Initial Monitoring Locations

- Yeshwanthpur
- Hebbal
- Yelahanka
- Madavara
- Kengeri
- Indiranagar
- KR Puram
- Koramangala
- Silk Board
- Electronic City
- Chandapura
- Jayanagar
- Bellandur
- Whitefield
- Malleshwaram
- Fraser Town
- Konanakunte
- Peenya

Coordinates for these locations will be resolved and validated during the data collection setup.

---

## 📊 Data and Forecasting

The target is an interactive Bengaluru map where a user selects an origin and destination and receives a future traffic forecast for that trip. The current collector samples 18 fixed road points every 15 minutes, so the first forecasting milestone is a reliable history and a forecast for monitored locations. Route-level forecasts for arbitrary points will need route and road-segment traffic data in a later phase.

Use `python script/inspect_traffic_data.py` to review collection coverage and `python script/prepare_traffic_panel.py` to export the historical feature table to `data/processed/traffic_panel.csv`. Both scripts read from MongoDB; configure `MONGO_DB_URL` in a local `.env` file before running them. The collector writes new records with a location name, a shared collection-run ID, and a UTC timestamp.

The committed LSTM baseline is in `artifacts/traffic_lstm_model.keras`, with its chronological holdout scores in `artifacts/traffic_lstm_model.json`. Run `python script/train_traffic_model.py` to train the next candidate, a pooled TensorFlow GRU for the next monitored reading (about 15 minutes ahead). It uses the same chronological train/validation/holdout split and persistence comparison, trains for up to 100 epochs with early stopping, and writes `artifacts/traffic_gru_model.keras` plus its metadata. Install its dependencies with `python -m pip install -r requirements-model.txt`. Use Python 3.12 for model training; TensorFlow's current pip support does not include this workspace's Python 3.14 environment. The point-level models do not yet forecast travel time for arbitrary routes.

## 🗺️ Live Map

The web app displays the newest stored readings for the 18 monitored locations and lets a user select any two points within Bengaluru. It refreshes readings from MongoDB once a minute. Trip routing and scheduled departure ETAs use TomTom's Routing API with traffic enabled; this is a traffic-aware routing estimate, while the project's learned model currently forecasts monitored points only.

Create `.env` from `.env.example`, then start both the web API and the continuous collector:

```bash
docker compose up --build
```

Open `http://localhost:8000`. The collector runs as a separate service and stores a collection every 15 minutes. The web service exposes `/api/health`, `/api/locations`, `/api/traffic/latest`, and `/api/route`. Keep the MongoDB URI and TomTom key in `.env`; the route key stays on the server.

GitHub Actions runs syntax checks and builds the Docker image on pushes and pull requests to `main`. A deployment target is still needed to add an automated deploy step.

## 🔌 Data Sources

### Traffic Data

Traffic information is collected using the **TomTom Traffic API**.

The API provides information such as:

- Current speed
- Free-flow speed
- Current travel time
- Free-flow travel time
- Confidence
- Road closure status
- Functional Road Class (FRC)
- Road segment coordinates

### Location Resolution

TomTom Search APIs are used during the initial location-resolution stage to identify suitable coordinates for the selected Bengaluru hotspots.

> Location resolution is performed during setup. The traffic collector will use the validated coordinates instead of repeatedly geocoding locations.

### Weather Data

Weather data will be integrated later as an additional feature source.

This will allow the project to study relationships between:

**Traffic + Weather + Time + Location**
