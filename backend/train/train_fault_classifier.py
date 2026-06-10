import sys
from datetime import timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
from augment.run_augment import PLANS, START_DATE  # noqa: E402

DATA_CSV = BACKEND_DIR / "data" / "augmented" / "TB_SNSR_AUGMENTED.csv"
MODEL_DIR = BACKEND_DIR / "data" / "model_registry"

WINDOW_DAYS = 7
FEATURES = [
    "ACC_mean", "ACC_std",
    "ENV_mean", "ENV_std",
    "VEL_mean", "VEL_std",
    "VEL_slope", "ACC_VEL_ratio",
]


def build_anomaly_labels() -> pd.DataFrame:
    """run_augment.PLANS의 에피소드 정의로부터 (EQUIP_CD, MEAS_DT, fault_type) 레이블을 생성."""
    rows = []
    for equip_cd, episodes in PLANS.items():
        for ep in episodes:
            ep_start = START_DATE + timedelta(days=ep["offset"])
            if ep["type"] == "spike":
                fault_start, fault_days, label = ep_start, ep["days"], "Spike"
            elif ep["type"] == "creep":
                fault_start = ep_start + timedelta(days=ep["warning_days"])
                fault_days, label = ep["fault_days"], "Creep"
            else:  # drift
                fault_start, fault_days, label = ep_start, ep["days"], "Drift"

            for i in range(fault_days):
                rows.append({
                    "EQUIP_CD": equip_cd,
                    "MEAS_DT": (fault_start + timedelta(days=i)).isoformat(),
                    "fault_type": label,
                })
    return pd.DataFrame(rows)


def build_feature_matrix() -> pd.DataFrame:
    df = pd.read_csv(DATA_CSV)
    df["EQUIP_CD"] = df["TAG_CD"].str.rsplit("-", n=1).str[0]
    df["TAG_TYPE"] = df["TAG_CD"].str.rsplit("-", n=1).str[1]
    pivot = df.pivot_table(
        index=["EQUIP_CD", "MEAS_DT"], columns="TAG_TYPE", values="MEAS_VAL"
    ).reset_index()
    pivot = pivot.sort_values(["EQUIP_CD", "MEAS_DT"]).reset_index(drop=True)

    labels = build_anomaly_labels()

    samples = []
    for equip_cd, group in pivot.groupby("EQUIP_CD"):
        group = group.reset_index(drop=True)
        date_to_idx = {d: i for i, d in enumerate(group["MEAS_DT"])}
        equip_labels = labels[labels["EQUIP_CD"] == equip_cd]

        for _, label_row in equip_labels.iterrows():
            idx = date_to_idx.get(label_row["MEAS_DT"])
            if idx is None or idx < WINDOW_DAYS - 1:
                continue
            window = group.iloc[idx - WINDOW_DAYS + 1: idx + 1]

            acc_mean, acc_std = window["ACC"].mean(), window["ACC"].std()
            env_mean, env_std = window["ENV"].mean(), window["ENV"].std()
            vel_mean, vel_std = window["VEL"].mean(), window["VEL"].std()
            vel_slope = np.polyfit(range(WINDOW_DAYS), window["VEL"].values, 1)[0]
            acc_vel_ratio = acc_mean / vel_mean if vel_mean else 0.0

            samples.append({
                "ACC_mean": acc_mean, "ACC_std": acc_std,
                "ENV_mean": env_mean, "ENV_std": env_std,
                "VEL_mean": vel_mean, "VEL_std": vel_std,
                "VEL_slope": vel_slope, "ACC_VEL_ratio": acc_vel_ratio,
                "fault_type": label_row["fault_type"],
            })

    return pd.DataFrame(samples)


def main() -> None:
    data = build_feature_matrix()
    print(f"학습 샘플 수: {len(data)} (클래스별: {data['fault_type'].value_counts().to_dict()})")

    X = data[FEATURES]
    y = data["fault_type"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(n_estimators=200, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\n분류 리포트:")
    print(classification_report(y_test, y_pred))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": FEATURES, "classes": list(model.classes_)},
                 MODEL_DIR / "fault_classifier.pkl")
    print(f"저장 완료: {MODEL_DIR}/fault_classifier.pkl")


if __name__ == "__main__":
    main()