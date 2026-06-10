import json
from pathlib import Path
from typing import Optional

import joblib
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BACKEND_DIR / "data" / "model_registry"
RAW_DIR = BACKEND_DIR / "data" / "raw"
DATA_CSV = BACKEND_DIR / "data" / "augmented" / "TB_SNSR_AUGMENTED.csv"

STATUS_THRESHOLD = 0.5


def status_label(predict_value: float) -> str:
    if predict_value > 0.9:
        return "정상"
    if predict_value > 0.7:
        return "주의"
    if predict_value > 0.5:
        return "경고"
    return "위험"


class Predictor:
    _instance: Optional["Predictor"] = None

    def __init__(self):
        self.model = None
        self.scaler = None
        self.thresholds = {}
        self.linear_params: dict[str, dict[str, float]] = {}

        try:
            self.model = joblib.load(MODEL_DIR / "extra_trees.pkl")
            self.scaler = joblib.load(MODEL_DIR / "scaler.pkl")
            with open(MODEL_DIR / "thresholds.json") as f:
                self.thresholds = json.load(f)
            self.linear_params = self._load_linear_params()
        except FileNotFoundError:
            pass

    @classmethod
    def get_instance(cls) -> "Predictor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_loaded(self) -> bool:
        return self.model is not None and self.scaler is not None

    def _load_linear_params(self) -> dict[str, dict[str, float]]:
        df = pd.read_csv(RAW_DIR / "TB_AI_MDL_PARAM.csv", encoding="utf-8-sig")
        params: dict[str, dict[str, float]] = {}
        for algo, group in df.groupby("ALGO_CD"):
            params[algo] = dict(zip(group["TAG_CD"], group["COEFF_VAL"]))
        return params

    def predict_extra_trees(self, acc: float, env: float, vel: float) -> float:
        X = self.scaler.transform([[acc, env, vel]])
        return float(self.model.predict(X)[0])

    def predict_linear_models(self, acc: float, env: float, vel: float) -> dict[str, dict]:
        results = {}
        for algo, coef in self.linear_params.items():
            value = coef["ACC"] * acc + coef["ENV"] * env + coef["VEL"] * vel + coef["절편"]
            value = max(0.0, value)  # CLAUDE.md: 선형 모델 예측값 하한 0으로 클리핑
            results[algo] = {"value": round(value, 4), "status": status_label(value)}
        return results

    def predict(self, equip_cd: str, meas_dt: str, acc: float, env: float, vel: float) -> dict:
        et_value = self.predict_extra_trees(acc, env, vel)
        model_results = {"ExtraTreesRegressor": {"value": round(et_value, 4), "status": status_label(et_value)}}
        model_results.update(self.predict_linear_models(acc, env, vel))

        return {
            "equip_cd": equip_cd,
            "predict_value": round(et_value, 4),
            "status": status_label(et_value),
            "sensor_values": {"ACC": acc, "ENV": env, "VEL": vel},
            "model_results": model_results,
            "meas_dt": meas_dt,
        }