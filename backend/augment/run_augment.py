import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from augment.generator import (  # noqa: E402
    generate_creep_fault,
    generate_drift_fault,
    generate_normal_period,
    generate_spike_fault,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent
RAW_CSV = BACKEND_DIR / "data" / "raw" / "TB_SNSR_RAW_DATA.csv"
OUT_CSV = BACKEND_DIR / "data" / "augmented" / "TB_SNSR_AUGMENTED.csv"

START_DATE = date(2026, 5, 11)
TOTAL_DAYS = 220  # 2026-05-11 ~ 2027-01-17

# 설비별 이상 에피소드 계획 (CLAUDE.md 실제 이상 이력을 템플릿으로 사용)
# offset: START_DATE 기준 시작일 오프셋(일)
# truncate: 마지막 에피소드가 미복구일 경우 해당 에피소드 종료 시점에서 데이터 종료
PLANS = {
    "MTR-21A01-CNV01": [  # drift, 미복구
        {"type": "drift", "offset": 60, "days": 14},
        {"type": "drift", "offset": 200, "days": 14, "truncate": True},
    ],
    "MTR-21A09-CNV01": [  # spike, 복구
        {"type": "spike", "offset": 20, "days": 5},
        {"type": "spike", "offset": 95, "days": 4},
        {"type": "spike", "offset": 174, "days": 5},
    ],
    "MTR-21A12-CNV01": [  # creep, 복구 (경고 7일 + 이상 4일)
        {"type": "creep", "offset": 30, "warning_days": 7, "fault_days": 4},
        {"type": "creep", "offset": 101, "warning_days": 7, "fault_days": 4},
    ],
    "MTR-22B01-CNV01": [  # spike, 복구
        {"type": "spike", "offset": 25, "days": 4},
        {"type": "spike", "offset": 94, "days": 5},
        {"type": "spike", "offset": 179, "days": 4},
    ],
    "MTR-22B09-CNV01": [  # recurring(spike 패턴 3회), 복구
        {"type": "spike", "offset": 15, "days": 5},
        {"type": "spike", "offset": 70, "days": 4},
        {"type": "spike", "offset": 145, "days": 5},
    ],
    "MTR-22B12-CNV01": [  # recurring(spike 패턴 3회), 마지막 미복구
        {"type": "spike", "offset": 40, "days": 5},
        {"type": "spike", "offset": 110, "days": 4},
        {"type": "spike", "offset": 200, "days": 5, "truncate": True},
    ],
}


def _generate_episode_rows(equip_cd: str, ep: dict) -> list[dict]:
    ep_start = START_DATE + timedelta(days=ep["offset"])
    if ep["type"] == "spike":
        return generate_spike_fault(equip_cd, ep_start, ep["days"])
    if ep["type"] == "creep":
        return generate_creep_fault(equip_cd, ep_start, ep["warning_days"], ep["fault_days"])
    if ep["type"] == "drift":
        return generate_drift_fault(equip_cd, ep_start, ep["days"])
    raise ValueError(f"unknown episode type: {ep['type']}")


def build_equipment_rows(equip_cd: str, plans: list[dict]) -> list[dict]:
    total_days = TOTAL_DAYS
    if plans and plans[-1].get("truncate"):
        last = plans[-1]
        total_days = last["offset"] + last["days"]

    rows_by_date: dict[str, list[dict]] = {}
    for row in generate_normal_period(equip_cd, START_DATE, total_days):
        rows_by_date.setdefault(row["MEAS_DT"], []).append(row)

    for ep in plans:
        fault_rows = _generate_episode_rows(equip_cd, ep)
        grouped: dict[str, list[dict]] = {}
        for row in fault_rows:
            grouped.setdefault(row["MEAS_DT"], []).append(row)
        rows_by_date.update(grouped)

    all_rows: list[dict] = []
    for d in sorted(rows_by_date.keys()):
        all_rows.extend(rows_by_date[d])
    return all_rows


def main() -> None:
    augmented_rows: list[dict] = []
    for equip_cd, plans in PLANS.items():
        augmented_rows.extend(build_equipment_rows(equip_cd, plans))

    aug_df = pd.DataFrame(augmented_rows)
    aug_df["STATUS"] = "GOOD"  # raw 데이터 STATUS 컬럼 형식(품질 플래그)에 맞춤
    aug_df = aug_df[["MEAS_DT", "TAG_CD", "MEAS_VAL", "STATUS"]]

    raw_df = pd.read_csv(RAW_CSV, encoding="utf-8-sig")

    final_df = pd.concat([raw_df, aug_df], ignore_index=True)
    final_df = final_df.sort_values(["MEAS_DT", "TAG_CD"]).reset_index(drop=True)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(OUT_CSV, index=False)

    # --- 통계 출력 ---
    print(f"전체 행수: {len(final_df)}")

    status_rows = final_df[final_df["TAG_CD"].str.endswith("-STATUS")]
    zero_ratio = (status_rows["MEAS_VAL"] == 0.0).mean()
    print(f"STATUS=0 비율: {zero_ratio:.2%} ({(status_rows['MEAS_VAL'] == 0.0).sum()}/{len(status_rows)})")

    final_df["EQUIP_CD"] = final_df["TAG_CD"].str.rsplit("-", n=1).str[0]
    print("\n설비별 행수:")
    for equip_cd, count in final_df["EQUIP_CD"].value_counts().sort_index().items():
        print(f"  {equip_cd}: {count}")

    print(f"\n날짜 범위: {final_df['MEAS_DT'].min()} ~ {final_df['MEAS_DT'].max()}")


if __name__ == "__main__":
    main()