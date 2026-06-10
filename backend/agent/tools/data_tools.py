import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from langchain_core.tools import tool

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BACKEND_DIR / "data")))
MODEL_DIR = Path(os.environ.get("MODEL_DIR", str(DATA_DIR / "model_registry")))
RAW_DIR = DATA_DIR / "raw"
AUGMENTED_CSV = DATA_DIR / "augmented" / "TB_SNSR_AUGMENTED.csv"

EQUIPMENTS = [
    "MTR-21A01-CNV01", "MTR-21A09-CNV01", "MTR-21A12-CNV01",
    "MTR-22B01-CNV01", "MTR-22B09-CNV01", "MTR-22B12-CNV01",
]

# CLAUDE.md — 전체 정상 구간 UCL 임계값
UCL = {
    "ACC": {"mean": 5.440, "std": 4.676, "1s": 10.116, "2s": 14.792, "3s": 19.469},
    "ENV": {"mean": 4.137, "std": 3.772, "1s": 7.908, "2s": 11.680, "3s": 15.452},
    "VEL": {"mean": 1.936, "std": 1.549, "1s": 3.485, "2s": 5.034, "3s": 6.582},
}

WINDOW_DAYS = 7

_csv_cache: dict[str, tuple[float, pd.DataFrame]] = {}


def _load_pivot(csv_path: Path) -> pd.DataFrame:
    """MEAS_DT/TAG_CD/MEAS_VAL 롱 포맷 CSV를 (EQUIP_CD, MEAS_DT) x ACC/ENV/VEL/STATUS 와이드 포맷으로 변환. mtime 기반 캐시."""
    mtime = csv_path.stat().st_mtime
    cached = _csv_cache.get(str(csv_path))
    if cached and cached[0] == mtime:
        return cached[1]

    df = pd.read_csv(csv_path)
    df["EQUIP_CD"] = df["TAG_CD"].str.rsplit("-", n=1).str[0]
    df["TAG_TYPE"] = df["TAG_CD"].str.rsplit("-", n=1).str[1]
    pivot = df.pivot_table(
        index=["EQUIP_CD", "MEAS_DT"], columns="TAG_TYPE", values="MEAS_VAL"
    ).reset_index()
    pivot = pivot.sort_values(["EQUIP_CD", "MEAS_DT"]).reset_index(drop=True)

    _csv_cache[str(csv_path)] = (mtime, pivot)
    return pivot


@tool
def summarize_equipment_status() -> str:
    """TB_SNSR_AUGMENTED.csv 최신 날짜 기준 설비별 ACC/ENV/VEL 센서값과 전체 정상 평균(UCL 기준) 대비 변화율(Δ%)을 반환합니다. PM API 사용 불가(PM_API_UNAVAILABLE) 시 get_equipment_status 대체 도구로 사용합니다."""
    pivot = _load_pivot(AUGMENTED_CSV)
    latest_date = pivot["MEAS_DT"].max()

    equipments = []
    for equip_cd in EQUIPMENTS:
        row_df = pivot[(pivot["EQUIP_CD"] == equip_cd) & (pivot["MEAS_DT"] == latest_date)]
        if row_df.empty:
            continue
        row = row_df.iloc[0]
        entry = {"equip_cd": equip_cd, "meas_dt": latest_date, "status_val": row["STATUS"]}
        for tag in ["ACC", "ENV", "VEL"]:
            val = float(row[tag])
            mean = UCL[tag]["mean"]
            entry[tag] = round(val, 4)
            entry[f"{tag}_delta_pct"] = round((val - mean) / mean * 100, 1)
        equipments.append(entry)

    return json.dumps({"meas_dt": latest_date, "equipments": equipments}, ensure_ascii=False)


@tool
def find_missing_features(month: str) -> str:
    """해당 월(YYYY-MM 형식)의 날짜 x 설비 x 태그(ACC/ENV/VEL/STATUS) 조합 완전성을 검사하고 누락 항목을 반환합니다."""
    df = pd.read_csv(AUGMENTED_CSV)
    df["EQUIP_CD"] = df["TAG_CD"].str.rsplit("-", n=1).str[0]
    df["TAG_TYPE"] = df["TAG_CD"].str.rsplit("-", n=1).str[1]
    df_month = df[df["MEAS_DT"].str.startswith(month)]

    if df_month.empty:
        return json.dumps({"month": month, "message": "해당 월 데이터가 없습니다."}, ensure_ascii=False)

    dates = sorted(df_month["MEAS_DT"].unique())
    tags = ["ACC", "ENV", "VEL", "STATUS"]
    existing = set(zip(df_month["EQUIP_CD"], df_month["MEAS_DT"], df_month["TAG_TYPE"]))

    missing = []
    for equip_cd in EQUIPMENTS:
        for d in dates:
            for tag in tags:
                if (equip_cd, d, tag) not in existing:
                    missing.append({"equip_cd": equip_cd, "date": d, "tag": tag})

    total_expected = len(EQUIPMENTS) * len(dates) * len(tags)
    result = {
        "month": month,
        "date_range": [dates[0], dates[-1]],
        "total_expected": total_expected,
        "missing_count": len(missing),
        "completeness_pct": round((1 - len(missing) / total_expected) * 100, 2),
        "missing": missing[:50],
    }
    return json.dumps(result, ensure_ascii=False)


@tool
def compare_model_metrics() -> str:
    """TB_AI_MDL_RSLT_SMMRY.csv에서 채택 모델(USE_YN=Y) 그룹과 전체 모델 그룹의 R2/RMSE/MAE 평균을 비교합니다."""
    df = pd.read_csv(RAW_DIR / "TB_AI_MDL_RSLT_SMMRY.csv", encoding="utf-8-sig")
    df["ALGO_NM"] = df["ALGO_NM"].str.strip()
    adopted = df[df["USE_YN"] == "Y"]

    def _stats(d: pd.DataFrame) -> dict:
        return {
            "count": int(len(d)),
            "r2_mean": round(float(d["R2_VAL"].mean()), 4),
            "rmse_mean": round(float(d["RMSE_VAL"].mean()), 4),
            "mae_mean": round(float(d["MAE_VAL"].mean()), 4),
        }

    extra_trees_row = df[df["ALGO_NM"] == "ExtraTreesRegressor"].iloc[0]

    result = {
        "extra_trees": {
            "r2": float(extra_trees_row["R2_VAL"]),
            "rmse": float(extra_trees_row["RMSE_VAL"]),
            "mae": float(extra_trees_row["MAE_VAL"]),
        },
        "adopted_models": {"algos": adopted["ALGO_NM"].tolist(), **_stats(adopted)},
        "all_models": _stats(df),
    }
    return json.dumps(result, ensure_ascii=False)


@tool
def get_feature_contribution(equip_cd: str) -> str:
    """TB_AI_MDL_PARAM의 11종 선형 모델 계수와 최신 센서값을 곱해 ACC/ENV/VEL 피처별 기여도를 모델별로 계산합니다. HuberRegressor와 LinearSVR은 절편이 다른 선형 모델과 달라 다른 모델과 절대 평균화하지 않고 개별 계산됩니다."""
    pivot = _load_pivot(AUGMENTED_CSV)
    equip_df = pivot[pivot["EQUIP_CD"] == equip_cd]
    if equip_df.empty:
        return json.dumps({"error": f"설비 코드를 찾을 수 없습니다: {equip_cd}"}, ensure_ascii=False)

    latest = equip_df.iloc[-1]
    params = pd.read_csv(RAW_DIR / "TB_AI_MDL_PARAM.csv", encoding="utf-8-sig")

    contributions = {}
    for algo, group in params.groupby("ALGO_CD"):
        coef = dict(zip(group["TAG_CD"], group["COEFF_VAL"]))
        acc_c = coef["ACC"] * latest["ACC"]
        env_c = coef["ENV"] * latest["ENV"]
        vel_c = coef["VEL"] * latest["VEL"]
        contributions[algo] = {
            "ACC": round(float(acc_c), 4),
            "ENV": round(float(env_c), 4),
            "VEL": round(float(vel_c), 4),
            "intercept": coef["절편"],
            "predict_value": round(float(acc_c + env_c + vel_c + coef["절편"]), 4),
        }

    result = {
        "equip_cd": equip_cd,
        "meas_dt": latest["MEAS_DT"],
        "sensor_values": {
            "ACC": round(float(latest["ACC"]), 4),
            "ENV": round(float(latest["ENV"]), 4),
            "VEL": round(float(latest["VEL"]), 4),
        },
        "contributions_by_model": contributions,
        "note": "HuberRegressor/LinearSVR의 절편(0.41)은 다른 선형 모델(0.87~0.88)과 달라 개별 계산되었으며 평균화되지 않았습니다.",
    }
    return json.dumps(result, ensure_ascii=False)


@tool
def analyze_trend(window_days: int = 7) -> str:
    """최근 N일과 직전 N일의 설비별 ACC/ENV/VEL 평균을 비교해 변화율(%)을 계산합니다. ±15% 이상은 'caution', ±30% 이상은 'alert'로 표시합니다."""
    pivot = _load_pivot(AUGMENTED_CSV)

    results = []
    for equip_cd in EQUIPMENTS:
        equip_df = pivot[pivot["EQUIP_CD"] == equip_cd].reset_index(drop=True)
        if len(equip_df) < window_days * 2:
            continue

        recent = equip_df.tail(window_days)
        previous = equip_df.iloc[-window_days * 2: -window_days]

        entry = {
            "equip_cd": equip_cd,
            "recent_period": [recent["MEAS_DT"].iloc[0], recent["MEAS_DT"].iloc[-1]],
            "previous_period": [previous["MEAS_DT"].iloc[0], previous["MEAS_DT"].iloc[-1]],
        }
        for tag in ["ACC", "ENV", "VEL"]:
            r_mean, p_mean = float(recent[tag].mean()), float(previous[tag].mean())
            change_pct = (r_mean - p_mean) / p_mean * 100 if p_mean else 0.0
            level = "normal"
            if abs(change_pct) >= 30:
                level = "alert"
            elif abs(change_pct) >= 15:
                level = "caution"
            entry[tag] = {
                "recent_mean": round(r_mean, 4),
                "previous_mean": round(p_mean, 4),
                "change_pct": round(change_pct, 1),
                "level": level,
            }
        results.append(entry)

    return json.dumps({"window_days": window_days, "results": results}, ensure_ascii=False)


FAULT_RECOMMENDED_ACTIONS = {
    "Spike": "즉시 가동 중단 및 이물질·충격 원인 현장 점검",
    "Creep": "베어링 윤활 상태 확인 및 정밀 진단 예약",
    "Drift": "구조 이완·열변형 여부 확인, 정밀 측정 실시",
}


@tool
def classify_fault_type(equip_cd: str, window_days: int = 7) -> str:
    """fault_classifier.pkl을 사용해 최근 window_days일 센서 패턴(ACC/ENV/VEL 평균·표준편차, VEL 기울기, ACC/VEL 비율)으로 Spike/Creep/Drift 이상 유형을 분류하고 분류 근거와 권장 조치를 반환합니다."""
    pivot = _load_pivot(AUGMENTED_CSV)
    equip_df = pivot[pivot["EQUIP_CD"] == equip_cd].reset_index(drop=True)
    if equip_df.empty:
        return json.dumps({"error": f"설비 코드를 찾을 수 없습니다: {equip_cd}"}, ensure_ascii=False)
    if len(equip_df) < window_days:
        return json.dumps({"error": f"데이터가 부족합니다 ({len(equip_df)}일 < {window_days}일)."}, ensure_ascii=False)

    window = equip_df.tail(window_days)

    acc_mean, acc_std = float(window["ACC"].mean()), float(window["ACC"].std())
    env_mean, env_std = float(window["ENV"].mean()), float(window["ENV"].std())
    vel_mean, vel_std = float(window["VEL"].mean()), float(window["VEL"].std())
    vel_slope = float(np.polyfit(range(window_days), window["VEL"].values, 1)[0])
    acc_vel_ratio = acc_mean / vel_mean if vel_mean else 0.0

    bundle = joblib.load(MODEL_DIR / "fault_classifier.pkl")
    model, features = bundle["model"], bundle["features"]

    feature_row = {
        "ACC_mean": acc_mean, "ACC_std": acc_std,
        "ENV_mean": env_mean, "ENV_std": env_std,
        "VEL_mean": vel_mean, "VEL_std": vel_std,
        "VEL_slope": vel_slope, "ACC_VEL_ratio": acc_vel_ratio,
    }
    X = pd.DataFrame([feature_row])[features]

    fault_type = model.predict(X)[0]
    confidence = round(float(max(model.predict_proba(X)[0])), 3)

    evidence = [
        f"VEL_{window_days}일_기울기: {vel_slope:+.3f}/day",
        f"ACC/VEL_비율: {acc_vel_ratio:.2f}",
        f"ENV_평균: {env_mean:.2f}, ACC_평균: {acc_mean:.2f}",
    ]

    result = {
        "equip_cd": equip_cd,
        "fault_type": fault_type,
        "confidence": confidence,
        "evidence": evidence,
        "recommended_action": FAULT_RECOMMENDED_ACTIONS.get(fault_type, ""),
    }
    return json.dumps(result, ensure_ascii=False)