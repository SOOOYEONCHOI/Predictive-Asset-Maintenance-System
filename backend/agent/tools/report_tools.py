import json
from datetime import date, datetime, timedelta

import joblib
import numpy as np
import pandas as pd
from langchain_core.tools import tool

from agent.tools.data_tools import AUGMENTED_CSV, MODEL_DIR, _load_pivot

WINDOW_DAYS = 7

FAULT_LABELS = {
    "Spike": "Spike형 (급격형, 기계적 충격/이물질)",
    "Creep": "Creep형 (점진형, 베어링 마모/윤활 부족)",
    "Drift": "Drift형 (누적형, 구조적 이완/열변형)",
    "Normal": "이상 없음",
}

FAULT_ACTION_ITEMS = {
    "Spike": "□ 즉시 가동 중단 및 이물질·충격 원인 현장 점검\n□ 컨베이어 주변 이물질 제거\n□ 충격 흔적 육안 점검 후 부품 교체 여부 판단",
    "Creep": "□ 베어링 윤활 상태 육안 점검\n□ 윤활유 보충/교체\n□ 정밀 진동 진단 예약",
    "Drift": "□ 구조 이완·열변형 여부 확인\n□ 볼트/프레임 체결 상태 점검\n□ 정밀 측정 실시 및 재조정",
    "Normal": "□ 정기 점검 일정 유지\n□ 센서 데이터 모니터링 지속",
}


@tool
def estimate_rul(equip_cd: str) -> str:
    """rul_model.pkl과 최근 7일 VEL 추세 외삽을 사용해 UCL_2σ 도달까지 남은 일수(RUL)를 예측합니다."""
    pivot = _load_pivot(AUGMENTED_CSV)
    equip_df = pivot[pivot["EQUIP_CD"] == equip_cd].reset_index(drop=True)
    if equip_df.empty or len(equip_df) < WINDOW_DAYS:
        return json.dumps({"error": f"데이터가 부족합니다: {equip_cd}"}, ensure_ascii=False)

    window = equip_df.tail(WINDOW_DAYS)
    vel_values = window["VEL"].values

    vel_ma7 = float(window["VEL"].mean())
    vel_prev, vel_now = float(vel_values[0]), float(vel_values[-1])
    vel_growth_rate = (vel_now - vel_prev) / vel_prev if vel_prev else 0.0
    acc_vel_ratio = float(equip_df["ACC"].iloc[-1]) / vel_now if vel_now else 0.0

    bundle = joblib.load(MODEL_DIR / "rul_model.pkl")
    model, features = bundle["model"], bundle["features"]
    X = pd.DataFrame([{
        "VEL_ma7": vel_ma7,
        "VEL_growth_rate": vel_growth_rate,
        "ACC_VEL_ratio": acc_vel_ratio,
    }])[features]
    rul_days = max(0, int(round(model.predict(X)[0])))

    # VEL 선형 추세 외삽으로 UCL_2σ 도달일 계산, R^2를 confidence로 사용
    x = np.arange(WINDOW_DAYS)
    slope, intercept = np.polyfit(x, vel_values, 1)
    y_fit = slope * x + intercept
    ss_res = float(np.sum((vel_values - y_fit) ** 2))
    ss_tot = float(np.sum((vel_values - vel_values.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    confidence = round(max(0.0, min(1.0, r2)), 2)

    with open(MODEL_DIR / "thresholds.json") as f:
        thresholds = json.load(f)
    ucl_2s = thresholds["ucl"]["VEL"]["2s"]

    if slope > 0:
        days_to_ucl = (ucl_2s - vel_now) / slope
        basis = (
            f"VEL 일간 증가율 {slope:+.3f}/일, UCL_2σ({ucl_2s}) 도달 예상 {days_to_ucl:.1f}일 "
            f"(모델 예측 RUL={rul_days}일, R²={confidence})"
        )
    else:
        basis = f"VEL 추세 정체/하락 (모델 예측 RUL={rul_days}일, R²={confidence})"

    latest_date = date.fromisoformat(equip_df["MEAS_DT"].iloc[-1])
    recommended_maintenance_date = (latest_date + timedelta(days=rul_days)).isoformat()

    result = {
        "equip_cd": equip_cd,
        "rul_days": rul_days,
        "recommended_maintenance_date": recommended_maintenance_date,
        "confidence": confidence,
        "basis": basis,
    }
    return json.dumps(result, ensure_ascii=False)


@tool
def make_work_order_draft(
    equip_cd: str,
    status: str,
    fault_type: str,
    predict_value: float,
    abnormal_tags: str,
    estimated_rul: int,
    meas_dt: str,
    model_name: str,
) -> str:
    """분석 완료 후, SPEC.md 시나리오 7 형식의 설비 보전 작업 지시서를 마크다운으로 생성합니다."""
    issued_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    fault_label = FAULT_LABELS.get(fault_type, fault_type)
    action_items = FAULT_ACTION_ITEMS.get(fault_type, "□ 정밀 점검 실시")

    return f"""# 설비 보전 작업 지시서

**발행일시**: {issued_at}
**설비코드**: {equip_cd}

## 현황
- 예측 상태: {status} (PREDICT_VALUE: {predict_value})
- 이상 유형: {fault_label}
- 예상 잔여 가동일: 약 {estimated_rul}일
- 측정일자: {meas_dt}
- 사용 모델: {model_name}

## 이상 근거
- 이상 감지 태그: {abnormal_tags}

## 조치 항목
{action_items}
"""