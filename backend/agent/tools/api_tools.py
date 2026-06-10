import json
import os

import httpx
from langchain_core.tools import tool

PM_API_BASE = os.environ.get("PM_API_BASE", "http://pm-api:8000")
TIMEOUT = 5.0


@tool
def check_health() -> str:
    """PM API(:8000)의 헬스 상태(/health)를 확인합니다. 운영 장애 진단 시 첫 번째로 사용합니다."""
    try:
        r = httpx.get(f"{PM_API_BASE}/health", timeout=TIMEOUT)
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False)
    except httpx.HTTPError as e:
        return json.dumps({"status": "error", "detail": str(e)}, ensure_ascii=False)


@tool
def get_equipment_status(start_date: str = "") -> str:
    """PM API(/predict/from-db)에서 LN21 라인 6개 설비 전체의 예측 결과(상태)를 조회합니다. start_date(YYYY-MM-DD)를 지정하면 해당 날짜 기준으로 조회합니다. PM API 사용 불가 시 'PM_API_UNAVAILABLE' 문자열을 반환하므로, 이 경우 summarize_equipment_status로 전환하세요."""
    try:
        body = {"date": start_date} if start_date else {}
        r = httpx.post(f"{PM_API_BASE}/predict/from-db", json=body, timeout=TIMEOUT)
        if r.status_code == 503:
            return "PM_API_UNAVAILABLE"
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False)
    except httpx.HTTPError:
        return "PM_API_UNAVAILABLE"


@tool
def get_raw_sensor_data(equip_cd: str, days: int = 14) -> str:
    """PM API(/raw-data)에서 특정 설비의 최근 N일 ACC/ENV/VEL/STATUS 센서 시계열 데이터를 조회합니다."""
    try:
        r = httpx.get(f"{PM_API_BASE}/raw-data", params={"equip_cd": equip_cd, "days": days}, timeout=TIMEOUT)
        if r.status_code == 503:
            return "PM_API_UNAVAILABLE"
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False)
    except httpx.HTTPError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def predict_single_equip(equip_cd: str, date: str = "") -> str:
    """PM API(/predict/from-db)에서 특정 설비 1대의 예측 결과(ExtraTrees + 선형 11종, PREDICT_VALUE, 상태 판정)를 조회합니다. date(YYYY-MM-DD)를 지정하지 않으면 최신 날짜 기준입니다."""
    try:
        body: dict = {"equip_cd": equip_cd}
        if date:
            body["date"] = date
        r = httpx.post(f"{PM_API_BASE}/predict/from-db", json=body, timeout=TIMEOUT)
        if r.status_code == 503:
            return "PM_API_UNAVAILABLE"
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False)
    except httpx.HTTPError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def get_model_definitions() -> str:
    """PM API(/models/definitions)에서 모델 정의(TM_MST_MODEL_DEFINE)와 채택 모델 성능(TB_AI_MDL_RSLT_SMMRY, USE_YN=Y) 정보를 조회합니다."""
    try:
        r = httpx.get(f"{PM_API_BASE}/models/definitions", timeout=TIMEOUT)
        if r.status_code == 503:
            return "PM_API_UNAVAILABLE"
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False)
    except httpx.HTTPError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)