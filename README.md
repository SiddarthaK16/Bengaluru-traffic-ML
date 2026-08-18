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

