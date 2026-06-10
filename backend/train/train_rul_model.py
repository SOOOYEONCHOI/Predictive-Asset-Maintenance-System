import sys
from datetime import timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
from augment.run_augment import PLANS, START_DATE  # noqa: E402

DATA_CSV = BACKEND_DIR / "data" / "augmented" / "TB_SNSR_AUGMENTED.csv"
MODEL_DIR = BACKEND_DIR / "data" / "model_registry"

WINDOW_DAYS = 7
MAX_RUL = 30
FEATURES = ["VEL_ma7", "VEL_growth_rate", "ACC_VEL_ratio"]


def anomaly_start_dates() -> dict[str, list[str]]:
    """run_augment.PLANS의 에피소드별 STATUS=0 시작일 목록."""
    starts: dict[str, list[str]] = {}
    for equip_cd, episodes in PLANS.items():
        dates = []
        for ep in episodes:
            ep_start = START_DATE + timedelta(days=ep["offset"])
            if ep["type"] == "creep":
                fault_start = ep_start + timedelta(days=ep["warning_days"])
            else:  # spike, drift
                fault_start = ep_start
            dates.append(fault_start.isoformat())
        starts[equip_cd] = dates
    return starts


def build_feature_matrix() -> pd.DataFrame:
    df = pd.read_csv(DATA_CSV)
    df["EQUIP_CD"] = df["TAG_CD"].str.rsplit("-", n=1).str[0]
    df["TAG_TYPE"] = df["TAG_CD"].str.rsplit("-", n=1).str[1]
    pivot = df.pivot_table(
        index=["EQUIP_CD", "MEAS_DT"], columns="TAG_TYPE", values="MEAS_VAL"
    ).reset_index()
    pivot = pivot.sort_values(["EQUIP_CD", "MEAS_DT"]).reset_index(drop=True)

    starts = anomaly_start_dates()

    samples = []
    for equip_cd, group in pivot.groupby("EQUIP_CD"):
        group = group.reset_index(drop=True)
        date_to_idx = {d: i for i, d in enumerate(group["MEAS_DT"])}

        for fault_start in starts[equip_cd]:
            start_idx = date_to_idx.get(fault_start)
            if start_idx is None:
                continue

            for rul in range(0, MAX_RUL + 1):
                idx = start_idx - rul
                if idx < WINDOW_DAYS - 1:
                    continue
                window = group.iloc[idx - WINDOW_DAYS + 1: idx + 1]

                vel_ma7 = window["VEL"].mean()
                vel_prev = window["VEL"].iloc[0]
                vel_now = window["VEL"].iloc[-1]
                vel_growth_rate = (vel_now - vel_prev) / vel_prev if vel_prev else 0.0
                acc_vel_ratio = group["ACC"].iloc[idx] / vel_now if vel_now else 0.0

                samples.append({
                    "VEL_ma7": vel_ma7,
                    "VEL_growth_rate": vel_growth_rate,
                    "ACC_VEL_ratio": acc_vel_ratio,
                    "rul": rul,
                })

    return pd.DataFrame(samples)


def main() -> None:
    data = build_feature_matrix()
    print(f"학습 샘플 수: {len(data)}")

    X = data[FEATURES]
    y = data["rul"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = GradientBoostingRegressor(n_estimators=200, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)

    print(f"R2:   {r2:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"MAE:  {mae:.4f}")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": FEATURES}, MODEL_DIR / "rul_model.pkl")
    print(f"저장 완료: {MODEL_DIR}/rul_model.pkl")


if __name__ == "__main__":
    main()