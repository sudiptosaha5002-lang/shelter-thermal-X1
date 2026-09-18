"""
ML Training Pipeline
====================
Trains surrogate models to predict thermal performance of shelter assemblies.

Targets:
  1. total_heating_energy_mwh  (regression)
  2. heat_flux_w_m2            (regression)
  3. mean_indoor_temp_c        (regression)
  4. compliance_label           (classification)

Models:
  - Random Forest Regressor / Classifier
  - Gradient Boosting Regressor / Classifier
  - Ridge Regression (baseline)
  - Support Vector Regression (SVR)
  - Multi-output regression for joint prediction

Usage:
  cd backend
  python -m ml.train
"""

import os
import sys
import json
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

from sklearn.model_selection import cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import (
    RandomForestRegressor,
    RandomForestClassifier,
    GradientBoostingRegressor,
    GradientBoostingClassifier,
    AdaBoostRegressor,
    ExtraTreesRegressor,
)
from sklearn.linear_model import Ridge, Lasso, ElasticNet
from sklearn.svm import SVR, SVC
from sklearn.neural_network import MLPRegressor, MLPClassifier
from sklearn.multioutput import MultiOutputRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    mean_absolute_percentage_error,
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    confusion_matrix,
    classification_report,
)
from sklearn.pipeline import Pipeline
import joblib
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.data_generator import generate_training_data, save_dataset, MATERIAL_LIBRARY, REGION_CLIMATES


# ---------------------------------------------------------------------------
# Feature / target definitions
# ---------------------------------------------------------------------------
FEATURE_COLS = [
    "density",
    "specific_heat",
    "thermal_conductivity",
    "emissivity",
    "solar_absorptance",
    "thickness",
    "u_value",
    "thermal_resistance",
    "volumetric_heat_capacity",
    "length",
    "width",
    "height",
    "window_area",
    "glazing_ratio",
    "wall_area",
    "roof_area",
    "total_envelope_area",
    "elevation_m",
    "mean_humidity",
    "mean_wind_speed",
    "mean_solar_radiation",
    "temp_range",
    "freeze_thaw_cycles",
    "snow_depth_max",
    "dust_storm_days",
]

CATEGORICAL_COLS = ["region_key", "material_key"]

REGRESSION_TARGETS = [
    "total_heating_energy_mwh",
    "heat_flux_w_m2",
    "mean_indoor_temp_c",
    "heating_degree_days",
    "peak_heating_w",
    "comfort_ratio",
]

CLASSIFICATION_TARGETS = [
    "compliance_label",
]

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_models")
PLOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plots")


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------
def prepare_data(df: pd.DataFrame):
    """Encode categoricals, split features/targets, return train/val/test."""
    df = df.copy()

    le_dict = {}
    for col in CATEGORICAL_COLS:
        le = LabelEncoder()
        df[col + "_enc"] = le.fit_transform(df[col].astype(str))
        le_dict[col] = le

    feature_cols = FEATURE_COLS + [c + "_enc" for c in CATEGORICAL_COLS]

    splits = {}
    for split_name in ["train", "validation", "test"]:
        mask = df["split"] == split_name
        splits[split_name] = {
            "X": df.loc[mask, feature_cols].values,
            "y_reg": df.loc[mask, REGRESSION_TARGETS].values,
            "y_clf": df.loc[mask, CLASSIFICATION_TARGETS].values.ravel(),
            "df": df.loc[mask],
        }

    scaler = StandardScaler()
    splits["train"]["X"] = scaler.fit_transform(splits["train"]["X"])
    splits["validation"]["X"] = scaler.transform(splits["validation"]["X"])
    splits["test"]["X"] = scaler.transform(splits["test"]["X"])

    return splits, scaler, le_dict, feature_cols


# ---------------------------------------------------------------------------
# Model definitions
# ---------------------------------------------------------------------------
def get_regression_models():
    """Return dict of regression model name -> sklearn estimator."""
    return {
        "Ridge": Ridge(alpha=1.0),
        "Lasso": Lasso(alpha=0.1),
        "ElasticNet": ElasticNet(alpha=0.1, l1_ratio=0.5),
        "RandomForest": RandomForestRegressor(
            n_estimators=200, max_depth=15, min_samples_split=5,
            min_samples_leaf=2, n_jobs=-1, random_state=42,
        ),
        "GradientBoosting": GradientBoostingRegressor(
            n_estimators=200, max_depth=8, learning_rate=0.1,
            subsample=0.8, random_state=42,
        ),
        "AdaBoost": AdaBoostRegressor(
            n_estimators=100, learning_rate=0.1, random_state=42,
        ),
        "ExtraTrees": ExtraTreesRegressor(
            n_estimators=200, max_depth=15, min_samples_split=5,
            n_jobs=-1, random_state=42,
        ),
        "MLP": MLPRegressor(
            hidden_layer_sizes=(256, 128, 64), activation="relu",
            max_iter=500, early_stopping=True, random_state=42,
        ),
    }


def get_classification_models():
    """Return dict of classification model name -> sklearn estimator."""
    return {
        "RandomForest_clf": RandomForestClassifier(
            n_estimators=200, max_depth=12, min_samples_split=5,
            n_jobs=-1, random_state=42,
        ),
        "GradientBoosting_clf": GradientBoostingClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            subsample=0.8, random_state=42,
        ),
        "MLP_clf": MLPClassifier(
            hidden_layer_sizes=(256, 128, 64), activation="relu",
            max_iter=500, early_stopping=True, random_state=42,
        ),
    }


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def train_regression_models(splits: dict):
    """Train all regression models on all targets, return best results."""
    models = get_regression_models()
    train_X = splits["train"]["X"]
    val_X = splits["validation"]["X"]
    test_X = splits["test"]["X"]

    results = {}
    trained_models = {}

    for target_idx, target_name in enumerate(REGRESSION_TARGETS):
        print(f"\n{'='*60}")
        print(f"  TARGET: {target_name}")
        print(f"{'='*60}")

        train_y = splits["train"]["y_reg"][:, target_idx]
        val_y = splits["validation"]["y_reg"][:, target_idx]
        test_y = splits["test"]["y_reg"][:, target_idx]

        best_val_mae = float("inf")
        best_model_name = None

        for model_name, model in models.items():
            t0 = time.time()
            model.fit(train_X, train_y)
            train_time = time.time() - t0

            train_pred = model.predict(train_X)
            val_pred = model.predict(val_X)
            test_pred = model.predict(test_X)

            train_mae = mean_absolute_error(train_y, train_pred)
            val_mae = mean_absolute_error(val_y, val_pred)
            test_mae = mean_absolute_error(test_y, test_pred)
            train_r2 = r2_score(train_y, train_pred)
            val_r2 = r2_score(val_y, val_pred)
            test_r2 = r2_score(test_y, test_pred)
            test_rmse = np.sqrt(mean_squared_error(test_y, test_pred))

            print(f"  {model_name:25s} | Train MAE: {train_mae:10.4f} | Val MAE: {val_mae:10.4f} | "
                  f"Test MAE: {test_mae:10.4f} | R2: {test_r2:.4f} | {train_time:.1f}s")

            if val_mae < best_val_mae:
                best_val_mae = val_mae
                best_model_name = model_name

                results[target_name] = {
                    "model_name": model_name,
                    "train_mae": float(train_mae),
                    "val_mae": float(val_mae),
                    "test_mae": float(test_mae),
                    "test_rmse": float(test_rmse),
                    "test_r2": float(test_r2),
                    "train_r2": float(train_r2),
                    "train_time_s": float(train_time),
                    "feature_importance": None,
                }

                if hasattr(model, "feature_importances_"):
                    results[target_name]["feature_importance"] = model.feature_importances_.tolist()

                trained_models[target_name] = model

        print(f"  >>> Best for {target_name}: {best_model_name}")

    return trained_models, results


def train_classification_models(splits: dict):
    """Train classification models for compliance prediction."""
    models = get_classification_models()
    train_X = splits["train"]["X"]
    val_X = splits["validation"]["X"]
    test_X = splits["test"]["X"]
    train_y = splits["train"]["y_clf"]
    val_y = splits["validation"]["y_clf"]
    test_y = splits["test"]["y_clf"]

    results = {}
    trained_models = {}

    print(f"\n{'='*60}")
    print(f"  TARGET: compliance_label (classification)")
    print(f"{'='*60}")

    best_val_acc = 0
    best_model_name = None

    for model_name, model in models.items():
        t0 = time.time()
        model.fit(train_X, train_y)
        train_time = time.time() - t0

        train_pred = model.predict(train_X)
        val_pred = model.predict(val_X)
        test_pred = model.predict(test_X)

        train_acc = accuracy_score(train_y, train_pred)
        val_acc = accuracy_score(val_y, val_pred)
        test_acc = accuracy_score(test_y, test_pred)
        test_f1 = f1_score(test_y, test_pred, average="weighted", zero_division=0)
        test_prec = precision_score(test_y, test_pred, average="weighted", zero_division=0)
        test_rec = recall_score(test_y, test_pred, average="weighted", zero_division=0)

        print(f"  {model_name:25s} | Train Acc: {train_acc:.4f} | Val Acc: {val_acc:.4f} | "
              f"Test Acc: {test_acc:.4f} | F1: {test_f1:.4f} | {train_time:.1f}s")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_model_name = model_name

            results["compliance_label"] = {
                "model_name": model_name,
                "train_accuracy": float(train_acc),
                "val_accuracy": float(val_acc),
                "test_accuracy": float(test_acc),
                "test_f1": float(test_f1),
                "test_precision": float(test_prec),
                "test_recall": float(test_rec),
                "train_time_s": float(train_time),
                "confusion_matrix": confusion_matrix(test_y, test_pred).tolist(),
                "classification_report": classification_report(test_y, test_pred, zero_division=0),
            }

            if hasattr(model, "feature_importances_"):
                results["compliance_label"]["feature_importance"] = model.feature_importances_.tolist()

            trained_models["compliance_label"] = model

    print(f"  >>> Best for compliance_label: {best_model_name}")
    return trained_models, results


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------
def plot_results(results: dict, trained_models: dict, splits: dict, feature_cols: list):
    """Generate evaluation plots."""
    os.makedirs(PLOT_DIR, exist_ok=True)

    # --- Regression: Actual vs Predicted ---
    n_targets = len(REGRESSION_TARGETS)
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes = axes.ravel()

    test_X = splits["test"]["X"]

    for i, target_name in enumerate(REGRESSION_TARGETS):
        if target_name not in trained_models:
            continue
        model = trained_models[target_name]
        test_y = splits["test"]["y_reg"][:, i]
        pred_y = model.predict(test_X)

        ax = axes[i]
        ax.scatter(test_y, pred_y, alpha=0.3, s=8, c="steelblue")
        lims = [
            min(test_y.min(), pred_y.min()) * 0.9,
            max(test_y.max(), pred_y.max()) * 1.1,
        ]
        ax.plot(lims, lims, "r--", linewidth=1.5, label="Perfect prediction")
        ax.set_xlabel(f"Actual {target_name}")
        ax.set_ylabel(f"Predicted {target_name}")
        ax.set_title(f"{target_name}\nR2={results[target_name]['test_r2']:.4f}, "
                      f"MAE={results[target_name]['test_mae']:.4f}")
        ax.legend(fontsize=8)

    if n_targets < 6:
        axes[-1].axis("off")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, "regression_actual_vs_predicted.png"), dpi=150)
    plt.close()

    # --- Classification: Confusion Matrix ---
    if "compliance_label" in trained_models:
        clf_results = results.get("compliance_label", {})
        cm = np.array(clf_results.get("confusion_matrix", []))
        if cm.size > 0:
            fig, ax = plt.subplots(figsize=(6, 5))
            im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
            ax.figure.colorbar(im, ax=ax)
            ax.set(
                xticks=[0, 1], yticks=[0, 1],
                xticklabels=["Non-compliant", "Compliant"],
                yticklabels=["Non-compliant", "Compliant"],
                ylabel="True label", xlabel="Predicted label",
                title=f"Confusion Matrix — {clf_results.get('model_name', 'N/A')}\n"
                      f"Accuracy={clf_results.get('test_accuracy', 0):.4f}",
            )
            for i in range(cm.shape[0]):
                for j in range(cm.shape[1]):
                    ax.text(j, i, format(cm[i, j], "d"),
                            ha="center", va="center",
                            color="white" if cm[i, j] > cm.max() / 2 else "black")
            plt.tight_layout()
            plt.savefig(os.path.join(PLOT_DIR, "classification_confusion_matrix.png"), dpi=150)
            plt.close()

    # --- Feature Importance ---
    for target_name in REGRESSION_TARGETS:
        if target_name not in results:
            continue
        fi = results[target_name].get("feature_importance")
        if fi is None:
            continue
        fi = np.array(fi)
        top_k = min(20, len(fi))
        indices = np.argsort(fi)[-top_k:]

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(range(top_k), fi[indices], align="center", color="steelblue")
        ax.set_yticks(range(top_k))
        ax.set_yticklabels([feature_cols[j] for j in indices], fontsize=9)
        ax.set_xlabel("Feature Importance")
        ax.set_title(f"Top {top_k} Features — {target_name}\n"
                      f"Model: {results[target_name]['model_name']}")
        plt.tight_layout()
        plt.savefig(os.path.join(PLOT_DIR, f"feature_importance_{target_name}.png"), dpi=150)
        plt.close()

    # --- Region-wise performance ---
    test_df = splits["test"]["df"].copy()
    for target_name in REGRESSION_TARGETS:
        if target_name not in trained_models:
            continue
        model = trained_models[target_name]
        target_idx = REGRESSION_TARGETS.index(target_name)
        test_df[f"pred_{target_name}"] = model.predict(test_X)
        test_df[f"error_{target_name}"] = np.abs(
            test_df[target_name].values - test_df[f"pred_{target_name}"].values
        )

    if REGRESSION_TARGETS:
        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
        axes = axes.ravel()
        for i, target_name in enumerate(REGRESSION_TARGETS):
            if target_name not in trained_models:
                continue
            ax = axes[i]
            region_errors = test_df.groupby("region_key")[f"error_{target_name}"].mean()
            region_errors.plot(kind="bar", ax=ax, color="coral", edgecolor="black")
            ax.set_title(f"MAE by Region — {target_name}")
            ax.set_ylabel("Mean Absolute Error")
            ax.tick_params(axis="x", rotation=45)
        if len(REGRESSION_TARGETS) < 6:
            axes[-1].axis("off")
        plt.tight_layout()
        plt.savefig(os.path.join(PLOT_DIR, "region_wise_mae.png"), dpi=150)
        plt.close()

    # --- Material-wise performance ---
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.ravel()
    for i, target_name in enumerate(REGRESSION_TARGETS):
        if target_name not in trained_models:
            continue
        ax = axes[i]
        mat_errors = test_df.groupby("material_key")[f"error_{target_name}"].mean().sort_values(ascending=True)
        mat_errors.head(15).plot(kind="barh", ax=ax, color="teal", edgecolor="black")
        ax.set_title(f"MAE by Material — {target_name}")
        ax.set_xlabel("Mean Absolute Error")
    if len(REGRESSION_TARGETS) < 6:
        axes[-1].axis("off")
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, "material_wise_mae.png"), dpi=150)
    plt.close()

    # --- Energy distribution by region ---
    fig, ax = plt.subplots(figsize=(12, 6))
    for region in test_df["region_key"].unique():
        mask = test_df["region_key"] == region
        ax.hist(test_df.loc[mask, "total_heating_energy_mwh"], bins=40, alpha=0.5, label=region)
    ax.set_xlabel("Total Heating Energy (MWh)")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of Heating Energy by Region (Test Set)")
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, "energy_distribution_by_region.png"), dpi=150)
    plt.close()

    # --- Sample comparison plot ---
    n_show = 200
    fig, ax = plt.subplots(figsize=(14, 6))
    if "total_heating_energy_mwh" in trained_models:
        test_y = splits["test"]["y_reg"][:, REGRESSION_TARGETS.index("total_heating_energy_mwh")]
        pred_y = trained_models["total_heating_energy_mwh"].predict(test_X)[:n_show]
        x_axis = range(n_show)
        ax.plot(x_axis, test_y[:n_show], "b-", linewidth=1.2, label="Actual", alpha=0.8)
        ax.plot(x_axis, pred_y[:n_show], "r--", linewidth=1.2, label="Predicted", alpha=0.8)
        ax.set_xlabel("Sample Index (Test Set)")
        ax.set_ylabel("Total Heating Energy (MWh)")
        ax.set_title(f"Heating Energy — Actual vs Predicted (first {n_show} test samples)")
        ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, "sample_comparison.png"), dpi=150)
    plt.close()

    print(f"  Plots saved to: {PLOT_DIR}")


# ---------------------------------------------------------------------------
# Model persistence
# ---------------------------------------------------------------------------
def save_models(trained_models: dict, scaler, le_dict, feature_cols: list, results: dict):
    """Save trained models and preprocessing artifacts."""
    os.makedirs(MODEL_DIR, exist_ok=True)

    for target_name, model in trained_models.items():
        safe_name = target_name.replace(" ", "_").replace("/", "_")
        path = os.path.join(MODEL_DIR, f"model_{safe_name}.joblib")
        joblib.dump(model, path)
        print(f"  Saved: {path}")

    joblib.dump(scaler, os.path.join(MODEL_DIR, "scaler.joblib"))
    joblib.dump(le_dict, os.path.join(MODEL_DIR, "label_encoders.joblib"))
    joblib.dump(feature_cols, os.path.join(MODEL_DIR, "feature_columns.joblib"))

    results_path = os.path.join(MODEL_DIR, "training_results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"  Saved: {results_path}")


# ---------------------------------------------------------------------------
# Cross-validation for best model
# ---------------------------------------------------------------------------
def cross_validate_best(splits: dict, results: dict, feature_cols: list):
    """Run 5-fold cross-validation on the best model for each target."""
    print(f"\n{'='*60}")
    print(f"  5-FOLD CROSS-VALIDATION (Best Models)")
    print(f"{'='*60}")

    all_X = np.vstack([
        splits["train"]["X"],
        splits["validation"]["X"],
        splits["test"]["X"],
    ])

    cv_results = {}

    for target_idx, target_name in enumerate(REGRESSION_TARGETS):
        if target_name not in results:
            continue
        model_name = results[target_name]["model_name"]
        all_y = np.concatenate([
            splits["train"]["y_reg"][:, target_idx],
            splits["validation"]["y_reg"][:, target_idx],
            splits["test"]["y_reg"][:, target_idx],
        ])

        from sklearn.model_selection import KFold
        models = get_regression_models()
        model = models[model_name]

        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        scores = cross_val_score(model, all_X, all_y, cv=kf, scoring="neg_mean_absolute_error", n_jobs=-1)
        mae_scores = -scores

        r2_scores = cross_val_score(model, all_X, all_y, cv=kf, scoring="r2", n_jobs=-1)

        cv_results[target_name] = {
            "model": model_name,
            "mae_mean": float(mae_scores.mean()),
            "mae_std": float(mae_scores.std()),
            "r2_mean": float(r2_scores.mean()),
            "r2_std": float(r2_scores.std()),
        }
        print(f"  {target_name:30s} | MAE: {mae_scores.mean():.4f} ± {mae_scores.std():.4f} | "
              f"R2: {r2_scores.mean():.4f} ± {r2_scores.std():.4f}")

    if "compliance_label" in results:
        model_name = results["compliance_label"]["model_name"]
        all_y = np.concatenate([
            splits["train"]["y_clf"],
            splits["validation"]["y_clf"],
            splits["test"]["y_clf"],
        ])
        models = get_classification_models()
        model = models[model_name]
        from sklearn.model_selection import KFold
        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        acc_scores = cross_val_score(model, all_X, all_y, cv=kf, scoring="accuracy", n_jobs=-1)
        cv_results["compliance_label"] = {
            "model": model_name,
            "accuracy_mean": float(acc_scores.mean()),
            "accuracy_std": float(acc_scores.std()),
        }
        print(f"  {'compliance_label':30s} | Acc: {acc_scores.mean():.4f} ± {acc_scores.std():.4f}")

    return cv_results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 72)
    print("  Shelter Thermal Optimizer — ML Training Pipeline")
    print("  Models: RF, GBR, Ridge, SVR, MLP, AdaBoost, ExtraTrees")
    print("  Targets: Energy, Heat Flux, Indoor Temp, Compliance")
    print("=" * 72)

    # 1. Generate data
    print("\n[1/6] Generating training data from thermal engine...")
    df = generate_training_data(max_samples_per_region=3000)
    csv_path, parquet_path = save_dataset(df)

    # 2. Prepare data
    print("\n[2/6] Preparing features and targets...")
    splits, scaler, le_dict, feature_cols = prepare_data(df)
    print(f"  Feature dimensions: {splits['train']['X'].shape}")

    # 3. Train regression models
    print("\n[3/6] Training regression models...")
    reg_models, reg_results = train_regression_models(splits)

    # 4. Train classification models
    print("\n[4/6] Training classification models...")
    clf_models, clf_results = train_classification_models(splits)

    # Merge results
    all_results = {**reg_results, **clf_results}
    all_models = {**reg_models, **clf_models}

    # 5. Cross-validation
    print("\n[5/6] Cross-validating best models...")
    cv_results = cross_validate_best(splits, all_results, feature_cols)
    all_results["cross_validation"] = cv_results

    # 6. Visualize
    print("\n[6/6] Generating evaluation plots...")
    plot_results(all_results, all_models, splits, feature_cols)

    # Save models
    print("\n  Saving models and artifacts...")
    save_models(all_models, scaler, le_dict, feature_cols, all_results)

    # Summary
    print("\n" + "=" * 72)
    print("  TRAINING COMPLETE")
    print("=" * 72)
    print(f"\n  Models saved to:  {MODEL_DIR}")
    print(f"  Plots saved to:   {PLOT_DIR}")
    print(f"  Dataset saved to: {csv_path}")

    print(f"\n  Best regression models:")
    for t in REGRESSION_TARGETS:
        if t in all_results:
            r = all_results[t]
            print(f"    {t:30s} -> {r['model_name']:20s} | R2={r['test_r2']:.4f} | MAE={r['test_mae']:.4f}")

    if "compliance_label" in all_results:
        r = all_results["compliance_label"]
        print(f"\n  Best classification model:")
        print(f"    {'compliance_label':30s} -> {r['model_name']:20s} | Acc={r['test_accuracy']:.4f}")

    print("\n" + "=" * 72)
    return all_models, all_results


if __name__ == "__main__":
    main()
