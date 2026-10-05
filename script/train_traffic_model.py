"""Train and evaluate a pooled TensorFlow LSTM for the next traffic reading."""

import csv
from datetime import datetime
import json
from pathlib import Path

import numpy as np
import tensorflow as tf


ROOT = Path(__file__).resolve().parents[1]
PANEL_PATH = ROOT / "data" / "processed" / "traffic_panel.csv"
MODEL_PATH = ROOT / "artifacts" / "traffic_lstm_model.keras"
METADATA_PATH = ROOT / "artifacts" / "traffic_lstm_model.json"
LOOKBACK = 4
HOLDOUT_FRACTION = 0.2
MAX_EPOCHS = 100
BATCH_SIZE = 64
RANDOM_SEED = 42


def time_features(timestamp):
    hour = timestamp.hour + timestamp.minute / 60 + timestamp.second / 3600
    day_phase = (timestamp.weekday() + hour / 24) / 7
    return [
        np.sin(2 * np.pi * hour / 24),
        np.cos(2 * np.pi * hour / 24),
        np.sin(2 * np.pi * day_phase),
        np.cos(2 * np.pi * day_phase),
    ]


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

    timestamps = []
    location_indices = []
    histories = []
    contexts = []
    targets = []
    persistence = []

    for segment_rows in segments.values():
        segment_rows.sort(key=lambda row: datetime.fromisoformat(row["timestamp"]))
        for index in range(LOOKBACK - 1, len(segment_rows) - 1):
            target_row = segment_rows[index + 1]
            target_time = datetime.fromisoformat(target_row["timestamp"])
            for location_index, column in enumerate(ratio_columns):
                values = [
                    segment_rows[position][column]
                    for position in range(index - LOOKBACK + 1, index + 1)
                ]
                target = target_row[column]
                if any(value == "" for value in values) or target == "":
                    continue

                location_vector = np.zeros(len(locations), dtype=np.float32)
                location_vector[location_index] = 1.0
                context = np.concatenate(
                    (location_vector, np.asarray(time_features(target_time), dtype=np.float32))
                )
                histories.append(np.asarray(values, dtype=np.float32).reshape(LOOKBACK, 1))
                contexts.append(context)
                targets.append(float(target))
                persistence.append(float(values[-1]))
                timestamps.append(target_time)
                location_indices.append(location_index)

    return {
        "locations": locations,
        "timestamps": np.asarray(timestamps, dtype=object),
        "location_indices": np.asarray(location_indices, dtype=np.int32),
        "histories": np.asarray(histories, dtype=np.float32),
        "contexts": np.asarray(contexts, dtype=np.float32),
        "targets": np.asarray(targets, dtype=np.float32),
        "persistence": np.asarray(persistence, dtype=np.float32),
    }


def make_model(location_count):
    history_input = tf.keras.Input(shape=(LOOKBACK, 1), name="traffic_history")
    context_input = tf.keras.Input(shape=(location_count + 4,), name="location_and_time")

    sequence = tf.keras.layers.LSTM(32, dropout=0.1, name="traffic_lstm")(history_input)
    combined = tf.keras.layers.Concatenate()([sequence, context_input])
    hidden = tf.keras.layers.Dense(16, activation="relu")(combined)
    output = tf.keras.layers.Dense(1, name="next_congestion_ratio")(hidden)

    model = tf.keras.Model(
        inputs={"traffic_history": history_input, "location_and_time": context_input},
        outputs=output,
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss="mse",
        metrics=["mae"],
    )
    return model


def model_inputs(samples, indices):
    return {
        "traffic_history": samples["histories"][indices],
        "location_and_time": samples["contexts"][indices],
    }


def score(actual, predicted):
    errors = np.asarray(predicted).reshape(-1) - np.asarray(actual).reshape(-1)
    return {
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(errors**2))),
    }


def chronological_partition(timestamps, fraction):
    ordered = sorted(timestamps)
    cutoff_index = min(int(len(ordered) * fraction), len(ordered) - 1)
    return ordered[cutoff_index]


def main():
    tf.keras.utils.set_random_seed(RANDOM_SEED)
    try:
        tf.config.experimental.enable_op_determinism()
    except AttributeError:
        pass

    samples = build_samples(read_panel())
    if len(samples["targets"]) < 20:
        raise SystemExit("Not enough valid lookback windows to train an LSTM.")

    holdout_cutoff = chronological_partition(
        samples["timestamps"], 1 - HOLDOUT_FRACTION
    )
    train_indices = np.flatnonzero(samples["timestamps"] < holdout_cutoff)
    test_indices = np.flatnonzero(samples["timestamps"] >= holdout_cutoff)
    validation_cutoff = chronological_partition(
        samples["timestamps"][train_indices], 0.9
    )
    fit_indices = train_indices[
        samples["timestamps"][train_indices] < validation_cutoff
    ]
    validation_indices = train_indices[
        samples["timestamps"][train_indices] >= validation_cutoff
    ]
    if min(len(fit_indices), len(validation_indices), len(test_indices)) == 0:
        raise SystemExit("Not enough data for chronological train/validation/holdout splits.")

    print(f"Chronological holdout begins: {holdout_cutoff}")
    print(f"Temporal validation begins: {validation_cutoff}")
    print(f"Lookback: {LOOKBACK} readings (~{LOOKBACK * 15} minutes)")
    print(f"Training sequences: {len(fit_indices)} | holdout sequences: {len(test_indices)}")

    selection_model = make_model(len(samples["locations"]))
    early_stopping = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=12,
        min_delta=1e-5,
        restore_best_weights=True,
    )
    history = selection_model.fit(
        model_inputs(samples, fit_indices),
        samples["targets"][fit_indices],
        validation_data=(
            model_inputs(samples, validation_indices),
            samples["targets"][validation_indices],
        ),
        epochs=MAX_EPOCHS,
        batch_size=BATCH_SIZE,
        shuffle=True,
        callbacks=[early_stopping],
        verbose=0,
    )
    best_epoch = int(np.argmin(history.history["val_loss"]) + 1)
    print(f"Selected training epochs from temporal validation: {best_epoch} / {MAX_EPOCHS}")

    evaluation_model = make_model(len(samples["locations"]))
    evaluation_model.fit(
        model_inputs(samples, train_indices),
        samples["targets"][train_indices],
        epochs=best_epoch,
        batch_size=BATCH_SIZE,
        shuffle=True,
        verbose=0,
    )
    predicted = evaluation_model.predict(
        model_inputs(samples, test_indices), batch_size=BATCH_SIZE, verbose=0
    ).reshape(-1)
    actual = samples["targets"][test_indices]
    persistence = samples["persistence"][test_indices]
    location_indices = samples["location_indices"][test_indices]

    print("Per-location holdout metrics (congestion ratio units):")
    for location_index, location in enumerate(samples["locations"]):
        mask = location_indices == location_index
        if not np.any(mask):
            continue
        print(
            f"  {location}: n={int(mask.sum()):3d} | "
            f"persistence MAE {score(actual[mask], persistence[mask])['mae']:.4f}, "
            f"RMSE {score(actual[mask], persistence[mask])['rmse']:.4f} | "
            f"LSTM MAE {score(actual[mask], predicted[mask])['mae']:.4f}, "
            f"RMSE {score(actual[mask], predicted[mask])['rmse']:.4f}"
        )

    holdout_metrics = {
        "persistence": score(actual, persistence),
        "lstm": score(actual, predicted),
        "samples": int(len(test_indices)),
    }
    print("Overall holdout:")
    print(f"  persistence: {holdout_metrics['persistence']}")
    print(f"  LSTM:        {holdout_metrics['lstm']}")

    # Refit on all available sequences using the epoch count selected above.
    final_model = make_model(len(samples["locations"]))
    final_model.fit(
        model_inputs(samples, np.arange(len(samples["targets"]))),
        samples["targets"],
        epochs=best_epoch,
        batch_size=BATCH_SIZE,
        shuffle=True,
        verbose=0,
    )
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    final_model.save(MODEL_PATH)

    metadata = {
        "model_type": "TensorFlow Keras LSTM",
        "target": "next_reading_congestion_ratio",
        "nominal_horizon_minutes": 15,
        "lookback_readings": LOOKBACK,
        "max_epochs": MAX_EPOCHS,
        "selected_epochs": best_epoch,
        "batch_size": BATCH_SIZE,
        "features": [
            "four chronological congestion ratios",
            "one-hot monitored location",
            "target hour and weekday cycles",
        ],
        "locations": samples["locations"],
        "holdout_cutoff": holdout_cutoff.isoformat(sep=" "),
        "trained_through": max(samples["timestamps"]).isoformat(sep=" "),
        "holdout_metrics": holdout_metrics,
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Saved Keras model: {MODEL_PATH}")
    print(f"Saved model metadata: {METADATA_PATH}")


if __name__ == "__main__":
    main()
