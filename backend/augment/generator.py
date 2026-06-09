import math
import random
from datetime import date, timedelta
from typing import List

# CLAUDE.md — 설비별 정상 구간 센서 통계
NORMAL_STATS = {
    "MTR-21A01-CNV01": {"ACC": {"mean": 8.873, "std": 0.226}, "ENV": {"mean": 6.443, "std": 1.503}, "VEL": {"mean": 2.848, "std": 0.591}},
    "MTR-21A09-CNV01": {"ACC": {"mean": 3.909, "std": 3.736}, "ENV": {"mean": 2.491, "std": 2.458}, "VEL": {"mean": 1.149, "std": 0.927}},
    "MTR-21A12-CNV01": {"ACC": {"mean": 6.453, "std": 4.426}, "ENV": {"mean": 4.579, "std": 3.264}, "VEL": {"mean": 1.869, "std": 1.288}},
    "MTR-22B01-CNV01": {"ACC": {"mean": 3.334, "std": 3.666}, "ENV": {"mean": 2.600, "std": 2.439}, "VEL": {"mean": 1.731, "std": 1.319}},
    "MTR-22B09-CNV01": {"ACC": {"mean": 0.421, "std": 0.160}, "ENV": {"mean": 0.411, "std": 0.127}, "VEL": {"mean": 0.380, "std": 0.140}},
    "MTR-22B12-CNV01": {"ACC": {"mean": 9.925, "std": 4.360}, "ENV": {"mean": 8.421, "std": 4.205}, "VEL": {"mean": 3.657, "std": 1.695}},
}

PHI = 0.7  # AR(1) 자기상관 계수
SENSORS = ["ACC", "ENV", "VEL"]


def _clip(val: float) -> float:
    return max(0.001, min(val, 18.5))


def _ar1_series(mean: float, std: float, days: int) -> List[float]:
    """AR(1) 정상과정: x_t = mu + phi*(x_{t-1} - mu) + eps, eps ~ N(0, std*sqrt(1-phi^2))"""
    noise_std = std * math.sqrt(1 - PHI ** 2)
    x = mean
    series = []
    for _ in range(days):
        x = mean + PHI * (x - mean) + random.gauss(0, noise_std)
        series.append(_clip(x))
    return series


def _rows(equip_cd: str, dt: date, acc: float, env: float, vel: float, status_meas: float, status_col: int) -> List[dict]:
    d = dt.isoformat()
    return [
        {"MEAS_DT": d, "TAG_CD": f"{equip_cd}-ACC",    "MEAS_VAL": acc,         "STATUS": status_col},
        {"MEAS_DT": d, "TAG_CD": f"{equip_cd}-ENV",    "MEAS_VAL": env,         "STATUS": status_col},
        {"MEAS_DT": d, "TAG_CD": f"{equip_cd}-VEL",    "MEAS_VAL": vel,         "STATUS": status_col},
        {"MEAS_DT": d, "TAG_CD": f"{equip_cd}-STATUS", "MEAS_VAL": status_meas, "STATUS": status_col},
    ]


def generate_normal_period(equip_cd: str, start_date: date, days: int) -> List[dict]:
    stats = NORMAL_STATS[equip_cd]
    acc_s = _ar1_series(stats["ACC"]["mean"], stats["ACC"]["std"], days)
    env_s = _ar1_series(stats["ENV"]["mean"], stats["ENV"]["std"], days)
    vel_s = _ar1_series(stats["VEL"]["mean"], stats["VEL"]["std"], days)
    rows = []
    for i in range(days):
        rows.extend(_rows(equip_cd, start_date + timedelta(days=i), acc_s[i], env_s[i], vel_s[i], 1.0, 1))
    return rows


def generate_spike_fault(equip_cd: str, fault_start: date, fault_days: int = 5) -> List[dict]:
    """정상→이상 당일 급등. VEL 배율 > ACC 배율 (Spike 특징). ACC × 0.9 ≈ ENV."""
    stats = NORMAL_STATS[equip_cd]
    rows = []
    for i in range(fault_days):
        acc_ratio = random.uniform(3.0, 15.0)
        env_ratio = acc_ratio * 0.9                         # CLAUDE.md: ENV ≈ ACC × 0.9
        vel_ratio = acc_ratio * random.uniform(1.1, 1.5)    # CLAUDE.md: VEL > ACC
        rows.extend(_rows(
            equip_cd,
            fault_start + timedelta(days=i),
            _clip(stats["ACC"]["mean"] * acc_ratio),
            _clip(stats["ENV"]["mean"] * env_ratio),
            _clip(stats["VEL"]["mean"] * vel_ratio),
            0.0, 0,
        ))
    return rows


def generate_creep_fault(equip_cd: str, fault_start: date, warning_days: int = 7, fault_days: int = 4) -> List[dict]:
    """
    경고 구간(warning_days): VEL 1.0x → 2.5x 선형 증가, STATUS=1 유지.
    이상 구간(fault_days):  ACC ~2.2x, ENV ~3.1x, VEL ~7.1x, STATUS=0.
    """
    stats = NORMAL_STATS[equip_cd]
    rows = []
    # 경고 구간
    for i in range(warning_days):
        t = i / max(warning_days - 1, 1)
        vel_ratio = 1.0 + (2.5 - 1.0) * t
        rows.extend(_rows(
            equip_cd,
            fault_start + timedelta(days=i),
            _clip(stats["ACC"]["mean"] * random.uniform(0.95, 1.05)),
            _clip(stats["ENV"]["mean"] * random.uniform(0.95, 1.05)),
            _clip(stats["VEL"]["mean"] * vel_ratio),
            1.0, 1,
        ))
    # 이상 구간 (CLAUDE.md 기준값 ±10%)
    for i in range(fault_days):
        rows.extend(_rows(
            equip_cd,
            fault_start + timedelta(days=warning_days + i),
            _clip(stats["ACC"]["mean"] * random.uniform(2.0, 2.4)),   # 기준 2.2x
            _clip(stats["ENV"]["mean"] * random.uniform(2.8, 3.4)),   # 기준 3.1x
            _clip(stats["VEL"]["mean"] * random.uniform(6.4, 7.8)),   # 기준 7.1x
            0.0, 0,
        ))
    return rows


def generate_drift_fault(equip_cd: str, fault_start: date, drift_days: int = 14) -> List[dict]:
    """ENV 배율 > ACC 배율 항상 성립. VEL 3.5~5.5x. 전 기간 STATUS=0."""
    stats = NORMAL_STATS[equip_cd]
    rows = []
    for i in range(drift_days):
        acc_ratio = random.uniform(1.5, 2.1)
        env_ratio = random.uniform(2.0, 2.8)    # CLAUDE.md: ENV > ACC
        vel_ratio = random.uniform(3.5, 5.5)
        rows.extend(_rows(
            equip_cd,
            fault_start + timedelta(days=i),
            _clip(stats["ACC"]["mean"] * acc_ratio),
            _clip(stats["ENV"]["mean"] * env_ratio),
            _clip(stats["VEL"]["mean"] * vel_ratio),
            0.0, 0,
        ))
    return rows