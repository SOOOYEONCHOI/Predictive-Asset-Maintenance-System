from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    threshold: float


class PredictRequest(BaseModel):
    equip_cd: Optional[str] = None
    date: Optional[str] = None


class ModelResult(BaseModel):
    value: float
    status: str


class EquipPrediction(BaseModel):
    equip_cd: str
    predict_value: float
    status: str
    sensor_values: dict
    model_results: dict[str, ModelResult]
    meas_dt: str


class PredictResponse(BaseModel):
    results: list[EquipPrediction]


class RawDataPoint(BaseModel):
    meas_dt: str
    acc: float
    env: float
    vel: float
    status_val: float


class RawDataResponse(BaseModel):
    equip_cd: str
    data: list[RawDataPoint]


class ModelDefinitionsResponse(BaseModel):
    model_define: list[dict]
    primary_model: dict | None = None
    adopted_models: list[dict]