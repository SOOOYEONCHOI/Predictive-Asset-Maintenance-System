# 설비 예지보전 AI 에이전트 — 프로젝트 컨텍스트

> Claude Code가 이 파일을 가장 먼저 읽어야 합니다.
> 모든 구현 결정은 이 문서의 수치와 구조를 기준으로 합니다.

---

## 프로젝트 개요

자동차 의장 라인(LN21) 모터 설비 6대의 센서 데이터를 기반으로
이상 징후를 예측·분류하고 보전 조치를 자연어로 안내하는 AI 에이전트.

| 항목 | 값 |
|------|-----|
| 에이전트 유형 | LangGraph ReAct Single Agent |
| LLM | gpt-4o-mini |
| 백엔드 | FastAPI (Python 3.12) |
| 프론트엔드 | Vue 3 + Pinia |
| 스트리밍 | SSE (Server-Sent Events) |
| 모니터링 | LangSmith |

---

## 디렉토리 구조 (반드시 이 구조로 생성)

```
pm-agent/
├── CLAUDE.md                        ← 이 파일
├── docker-compose.yml
├── .env.example
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   │
│   ├── data/                        ← 원본 CSV + 증강 CSV + 모델 파일
│   │   ├── raw/
│   │   │   ├── TB_SNSR_RAW_DATA.csv
│   │   │   ├── TB_AI_MDL_PARAM.csv
│   │   │   ├── TB_AI_MDL_RSLT_SMMRY.csv
│   │   │   └── TM_MST_MODEL_DEFINE.csv
│   │   ├── augmented/
│   │   │   └── TB_SNSR_AUGMENTED.csv   ← 생성 대상
│   │   └── model_registry/
│   │       ├── extra_trees.pkl
│   │       ├── fault_classifier.pkl
│   │       ├── rul_model.pkl
│   │       ├── scaler.pkl
│   │       └── thresholds.json
│   │
│   ├── augment/                     ← Phase 1: 데이터 증강
│   │   ├── __init__.py
│   │   ├── generator.py             ← 4종 이상 시나리오 생성
│   │   └── run_augment.py           ← 실행 진입점
│   │
│   ├── train/                       ← Phase 2: 모델 학습
│   │   ├── __init__.py
│   │   ├── train_predictor.py       ← ExtraTrees 학습
│   │   ├── train_fault_classifier.py ← Spike/Creep/Drift 분류기
│   │   └── train_rul_model.py       ← 잔여수명 회귀
│   │
│   ├── pm_api/                      ← PM API (:8000)
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── predictor.py
│   │   └── schemas.py
│   │
│   └── agent/                       ← Agent API (:8001)
│       ├── __init__.py
│       ├── main.py                  ← FastAPI 진입점
│       ├── graph.py                 ← LangGraph 그래프
│       ├── prompts/
│       │   └── system_prompt.py
│       └── tools/
│           ├── __init__.py
│           ├── api_tools.py         ← PM API 연동 (5종)
│           ├── data_tools.py        ← 데이터 분석 (6종)
│           └── report_tools.py      ← 리포트 (2종)
│
└── frontend/                        ← Vue 3 앱 (:5173)
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.vue
        ├── components/
        │   ├── SidebarPanel.vue
        │   ├── ChatPanel.vue
        │   ├── ToolStepCard.vue
        │   ├── FaultTypeCard.vue    ← 신규: 이상 유형 시각화
        │   └── RULCard.vue          ← 신규: 잔여수명 게이지
        ├── stores/
        │   ├── chat.js
        │   └── dashboard.js
        └── composables/
            └── useSSE.js
```

---

## 핵심 데이터 수치 (모든 구현의 기준값)

### 설비 목록 (6대)
```
MTR-21A01-CNV01, MTR-21A09-CNV01, MTR-21A12-CNV01
MTR-22B01-CNV01, MTR-22B09-CNV01, MTR-22B12-CNV01
```

### 설비별 정상 구간 센서 통계 (증강 기준값)
```json
{
  "MTR-21A01-CNV01": {"ACC": {"mean": 8.873, "std": 0.226}, "ENV": {"mean": 6.443, "std": 1.503}, "VEL": {"mean": 2.848, "std": 0.591}},
  "MTR-21A09-CNV01": {"ACC": {"mean": 3.909, "std": 3.736}, "ENV": {"mean": 2.491, "std": 2.458}, "VEL": {"mean": 1.149, "std": 0.927}},
  "MTR-21A12-CNV01": {"ACC": {"mean": 6.453, "std": 4.426}, "ENV": {"mean": 4.579, "std": 3.264}, "VEL": {"mean": 1.869, "std": 1.288}},
  "MTR-22B01-CNV01": {"ACC": {"mean": 3.334, "std": 3.666}, "ENV": {"mean": 2.600, "std": 2.439}, "VEL": {"mean": 1.731, "std": 1.319}},
  "MTR-22B09-CNV01": {"ACC": {"mean": 0.421, "std": 0.160}, "ENV": {"mean": 0.411, "std": 0.127}, "VEL": {"mean": 0.380, "std": 0.140}},
  "MTR-22B12-CNV01": {"ACC": {"mean": 9.925, "std": 4.360}, "ENV": {"mean": 8.421, "std": 4.205}, "VEL": {"mean": 3.657, "std": 1.695}}
}
```

### UCL 임계값 (전체 정상 구간 기준)
```json
{
  "ACC": {"mean": 5.440, "std": 4.676, "ucl_1s": 10.116, "ucl_2s": 14.792, "ucl_3s": 19.469},
  "ENV": {"mean": 4.137, "std": 3.772, "ucl_1s": 7.908,  "ucl_2s": 11.680, "ucl_3s": 15.452},
  "VEL": {"mean": 1.936, "std": 1.549, "ucl_1s": 3.485,  "ucl_2s": 5.034,  "ucl_3s": 6.582}
}
```

### 상태 판정 기준
```
PREDICT_VALUE > 0.9   → 정상  (UCL 1σ 미만)
0.7 ~ 0.9            → 주의  (ACC UCL 1σ 이상)
0.5 ~ 0.7            → 경고  (ACC UCL 2σ 이상)
< 0.5                → 위험  (ACC UCL 3σ 이상)
```

### 이상 유형 3종 분류 기준
```
Spike (급격형):  STATUS=0 당일 센서 급등. VEL 배율 > ACC 배율. 기계적 충격/이물질.
Creep (점진형):  이상 7일 전부터 VEL 점진 상승. 베어링 마모/윤활 부족.
Drift (누적형):  장기 미복구. ENV 배율 > ACC 배율. 구조적 이완/열변형.
```

### 실제 이상 이력 (증강 템플릿으로 사용)
```json
{
  "MTR-21A01-CNV01": {"type": "drift",     "period": ["2025-10-13","2025-10-22"], "recovered": false, "acc_ratio": 1.8, "env_ratio": 2.4, "vel_ratio": 4.6},
  "MTR-21A09-CNV01": {"type": "spike",     "period": ["2025-09-21","2025-10-01"], "recovered": true,  "acc_ratio": 3.5, "env_ratio": 5.3, "vel_ratio": 9.6},
  "MTR-21A12-CNV01": {"type": "creep",     "period": ["2025-10-08","2025-10-10"], "recovered": true,  "acc_ratio": 2.2, "env_ratio": 3.1, "vel_ratio": 7.1},
  "MTR-22B01-CNV01": {"type": "spike",     "period": ["2025-09-29","2025-10-01"], "recovered": true,  "acc_ratio": 4.3, "env_ratio": 4.7, "vel_ratio": 5.4},
  "MTR-22B09-CNV01": {"type": "recurring", "period": [["2025-09-20","2025-09-22"],["2025-10-16","2025-10-18"]], "recovered": true, "acc_ratio": 30.3, "vel_ratio": 17.3},
  "MTR-22B12-CNV01": {"type": "recurring", "period": [["2025-09-27","2025-09-29"],["2025-10-20","2025-10-22"]], "recovered": false, "acc_ratio": 1.5, "vel_ratio": 2.8}
}
```

### 선형 모델 계수 (TB_AI_MDL_PARAM 전체)
```
예측 공식: PREDICT_VALUE = ACC×c1 + ENV×c2 + VEL×c3 + 절편
주의: HuberRegressor, LinearSVR의 절편(0.41)은 타 모델(0.87~0.88)과 달라 계수 평균화 금지

Ridge/RidgeCV/BayesianRidge/LinearRegression: ACC=-0.004, ENV=-0.011, VEL=-0.060, 절편=0.877
ARDRegression:   ACC=0.000,  ENV=-0.016, VEL=-0.059, 절편=0.874
ElasticNetCV:    ACC=-0.004, ENV=-0.012, VEL=-0.059, 절편=0.876
ElasticNet:      ACC=0.000,  ENV=-0.032, VEL=-0.022, 절편=0.814
HuberRegressor:  ACC=+0.133, ENV=-0.485, VEL=-0.099, 절편=0.414  ← 개별 계산만
LinearSVR:       ACC=+0.115, ENV=-0.443, VEL=-0.123, 절편=0.404  ← 개별 계산만
SGDRegressor:    ACC=-0.069, ENV=-0.124, VEL=-0.240, 절편=0.454
TweedieRegressor:ACC=-0.090, ENV=-0.104, VEL=-0.125, 절편=0.455
```

### 채택 모델 성능 (USE_YN=Y, TB_AI_MDL_RSLT_SMMRY)
```
ExtraTreesRegressor:          R²=0.860, RMSE=0.187  ← 주력 PKL 모델
RandomForestRegressor:        R²=0.845, RMSE=0.197
HistGradientBoostingRegressor:R²=0.844, RMSE=0.197
선형 그룹 (ARD/ElasticNetCV/Ridge/RidgeCV/BayesianRidge/LinearRegression): R²=0.702
SGDRegressor: R²=0.689
ElasticNet:   R²=0.655
LinearSVR:    R²=0.641
HuberRegressor: R²=0.640
TweedieRegressor: R²=0.629
```

---

## 구현 순서 (Phase별 의존성)

```
Phase 1 → Phase 2 → Phase 3 → Phase 4
(증강)    (학습)    (API)      (프론트)

각 Phase는 이전 Phase 완료 후 시작.
Phase 1 산출물: backend/data/augmented/TB_SNSR_AUGMENTED.csv
Phase 2 산출물: backend/data/model_registry/*.pkl, thresholds.json
Phase 3 산출물: 동작하는 /chat/stream SSE 엔드포인트
Phase 4 산출물: Vue 앱에서 8개 시나리오 동작
```

---

## 환경변수 (.env)

```
OPENAI_API_KEY=
LLM_MODEL=gpt-4o-mini
PM_API_BASE=http://pm-api:8000
AGENT_API_PORT=8001
MONITORING_BACKEND=langsmith
LANGCHAIN_PROJECT=pm-agent
LANGCHAIN_API_KEY=
DATA_DIR=/app/data
MODEL_DIR=/app/data/model_registry
RECURSION_LIMIT=20
```

---

## 절대 하지 말아야 할 것

1. HuberRegressor와 LinearSVR의 계수를 다른 선형 모델과 평균하지 말 것
2. STATUS 태그(가동여부)를 예측 피처로 사용하지 말 것 (data leakage)
3. SMOTE를 테스트 데이터에 적용하지 말 것 (훈련셋에만)
4. 증강 데이터와 원본 데이터를 날짜 연속성 없이 단순 concat하지 말 것
5. 설비별 정상 통계를 전체 평균으로 대체하지 말 것 (MTR-22B09의 ACC 평균 0.421은 다른 설비와 전혀 다름)


## UI 레퍼런스

`ui-preview/pm-agent-ui.html` 이 파일이 프론트엔드의 유일한 디자인 기준입니다.
Vue 컴포넌트 구현 시 이 파일의 모든 CSS 변수, 클래스명, 구조를 그대로 따릅니다.

### 컴포넌트 → HTML 클래스 매핑

| Vue 컴포넌트 | HTML 기준 클래스 |
|---|---|
| SidebarPanel.vue | .sidebar, .sidebar-kpi, .equip-section, .scenario-section, .monitor-section |
| ChatPanel.vue | .chat-panel, .chat-header, .stat-bar, .messages, .input-area |
| ToolStepCard.vue | .tool-step, .step-head, .step-icon, .step-body |
| FaultTypeCard.vue | .result-card, .fault-card-head, .fault-type-badge, .conf-bar-wrap, .evidence-list, .fault-action |
| RULCard.vue | .result-card, .rul-card-head, .rul-main, .rul-number, .rul-gauge, .rul-basis |

### 반드시 지킬 것
- CSS 변수는 모두 App.vue :root 에 선언 (--bg, --surface, --brand 등 html 파일과 동일)
- FaultTypeCard의 fault_type 값(Spike/Creep/Drift)에 따라 .spike/.creep/.drift 클래스 동적 바인딩
- RULCard의 rul_days 값에 따라 .safe/.warn/.danger 클래스 동적 바인딩
- 시나리오 4번, 8번 버튼에 .s-tag.new 배지 표시