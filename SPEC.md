# 설비 예지보전 에이전트 — 상세 스펙

> CLAUDE.md(수치/구조) + COMMANDS.md(명령 순서)와 함께 사용.
> 이 파일은 각 컴포넌트의 입출력 스펙과 시나리오 흐름을 정의합니다.

---

## 1. 데이터 증강 스펙

### 입력 원본 (변경 불가)
```
backend/data/raw/TB_SNSR_RAW_DATA.csv
  MEAS_DT, TAG_CD, MEAS_VAL, STATUS
  960행, 2026-04-01 ~ 2026-05-10, STATUS 컬럼 전체 GOOD

TAG_CD 형식: {설비코드}-{센서종류}
  센서종류: ACC, ENV, VEL, STATUS (4종)
  설비코드: MTR-21A01-CNV01 등 6종
```

### 출력 증강 파일
```
backend/data/augmented/TB_SNSR_AUGMENTED.csv
  동일 컬럼 구조 유지 (MEAS_DT, TAG_CD, MEAS_VAL, STATUS)
  목표 행수: 9,000행 이상
  날짜 범위: 2026-04-01 ~ 2027-04-30 (약 13개월)
  STATUS=0 비율: 25~30%
```

### 이상 유형별 센서 패턴 (구현 기준)
```
Spike 이상 시:
  ACC 배율: 3.5 ~ 30.3x  (설비별 정상 평균 대비)
  ENV 배율: ACC × 0.9 수준
  VEL 배율: ACC × 1.1 이상 (VEL > ACC 항상 성립)
  지속: 3~7일, 이후 정상 복구

Creep 이상 시:
  경고 구간(7일): VEL 1.0x → 2.5x 선형 증가, STATUS=1.0 유지
  이상 구간(4일): VEL 7.1x, ACC 2.2x, ENV 3.1x, STATUS=0.0
  복구: 이상 종료 후 정상으로 즉시 복귀

Drift 이상 시:
  ACC 배율: 1.5 ~ 2.1x
  ENV 배율: 2.0 ~ 2.8x (ENV > ACC 항상 성립)
  VEL 배율: 3.5 ~ 5.5x
  지속: 14일 이상, 미복구 가능
```

---

## 2. 예측 파이프라인 스펙

### 입력 피처 (3개)
```
ACC: 가속도진동 (float)
ENV: 환경진동   (float)
VEL: 회전속도   (float)
```

### 예측 경로 1 — ExtraTrees PKL
```python
X = scaler.transform([[ACC, ENV, VEL]])
predict_value = model.predict(X)[0]  # 0.0 ~ 1.0 연속값
status = make_status(predict_value)
```

### 예측 경로 2 — 선형 11종
```python
# 각 알고리즘별 개별 계산 (평균화 금지)
predict_value = ACC*coeff_acc + ENV*coeff_env + VEL*coeff_vel + intercept
predict_value = max(0.0, predict_value)  # clip lower=0
status = make_status(predict_value)
```

### 상태 판정 함수
```python
def make_status(value: float) -> str:
    if value > 0.9:  return "정상"
    if value > 0.7:  return "주의"
    if value > 0.5:  return "경고"
    return "위험"
```

---

## 3. API 스펙

### PM API (:8000)

#### POST /predict/from-db
```json
Request:  {"equip_cd": "MTR-21A01-CNV01", "date": "2026-06-09"}
Response: {
  "equip_cd": "MTR-21A01-CNV01",
  "predict_value": 0.834,
  "status": "경고",
  "sensor_values": {"ACC": 9.23, "ENV": 7.81, "VEL": 3.14},
  "model_results": {
    "ExtraTreesRegressor": {"value": 0.821, "status": "경고"},
    "Ridge": {"value": 0.847, "status": "경고"}
  },
  "meas_dt": "2026-06-09"
}
```

#### GET /raw-data
```json
Request:  ?equip_cd=MTR-21A01-CNV01&days=7
Response: {
  "equip_cd": "MTR-21A01-CNV01",
  "data": [
    {"date": "2026-06-03", "ACC": 8.91, "ENV": 7.23, "VEL": 2.94, "status_val": 1.0},
    ...
  ]
}
```

### Agent API (:8001)

#### POST /chat/stream (SSE)
```
Content-Type: text/event-stream

data: {"type": "thread_id", "content": "a3f9bc12de45"}
data: {"type": "tool_call", "content": "[도구 호출] get_equipment_status"}
data: {"type": "tool_result", "content": "[도구 결과] get_equipment_status: {\"total\": 6, ...}"}
data: {"type": "fault_card", "content": {"fault_type": "Creep", "confidence": 0.87, "evidence": ["VEL_7d_slope: +0.18/day", "VEL/ACC_ratio: 1.23"]}}
data: {"type": "rul_card", "content": {"rul_days": 4, "confidence": 0.72, "basis": "VEL 추세 외삽 (R²=0.81)"}}
data: {"type": "answer", "content": "MTR-21A09의 현재 상태는..."}
data: {"type": "answer", "content": " 경고 수준으로"}
data: {"type": "done"}
```

---

## 4. 도구 입출력 스펙

### classify_fault_type
```python
Input:  equip_cd: str, window_days: int = 7
Output: str (JSON)
{
  "equip_cd": "MTR-21A09-CNV01",
  "fault_type": "Spike",      # "Spike" | "Creep" | "Drift" | "Normal"
  "confidence": 0.87,
  "evidence": [
    "VEL_배율_vs_ACC배율: 2.74 (VEL > ACC → Spike 특징)",
    "STATUS=0 당일 센서 급등: +847%"
  ],
  "recommended_action": "즉시 가동 중단 및 이물질/충격 원인 점검"
}
```

### estimate_rul
```python
Input:  equip_cd: str
Output: str (JSON)
{
  "equip_cd": "MTR-22B12-CNV01",
  "rul_days": 4,
  "recommended_maintenance_date": "2026-06-11",
  "confidence": 0.72,
  "basis": "VEL 일간 증가율 +0.18/일, UCL_2σ(5.034) 도달 예상 4.4일",
  "historical_reference": "2026-04-15 동일 설비: UCL 도달 2일 후 STATUS=0 발생"
}
```

### make_work_order_draft
```python
Input: equip_cd, status, fault_type, predict_value,
       abnormal_tags, estimated_rul, meas_dt, model_name

Output: str (마크다운 형식)
# 설비 보전 작업 지시서

**발행일시**: 2026-06-09 14:23
**설비코드**: MTR-21A09-CNV01

## 현황
- 예측 상태: 경고 (PREDICT_VALUE: 0.83)
- 이상 유형: Creep형 (점진적 열화)
- 예상 잔여 가동일: 약 4일

## 이상 근거
...

## 조치 항목
□ 베어링 윤활 상태 육안 점검
...
```

---

## 5. 프론트엔드 컴포넌트 스펙

### FaultTypeCard.vue Props
```typescript
interface FaultResult {
  fault_type: 'Spike' | 'Creep' | 'Drift' | 'Normal'
  confidence: number          // 0.0 ~ 1.0
  evidence: string[]          // 근거 문자열 배열
  recommended_action: string
}
```

색상 매핑:
- Spike → `--danger` (#E03E4D), 아이콘: ⚡
- Creep → `--warning` (#F08A00), 아이콘: 📈
- Drift → brand (#1B5BD9), 아이콘: 🌊
- Normal → `--success` (#1FA66B), 아이콘: ✅

### RULCard.vue Props
```typescript
interface RULResult {
  rul_days: number
  recommended_maintenance_date: string
  confidence: number
  basis: string
  historical_reference?: string
}
```

긴급도 색상:
- rul_days <= 3  → `--danger`
- rul_days <= 7  → `--warning`
- rul_days <= 14 → brand
- rul_days > 14  → `--success`

---

## 6. 시나리오별 예상 도구 호출 시퀀스

| 시나리오 | 호출 순서 | 예상 SSE 이벤트 |
|---------|---------|--------------|
| 1. 전체 현황 | get_equipment_status → summarize_line | tool_call×2, answer |
| 2. 추세 분석 | analyze_trend → get_raw_sensor_data | tool_call×2, answer |
| 3. 원인 분석 | predict_single + get_raw_sensor_data + get_feature_contribution + classify_fault_type | tool_call×4, fault_card, answer |
| 4. 유형 분류 | classify_fault_type | tool_call×1, fault_card, answer |
| 5. 모델 점검 | get_model_definitions + compare_model_metrics | tool_call×2, answer |
| 6. 품질 확인 | summarize_equipment_status + find_missing_features | tool_call×2, answer |
| 7. 작업지시서 | get_equipment_status + classify_fault_type + make_work_order_draft | tool_call×3, fault_card, answer |
| 8. RUL 예측 | get_raw_sensor_data + estimate_rul | tool_call×2, rul_card, answer |

---

## 7. Docker Compose 스펙

```yaml
services:
  pm-api:
    build: ./backend
    ports: ["8000:8000"]
    volumes: ["./backend/data:/app/data"]
    command: uvicorn pm_api.main:app --host 0.0.0.0 --port 8000

  agent-api:
    build: ./backend
    ports: ["8001:8001"]
    volumes: ["./backend/agent:/app/agent", "./backend/data:/app/data"]
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - PM_API_BASE=http://pm-api:8000
    depends_on: [pm-api]
    command: uvicorn agent.main:app --host 0.0.0.0 --port 8001 --reload

  frontend:
    build: ./frontend
    ports: ["5173:5173"]
    environment:
      - VITE_API_BASE=http://localhost:8001
    depends_on: [agent-api]
    command: npm run dev -- --host
```
