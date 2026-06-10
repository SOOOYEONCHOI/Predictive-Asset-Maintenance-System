import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import average_precision_score, mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_CSV = BACKEND_DIR / "data" / "augmented" / "TB_SNSR_AUGMENTED.csv"
MODEL_DIR = BACKEND_DIR / "data" / "model_registry"

UCL = {
    "ACC": {"mean": 5.440, "std": 4.676, "1s": 10.116, "2s": 14.792, "3s": 19.469},
    "ENV": {"mean": 4.137, "std": 3.772, "1s": 7.908, "2s": 11.680, "3s": 15.452},
    "VEL": {"mean": 1.936, "std": 1.549, "1s": 3.485, "2s": 5.034, "3s": 6.582},
}


def load_feature_matrix() -> pd.DataFrame:
    df = pd.read_csv(DATA_CSV)
    df["EQUIP_CD"] = df["TAG_CD"].str.rsplit("-", n=1).str[0]
    df["TAG_TYPE"] = df["TAG_CD"].str.rsplit("-", n=1).str[1]

    pivot = df.pivot_table(
        index=["EQUIP_CD", "MEAS_DT"], columns="TAG_TYPE", values="MEAS_VAL"
    ).reset_index()
    return pivot.dropna(subset=["ACC", "ENV", "VEL", "STATUS"])


def main() -> None:
    pivot = load_feature_matrix()

    X = pivot[["ACC", "ENV", "VEL"]]
    y = pivot["STATUS"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = ExtraTreesRegressor(n_estimators=300, random_state=42)
    model.fit(X_train_scaled, y_train)

    y_pred = model.predict(X_test_scaled)

    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    pr_auc = average_precision_score(y_test, y_pred)

    print(f"R2:     {r2:.4f}")
    print(f"RMSE:   {rmse:.4f}")
    print(f"MAE:    {mae:.4f}")
    print(f"PR-AUC: {pr_auc:.4f}")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_DIR / "extra_trees.pkl")
    joblib.dump(scaler, MODEL_DIR / "scaler.pkl")

    thresholds = {
        "status_threshold": 0.5,
        "ucl": UCL,
    }
    with open(MODEL_DIR / "thresholds.json", "w") as f:
        json.dump(thresholds, f, indent=2)

    print(f"\n저장 완료: {MODEL_DIR}/extra_trees.pkl, scaler.pkl, thresholds.json")


if __name__ == "__main__":
    main()