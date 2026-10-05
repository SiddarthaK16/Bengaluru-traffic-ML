"""Compare local-history and cross-location CatBoost traffic forecasts."""

from datetime import datetime
import csv
import json
import os
from pathlib import Path

import numpy as np
from catboost import CatBoostRegressor, Pool


ROOT = Path(__file__).resolve().parents[1]
PANEL_PATH = ROOT / "data" / "processed" / "traffic_panel.csv"
ARTIFACT_DIR = ROOT / "artifacts"
LOOKBACK = 4
HOLDOUT_FRACTION = 0.2
VALIDATION_FRACTION = 0.1
MAX_ITERATIONS = 1200
EARLY_STOPPING_ROUNDS = 100
RANDOM_SEED = 42


def time_features(timestamp):
    hour = timestamp.hour + timestamp.minute / 60 + timestamp.second / 3600
    day_phase = (timestamp.weekday() + hour / 24) / 7
    return {
        "target_hour_sin": float(np.sin(2 * np.pi * hour / 24)),
        "target_hour_cos": float(np.cos(2 * np.pi * hour / 24)),
        "target_week_sin": float(np.sin(2 * np.pi * day_phase)),
        "target_week_cos": float(np.cos(2 * np.pi * day_phase)),
    }


def read_panel():
    if not PANEL_PATH.exists():
        raise SystemExit(
            f"Panel not found at {PANEL_PATH}. Run script/prepare_traffic_panel.py first."
        )
    with PANEL_PATH.open(newline="") as input_file:
        rows = list(csv.DictReader(input_file))
    if not rows:
        raise SystemExit("The prepared traffic panel is empty.")
    return sorted(rows, key=lambda row: datetime.fromisoformat(row["timestamp"]))


def build_samples(rows):
    ratio_columns = [
        column for column in rows[0]
        if column.startswith("congestion_ratio_")
    ]
    locations = [column.removeprefix("congestion_ratio_") for column in ratio_columns]
    segments = {}
    for row in rows:
        segments.setdefault(row["segment_id"], []).append(row)

    examples = []
    for segment_rows in segments.values():
        segment_rows.sort(key=lambda row: datetime.fromisoformat(row["timestamp"]))
        for index in range(LOOKBACK - 1, len(segment_rows) - 1):
            observation = segment_rows[index]
            target_row = segment_rows[index + 1]
            target_time = datetime.fromisoformat(target_row["timestamp"])
            context_features = time_features(target_time)

            for column in ratio_columns:
                location = column.removeprefix("congestion_ratio_")
                own_history = [
                    segment_rows[index - lag].get(column, "")
                    for lag in range(LOOKBACK)
                ]
                target_value = target_row.get(column, "")
                if any(value == "" for value in own_history) or target_value == "":
                    continue

                base_features = {
                    "location": location,
                    **{
                        f"lag_{lag}": float(own_history[lag])
                        for lag in range(LOOKBACK)
                    },
                    **context_features,
                }
                network_features = {}
                for other_column in ratio_columns:
                    other_location = other_column.removeprefix("congestion_ratio_")
                    observed = observation.get(other_column, "")
                    if other_column == column or observed == "":
                        network_features[f"current_{other_location}"] = float("nan")
                    else:
                        network_features[f"current_{other_location}"] = float(observed)

                examples.append(
                    {
                        "timestamp": target_time,
                        "location": location,
                        "target": float(target_value),
                        "persistence": float(own_history[0]),
                        "local_features": base_features,
                        "network_features": {**base_features, **network_features},
                    }
                )

    return locations, examples


def chronological_cutoff(examples, fraction):
    timestamps = sorted(example["timestamp"] for example in examples)
    if len(timestamps) < 3:
        raise SystemExit("Not enough examples for chronological train/validation/holdout splits.")
    index = min(int(len(timestamps) * fraction), len(timestamps) - 1)
    return timestamps[index]


def make_pool(examples, indices, feature_names, feature_key):
    rows = [
        [examples[index][feature_key][name] for name in feature_names]
        for index in indices
    ]
    targets = [examples[index]["target"] for index in indices]
    return Pool(
        rows,
        label=targets,
        cat_features=["location"],
        feature_names=feature_names,
    )


def regression_metrics(actual, predicted):
    errors = np.asarray(predicted, dtype=float) - np.asarray(actual, dtype=float)
    return {
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(errors**2))),
    }


def evaluate_variant(name, feature_key, examples, train_indices, test_indices, feature_names):
    train_cutoff = chronological_cutoff(
        [examples[index] for index in train_indices], 1 - VALIDATION_FRACTION
    )
    fit_indices = [
        index for index in train_indices
        if examples[index]["timestamp"] < train_cutoff
    ]
    validation_indices = [
        index for index in train_indices
        if examples[index]["timestamp"] >= train_cutoff
    ]
    if not fit_indices or not validation_indices or not test_indices:
        raise SystemExit("Not enough data in a temporal train/validation/holdout split.")

    fit_pool = make_pool(examples, fit_indices, feature_names, feature_key)
    validation_pool = make_pool(examples, validation_indices, feature_names, feature_key)

    selection_model = CatBoostRegressor(
        iterations=MAX_ITERATIONS,
        depth=6,
        learning_rate=0.03,
        loss_function="RMSE",
        eval_metric="RMSE",
        l2_leaf_reg=5.0,
        random_seed=RANDOM_SEED,
        allow_writing_files=False,
        verbose=False,
    )
    selection_model.fit(
        fit_pool,
        eval_set=validation_pool,
        early_stopping_rounds=EARLY_STOPPING_ROUNDS,
        verbose=False,
    )
    best_iterations = max(1, selection_model.get_best_iteration() + 1)

    train_pool = make_pool(examples, train_indices, feature_names, feature_key)
    holdout_pool = make_pool(examples, test_indices, feature_names, feature_key)
    evaluation_model = CatBoostRegressor(
        iterations=best_iterations,
        depth=6,
        learning_rate=0.03,
        loss_function="RMSE",
        l2_leaf_reg=5.0,
        random_seed=RANDOM_SEED,
        allow_writing_files=False,
        verbose=False,
    )
    evaluation_model.fit(train_pool, verbose=False)
    predicted = evaluation_model.predict(holdout_pool)
    actual = [examples[index]["target"] for index in test_indices]
    persistence = [examples[index]["persistence"] for index in test_indices]
    metrics = {
        "catboost": regression_metrics(actual, predicted),
        "persistence": regression_metrics(actual, persistence),
        "samples": len(test_indices),
        "selected_iterations": best_iterations,
    }

    final_pool = make_pool(
        examples, list(range(len(examples))), feature_names, feature_key
    )
    final_model = CatBoostRegressor(
        iterations=best_iterations,
        depth=6,
        learning_rate=0.03,
        loss_function="RMSE",
        l2_leaf_reg=5.0,
        random_seed=RANDOM_SEED,
        allow_writing_files=False,
        verbose=False,
    )
    final_model.fit(final_pool, verbose=False)
    model_path = ARTIFACT_DIR / f"traffic_catboost_{name}.cbm"
    temporary_model_path = model_path.with_suffix(".cbm.tmp")
    final_model.save_model(temporary_model_path, format="cbm")
    os.replace(temporary_model_path, model_path)
    return metrics, best_iterations, model_path


def main():
    locations, examples = build_samples(read_panel())
    if len(examples) < 20:
        raise SystemExit("Not enough valid samples to train CatBoost models.")

    holdout_cutoff = chronological_cutoff(examples, 1 - HOLDOUT_FRACTION)
    train_indices = [
        index for index, example in enumerate(examples)
        if example["timestamp"] < holdout_cutoff
    ]
    test_indices = [
        index for index, example in enumerate(examples)
        if example["timestamp"] >= holdout_cutoff
    ]

    base_feature_names = [
        "location",
        *(f"lag_{lag}" for lag in range(LOOKBACK)),
        "target_hour_sin",
        "target_hour_cos",
        "target_week_sin",
        "target_week_cos",
    ]
    network_feature_names = [
        *base_feature_names,
        *(f"current_{location}" for location in locations),
    ]

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Chronological holdout begins: {holdout_cutoff}")
    print(f"Training examples: {len(train_indices)} | holdout examples: {len(test_indices)}")
    results = {}
    for name, feature_key, feature_names in (
        ("local", "local_features", base_feature_names),
        ("network", "network_features", network_feature_names),
    ):
        metrics, iterations, model_path = evaluate_variant(
            name, feature_key, examples, train_indices, test_indices, feature_names
        )
        results[name] = metrics
        print(
            f"{name.title()} CatBoost: MAE {metrics['catboost']['mae']:.4f}, "
            f"RMSE {metrics['catboost']['rmse']:.4f} | "
            f"persistence MAE {metrics['persistence']['mae']:.4f}, "
            f"RMSE {metrics['persistence']['rmse']:.4f} | "
            f"iterations {iterations} | saved {model_path}"
        )

    metadata = {
        "target": "next_reading_congestion_ratio",
        "nominal_horizon_minutes": 15,
        "lookback_readings": LOOKBACK,
        "locations": locations,
        "holdout_cutoff": holdout_cutoff.isoformat(sep=" "),
        "trained_through": max(example["timestamp"] for example in examples).isoformat(sep=" "),
        "holdout_results": results,
        "variants": {
            "local": "target location history, location category, and target time features",
            "network": "local features plus contemporaneous readings at other monitored points",
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    metadata_path = ARTIFACT_DIR / "traffic_catboost_comparison.json"
    temporary_metadata_path = metadata_path.with_suffix(".json.tmp")
    temporary_metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    os.replace(temporary_metadata_path, metadata_path)
    print(f"Saved comparison metadata: {metadata_path}")


if __name__ == "__main__":
    main()
