from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException

from pm_api.predictor import Predictor, STATUS_THRESHOLD
from pm_api.schemas import (
    HealthResponse,
    ModelDefinitionsResponse,
    PredictRequest,
    PredictResponse,
    RawDataResponse,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BACKEND_DIR / "data" / "raw"
DATA_CSV = BACKEND_DIR / "data" / "augmented" / "TB_SNSR_AUGMENTED.csv"

EQUIPMENTS = [
    "MTR-21A01-CNV01", "MTR-21A09-CNV01", "MTR-21A12-CNV01",
    "MTR-22B01-CNV01", "MTR-22B09-CNV01", "MTR-22B12-CNV01",
]


def load_sensor_pivot() -> pd.DataFrame:
    df = pd.read_csv(DATA_CSV)
    df["EQUIP_CD"] = df["TAG_CD"].str.rsplit("-", n=1).str[0]
    df["TAG_TYPE"] = df["TAG_CD"].str.rsplit("-", n=1).str[1]
    pivot = df.pivot_table(
        index=["EQUIP_CD", "MEAS_DT"], columns="TAG_TYPE", values="MEAS_VAL"
    ).reset_index()
    return pivot.sort_values(["EQUIP_CD", "MEAS_DT"]).reset_index(drop=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.predictor = Predictor.get_instance()
    try:
        app.state.sensor_pivot = load_sensor_pivot()
    except FileNotFoundError:
        app.state.sensor_pivot = None
    yield


app = FastAPI(title="PM API", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
def health():
    predictor: Predictor = app.state.predictor
    return HealthResponse(
        status="ok",
        model_loaded=predictor.is_loaded,
        threshold=predictor.thresholds.get("status_threshold", STATUS_THRESHOLD),
    )


@app.post("/predict/from-db", response_model=PredictResponse)
def predict_from_db(req: PredictRequest):
    predictor: Predictor = app.state.predictor
    pivot: pd.DataFrame = app.state.sensor_pivot

    if not predictor.is_loaded or pivot is None:
        raise HTTPException(status_code=503, detail="PM_API_UNAVAILABLE")

    target_equips = [req.equip_cd] if req.equip_cd else EQUIPMENTS

    results = []
    for equip_cd in target_equips:
        equip_df = pivot[pivot["EQUIP_CD"] == equip_cd]
        if equip_df.empty:
            continue

        if req.date:
            row_df = equip_df[equip_df["MEAS_DT"] == req.date]
            if row_df.empty:
                continue
            row = row_df.iloc[0]
        else:
            row = equip_df.iloc[-1]

        results.append(predictor.predict(equip_cd, row["MEAS_DT"], row["ACC"], row["ENV"], row["VEL"]))

    if not results:
        raise HTTPException(status_code=404, detail="설비/날짜에 해당하는 데이터가 없습니다.")

    return PredictResponse(results=results)


@app.get("/raw-data", response_model=RawDataResponse)
def raw_data(equip_cd: str, days: int = 14):
    pivot: pd.DataFrame = app.state.sensor_pivot
    if pivot is None:
        raise HTTPException(status_code=503, detail="PM_API_UNAVAILABLE")

    equip_df = pivot[pivot["EQUIP_CD"] == equip_cd]
    if equip_df.empty:
        raise HTTPException(status_code=404, detail=f"설비 코드를 찾을 수 없습니다: {equip_cd}")

    recent = equip_df.tail(days)
    data = [
        {
            "meas_dt": row["MEAS_DT"],
            "acc": row["ACC"],
            "env": row["ENV"],
            "vel": row["VEL"],
            "status_val": row["STATUS"],
        }
        for _, row in recent.iterrows()
    ]
    return RawDataResponse(equip_cd=equip_cd, data=data)


@app.get("/models/definitions", response_model=ModelDefinitionsResponse)
def model_definitions():
    define_df = pd.read_csv(RAW_DIR / "TM_MST_MODEL_DEFINE.csv", encoding="utf-8-sig")
    summary_df = pd.read_csv(RAW_DIR / "TB_AI_MDL_RSLT_SMMRY.csv", encoding="utf-8-sig")
    adopted_df = summary_df[summary_df["USE_YN"] == "Y"]

    return ModelDefinitionsResponse(
        model_define=define_df.to_dict(orient="records"),
        adopted_models=adopted_df.to_dict(orient="records"),
    )