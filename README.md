# Predictive Asset Maintenance System

자동차 의장 라인 LN21의 모터 설비 6대 센서 데이터를 기반으로 이상 징후를 예측하고, 이상 유형과 잔여수명(RUL)을 분석한 뒤 AI 에이전트가 보전 조치를 안내하는 예지보전 프로토타입입니다.

## 현재 구현 범위

현재 코드는 데이터 증강, 모델 학습, PM API, LangGraph 기반 Agent API, Vue 프론트엔드의 기본 흐름까지 구현되어 있습니다.

생성 데이터와 학습 모델은 저장소에 커밋하지 않습니다. 실행 시 아래 순서로 직접 생성해야 합니다.

1. 원본 CSV에서 증강 데이터 생성
2. ExtraTrees 예측 모델, 이상 유형 분류기, RUL 모델 학습
3. PM API 실행
4. Agent API 실행
5. Vue 프론트엔드 실행

## 프로젝트 구조

```text
pm-agent/
├── backend/
│   ├── augment/        # 센서 데이터 증강 로직
│   ├── train/          # 예측/분류/RUL 모델 학습 스크립트
│   ├── pm_api/         # FastAPI PM API (:8000)
│   ├── agent/          # LangGraph Agent API (:8001)
│   └── data/
│       ├── raw/        # 원본 CSV
│       ├── augmented/  # 생성 산출물, git 제외
│       └── model_registry/ # 학습 모델 산출물, git 제외
├── frontend/           # Vue 3 + Pinia + Vite
├── CLAUDE.md           # 프로젝트 기준 수치와 구현 컨텍스트
├── SPEC.md             # API/도구/컴포넌트 입출력 스펙
└── COMMANDS.md         # 단계별 구현 명령 기록
```

## 핵심 데이터

대상 설비는 6대입니다.

```text
MTR-21A01-CNV01
MTR-21A09-CNV01
MTR-21A12-CNV01
MTR-22B01-CNV01
MTR-22B09-CNV01
MTR-22B12-CNV01
```

입력 센서는 `ACC`, `ENV`, `VEL` 3종이고, `STATUS` 태그는 정상/이상 타겟 값으로 사용합니다.

상태 판정 기준은 다음과 같습니다.

```text
predict_value > 0.9  → 정상
predict_value > 0.7  → 주의
predict_value > 0.5  → 경고
그 외                → 위험
```

## 데이터 증강 로직

[backend/augment/generator.py](backend/augment/generator.py)는 설비별 정상 통계를 기준으로 시계열 데이터를 생성합니다.

- 정상 구간: AR(1) 자기상관 계수 `phi=0.7`을 적용해 연속성 있는 센서값 생성
- Spike: 짧은 기간 센서 급등, `VEL` 배율이 `ACC`보다 크게 생성
- Creep: 7일 경고 구간에서 `VEL`이 점진 상승한 뒤 이상 구간 진입
- Drift: 장기 이상, `ENV` 배율이 `ACC`보다 크게 생성
- 모든 센서값은 `0.001 ~ 18.5` 범위로 클리핑

[backend/augment/run_augment.py](backend/augment/run_augment.py)는 원본 `TB_SNSR_RAW_DATA.csv`와 증강 데이터를 합쳐 다음 파일을 생성합니다.

```text
backend/data/augmented/TB_SNSR_AUGMENTED.csv
```

## 모델 학습 로직

학습 스크립트는 모두 `backend/data/augmented/TB_SNSR_AUGMENTED.csv`를 입력으로 사용합니다.

### 1. 상태 예측 모델

[backend/train/train_predictor.py](backend/train/train_predictor.py)

- 입력 피처: `ACC`, `ENV`, `VEL`
- 타겟: `STATUS`
- 모델: `ExtraTreesRegressor(n_estimators=300, random_state=42)`
- 스케일러: `StandardScaler`
- 평가: R2, RMSE, MAE, PR-AUC
- 산출물:
  - `backend/data/model_registry/extra_trees.pkl`
  - `backend/data/model_registry/scaler.pkl`
  - `backend/data/model_registry/thresholds.json`

### 2. 이상 유형 분류기

[backend/train/train_fault_classifier.py](backend/train/train_fault_classifier.py)

- 분류 대상: `Spike`, `Creep`, `Drift`
- 피처: 최근 7일 `ACC/ENV/VEL` 평균·표준편차, `VEL` 기울기, `ACC/VEL` 비율
- 모델: `RandomForestClassifier(n_estimators=200, random_state=42)`
- 산출물:
  - `backend/data/model_registry/fault_classifier.pkl`

### 3. RUL 모델

[backend/train/train_rul_model.py](backend/train/train_rul_model.py)

- 목적: 이상 시작일까지 남은 일수 예측
- 학습 범위: 이상 시작 30일 전까지
- 피처: `VEL` 7일 이동평균, `VEL` 증가율, `ACC/VEL` 비율
- 모델: `GradientBoostingRegressor(n_estimators=200, random_state=42)`
- 산출물:
  - `backend/data/model_registry/rul_model.pkl`

## PM API 로직

[backend/pm_api/main.py](backend/pm_api/main.py)는 FastAPI 기반 PM API입니다.

주요 엔드포인트:

```text
GET  /health
POST /predict/from-db
GET  /raw-data
GET  /models/definitions
```

[backend/pm_api/predictor.py](backend/pm_api/predictor.py)는 다음 두 경로로 예측합니다.

- `ExtraTreesRegressor`: `scaler.transform([[ACC, ENV, VEL]])` 후 모델 예측
- 선형 11종 모델: `TB_AI_MDL_PARAM.csv`의 모델별 계수를 사용해 개별 계산

선형 모델은 계수를 평균화하지 않습니다. 특히 `HuberRegressor`, `LinearSVR`는 절편 스케일이 달라 다른 선형 모델과 섞지 않습니다.

## Agent API 로직

[backend/agent/main.py](backend/agent/main.py)는 SSE 기반 채팅 API입니다.

```text
POST /chat/stream
GET  /health
DELETE /chat/threads/{thread_id}
```

[backend/agent/graph.py](backend/agent/graph.py)는 LangGraph ReAct Single Agent 구조입니다.

- LLM: 환경변수 `LLM_MODEL`, 기본값 `gpt-4o-mini`
- Checkpointer: `MemorySaver`
- ToolNode: `agent.tools.ALL_TOOLS`
- 스트리밍: `graph.astream_events(..., version="v2")`

SSE 이벤트 타입:

```text
thread_id
tool_call
tool_result
fault_card
rul_card
answer
done
```

## Agent 도구

Agent는 다음 도구를 사용합니다.

API 연동 도구:

- `check_health`
- `get_equipment_status`
- `get_raw_sensor_data`
- `predict_single_equip`
- `get_model_definitions`

데이터 분석 도구:

- `summarize_equipment_status`
- `find_missing_features`
- `compare_model_metrics`
- `get_feature_contribution`
- `analyze_trend`
- `classify_fault_type`

리포트 도구:

- `estimate_rul`
- `make_work_order_draft`

PM API가 사용할 수 없는 경우 일부 도구는 `PM_API_UNAVAILABLE`을 반환하고, Agent는 CSV 기반 분석 도구로 우회할 수 있도록 설계되어 있습니다.

## 프론트엔드 로직

프론트엔드는 Vue 3 + Pinia + Vite 기반입니다.

- [frontend/src/App.vue](frontend/src/App.vue): 전체 레이아웃, 상단 바, 사이드바/채팅 패널 배치
- [frontend/src/components/SidebarPanel.vue](frontend/src/components/SidebarPanel.vue): 설비 목록과 요약 상태
- [frontend/src/components/ChatPanel.vue](frontend/src/components/ChatPanel.vue): Agent SSE 채팅 UI
- [frontend/src/components/ToolStepCard.vue](frontend/src/components/ToolStepCard.vue): 도구 호출/결과 표시
- [frontend/src/components/FaultTypeCard.vue](frontend/src/components/FaultTypeCard.vue): 이상 유형 카드
- [frontend/src/components/RULCard.vue](frontend/src/components/RULCard.vue): 잔여수명 카드
- [frontend/src/stores/chat.js](frontend/src/stores/chat.js): 채팅 메시지, SSE 이벤트 처리
- [frontend/src/stores/dashboard.js](frontend/src/stores/dashboard.js): 설비 상태 polling

## 실행 순서

### 1. 백엔드 의존성 설치

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 증강 데이터 생성

```bash
cd backend
python -m augment.run_augment
```

### 3. 모델 학습

```bash
cd backend
python -m train.train_predictor
python -m train.train_fault_classifier
python -m train.train_rul_model
```

### 4. PM API 실행

```bash
cd backend
uvicorn pm_api.main:app --host 0.0.0.0 --port 8000
```

### 5. Agent API 실행

별도 터미널에서 실행합니다.

```bash
cd backend
export OPENAI_API_KEY=your_api_key
export PM_API_BASE=http://localhost:8000
uvicorn agent.main:app --host 0.0.0.0 --port 8001
```

### 6. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

기본 접속 주소:

```text
http://localhost:5173
```

## 환경변수

주요 환경변수는 다음과 같습니다.

```text
OPENAI_API_KEY=
LLM_MODEL=gpt-4o-mini
PM_API_BASE=http://localhost:8000
AGENT_API_PORT=8001
MONITORING_BACKEND=langsmith
LANGCHAIN_PROJECT=pm-agent
LANGCHAIN_API_KEY=
DATA_DIR=
MODEL_DIR=
RECURSION_LIMIT=20
```

## Git에서 제외되는 산출물

다음 파일과 디렉터리는 `.gitignore`로 제외됩니다.

```text
.env
.DS_Store
__pycache__/
node_modules/
dist/
backend/data/augmented/
backend/data/model_registry/
```

따라서 새 환경에서는 증강 데이터 생성과 모델 학습을 먼저 실행해야 API와 Agent 도구가 정상 동작합니다.

## 현재 주의사항

- `backend/data/augmented/`와 `backend/data/model_registry/`는 커밋되지 않으므로 실행 전 생성해야 합니다.
- `docker-compose.yml`은 존재하지만 현재 저장소에는 Dockerfile이 포함되어 있지 않습니다. 현재 기준 실행은 로컬 Python/Vite 명령을 기준으로 합니다.
- Agent API는 OpenAI API 키가 필요합니다.
- 프론트엔드 빌드/실행 전 `npm install`이 필요합니다.
