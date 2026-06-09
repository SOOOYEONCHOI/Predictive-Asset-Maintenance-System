# Claude Code 명령 가이드

> 이 파일의 명령을 순서대로 Claude Code에 붙여넣으세요.
> 각 명령은 완료를 확인한 후 다음으로 넘어가세요.

---

## 사전 준비 (Claude Code 시작 전)

```bash
# 1. 프로젝트 폴더 생성 후 진입
mkdir pm-agent && cd pm-agent

# 2. 컨텍스트 파일 4개를 루트에 복사
#    - CLAUDE.md
#    - SPEC.md
#    - COMMANDS.md
#    - data_summary.json

# 3. UI 레퍼런스 HTML 배치
mkdir -p ui-preview
cp pm-agent-ui.html ui-preview/

# 4. 원본 CSV 4개를 backend/data/raw/ 에 복사
mkdir -p backend/data/raw
cp TB_SNSR_RAW_DATA.csv TB_AI_MDL_PARAM.csv \
   TB_AI_MDL_RSLT_SMMRY.csv TM_MST_MODEL_DEFINE.csv \
   backend/data/raw/

# 5. 최종 구조 확인 후 Claude Code 실행
# pm-agent/
# ├── CLAUDE.md                  ← Claude Code 자동 로드
# ├── SPEC.md
# ├── COMMANDS.md
# ├── data_summary.json
# ├── ui-preview/
# │   └── pm-agent-ui.html       ← Vue 구현의 유일한 디자인 기준
# └── backend/data/raw/          ← CSV 4개
claude
```

---

## Phase 0 — 프로젝트 스캐폴딩

```
CLAUDE.md와 SPEC.md를 읽고 전체 디렉토리 구조를 생성해줘.

구체적으로:
1. CLAUDE.md의 디렉토리 구조 섹션대로 모든 폴더와 __init__.py 파일 생성
2. docker-compose.yml 생성 (pm-api:8000, agent-api:8001, frontend:5173 세 서비스)
3. backend/requirements.txt 생성:
   - fastapi uvicorn httpx pandas numpy scikit-learn
   - xgboost imbalanced-learn shap joblib
   - langchain langchain-openai langgraph
   - langsmith python-dotenv
4. frontend/package.json 생성 (vue3, pinia, vite, marked)
5. .env.example 생성 (CLAUDE.md의 환경변수 섹션 참조)

파일 내용은 최소한으로, 구조 생성에 집중해줘.
```

---

## Phase 1 — 데이터 증강

### 명령 1-A: 증강 생성기 구현

```
backend/augment/generator.py를 구현해줘.

CLAUDE.md의 "핵심 데이터 수치" 섹션의 수치를 그대로 사용해야 해.

구현할 함수 4개:

1. generate_normal_period(equip_cd, start_date, days)
   - CLAUDE.md의 설비별 정상 통계를 기준값으로 사용
   - AR(1) 자기상관 계수 phi=0.7로 연속성 있는 시계열 생성
   - STATUS 태그는 항상 MEAS_VAL=1.0
   - 반환: List[dict] (MEAS_DT, TAG_CD, MEAS_VAL, STATUS 컬럼)

2. generate_spike_fault(equip_cd, fault_start, fault_days=5)
   - 정상→이상 당일 센서 급등 (VEL 배율이 ACC 배율보다 크게)
   - 이상 구간 MEAS_VAL은 설비별 정상 평균 × 랜덤 배율(3~15x)
   - STATUS 태그 MEAS_VAL=0.0

3. generate_creep_fault(equip_cd, fault_start, warning_days=7, fault_days=4)
   - warning_days 동안 VEL 1.0x → 2.5x 점진 상승 (STATUS=1.0 유지)
   - fault_days 동안 전 센서 2~7x, STATUS=0.0
   - 경고 구간(warning_days)이 에이전트의 '주의' 경보 트리거용

4. generate_drift_fault(equip_cd, fault_start, drift_days=14)
   - ENV 배율 > ACC 배율 (ENV 2.0~2.8x, ACC 1.5~2.1x)
   - VEL 3.5~5.5x, STATUS=0.0 전 기간 유지

모든 함수는 MEAS_VAL을 max(0.001, min(val, 18.5)) 로 클리핑.
반환 타입은 동일하게 List[dict].
```

### 명령 1-B: 증강 실행 스크립트

```
backend/augment/run_augment.py를 구현해줘.

다음 증강 계획대로 데이터를 생성하고
backend/data/augmented/TB_SNSR_AUGMENTED.csv 로 저장해줘:

증강 계획:
- 정상 구간: 각 설비별 220일치 (2026-05-11 ~ 2027-01-17)
  generator.generate_normal_period() 사용

- 이상 에피소드 (각 설비당 연간 2~3회):
  - Spike: 4~5일 지속, 복구 후 60~90일 정상
  - Creep: 경고 7일 + 이상 4일, 복구 후 60일 정상
  - Drift: 14일 지속 (미복구 설비는 데이터 종료)
  - Recurring: Spike 패턴 45~90일 간격으로 3회 반복

- 원본 데이터(raw/TB_SNSR_RAW_DATA.csv)와 concat 시
  날짜 기준 오름차순 정렬 필수

최종 저장 후 아래 통계를 출력해줘:
  - 전체 행수
  - STATUS=0 비율
  - 설비별 행수
  - 날짜 범위
```

---

## Phase 2 — 모델 학습

### 명령 2-A: 예측 모델 학습

```
backend/train/train_predictor.py를 구현하고 실행해줘.

데이터: backend/data/augmented/TB_SNSR_AUGMENTED.csv

전처리:
1. pivot_table로 (EQUIP_CD, MEAS_DT) × TAG_TYPE → 피처 매트릭스 생성
2. STATUS 태그는 타겟(y)으로 사용, 피처(X)에서 제거 (data leakage 방지)
3. 피처: ACC, ENV, VEL (3개)
4. 타겟: STATUS (0.0 or 1.0)
5. Stratified 80:20 분할

모델:
- ExtraTreesRegressor (n_estimators=300, random_state=42)
- StandardScaler 적용

평가:
- R², RMSE, MAE 출력
- PR-AUC 출력 (타겟 불균형 고려)

저장:
- backend/data/model_registry/extra_trees.pkl
- backend/data/model_registry/scaler.pkl
- backend/data/model_registry/thresholds.json
  {"status_threshold": 0.5, "ucl": {"ACC": {"1s":10.116,"2s":14.792,"3s":19.469}, ...}}
  (CLAUDE.md의 UCL 임계값 그대로 저장)
```

### 명령 2-B: 이상 유형 분류기 학습

```
backend/train/train_fault_classifier.py를 구현하고 실행해줘.

목적: 센서 패턴으로 Spike/Creep/Drift 3종 분류

피처 엔지니어링 (증강 데이터 기반):
- 최근 7일 ACC/ENV/VEL 평균, 표준편차 (6개)
- 최근 7일 VEL 증가율 기울기 (1개)
- ACC/VEL 비율 (1개)
- STATUS=0 직전 구간 레이블:
  - spike: VEL 기울기 급격 + ACC/VEL 비율 < 1
  - creep: VEL 7일 연속 증가 + 기울기 양수
  - drift: ENV 배율 > ACC 배율 + 장기 지속

모델: RandomForestClassifier (n_estimators=200, random_state=42)

저장: backend/data/model_registry/fault_classifier.pkl
```

### 명령 2-C: RUL 모델 학습

```
backend/train/train_rul_model.py를 구현하고 실행해줘.

목적: 이상 발생까지 남은 일수(RUL) 예측

레이블 생성:
- 증강 데이터의 STATUS=0 시작일로부터 역산
- 각 날짜의 RUL = (이상 시작일 - 현재 날짜).days
- RUL이 30일 초과인 데이터는 학습에서 제외 (임박 구간만 학습)

피처: VEL 7일 이동평균, VEL 증가율, ACC 대비 VEL 비율

모델: GradientBoostingRegressor (n_estimators=200, random_state=42)

저장: backend/data/model_registry/rul_model.pkl
```

---

## Phase 3 — 백엔드 API

### 명령 3-A: PM API 구현

```
backend/pm_api/main.py와 predictor.py를 구현해줘.

FastAPI 앱, 포트 8000.

엔드포인트:
GET  /health
     → {"status": "ok", "model_loaded": bool, "threshold": float}

POST /predict/from-db
     Body: {"equip_cd": str (optional), "date": str (optional)}
     → 전체 또는 특정 설비의 예측 결과
     → ExtraTrees + 선형 11종 결과 포함
     → 503 반환 시 에이전트가 CSV 도구로 자동 전환

GET  /raw-data?equip_cd=MTR-21A01-CNV01&days=14
     → 최근 N일 센서 시계열

GET  /models/definitions
     → TM_MST_MODEL_DEFINE + TB_AI_MDL_RSLT_SMMRY(USE_YN=Y) 정보

predictor.py:
- extra_trees.pkl + scaler.pkl 로드
- predict(equip_cd, features) → PREDICT_VALUE + 상태 판정
- CLAUDE.md의 상태 판정 기준 (>0.9 정상, 0.7~0.9 주의, 0.5~0.7 경고, <0.5 위험) 사용
```

### 명령 3-B: 에이전트 도구 구현

```
backend/agent/tools/ 아래 3개 파일을 구현해줘.

=== api_tools.py (5종) ===
@tool check_health()
@tool get_equipment_status(start_date: str)
  → 503 시 "PM_API_UNAVAILABLE" 반환 (에이전트가 CSV 도구로 전환)
@tool get_raw_sensor_data(equip_cd: str, days: int = 14)
@tool predict_single_equip(equip_cd: str, date: str = "")
@tool get_model_definitions()

=== data_tools.py (6종) ===
@tool summarize_equipment_status()
  → TB_SNSR_AUGMENTED.csv 최신 날짜 기준 설비별 센서값 + 전체 평균 대비 Δ%

@tool find_missing_features(month: str)
  → 해당 월의 날짜×설비×태그 완전성 검사

@tool compare_model_metrics()
  → TB_AI_MDL_RSLT_SMMRY USE_YN=Y vs 전체 성능 비교

@tool get_feature_contribution(equip_cd: str)
  → TB_AI_MDL_PARAM 계수 × 최신 센서값 = 피처별 기여도
  → 주의: HuberRegressor, LinearSVR은 반드시 개별 계산 (평균화 금지)

@tool analyze_trend(window_days: int = 7)
  → 최근 N일 vs 직전 N일 변화율, ±15% 이상 표시, ±30% 이상 경보

@tool classify_fault_type(equip_cd: str, window_days: int = 7)
  → fault_classifier.pkl 사용하여 Spike/Creep/Drift 분류
  → 분류 근거(주요 피처) 포함하여 반환

=== report_tools.py (2종) ===
@tool estimate_rul(equip_cd: str)
  → rul_model.pkl 사용
  → VEL 현재 추세 외삽으로 UCL 도달 예상일 계산
  → {"rul_days": int, "confidence": float, "basis": str} 반환

@tool make_work_order_draft(
    equip_cd: str, status: str, fault_type: str,
    predict_value: float, abnormal_tags: str,
    estimated_rul: int, meas_dt: str, model_name: str
  )
  → SPEC.md 시나리오 7의 작업지시서 형식으로 마크다운 생성
  → fault_type, estimated_rul 필드 반드시 포함

모든 도구는 반환 타입 str (JSON 직렬화).
CSV 캐시는 mtime 기반 자동 무효화 (_csv_cache dict 사용).
```

### 명령 3-C: LangGraph 그래프 + 시스템 프롬프트

```
backend/agent/graph.py와 prompts/system_prompt.py를 구현해줘.

graph.py:
- StateGraph(MessagesState) 사용
- 노드: agent, tools
- MemorySaver checkpointer
- recursion_limit=20
- 도구 13종 전체 바인딩

system_prompt.py:
아래 내용을 SystemMessage로 작성해줘.

---
당신은 LN21 라인 설비 예지보전 전문 AI 에이전트입니다.
오늘 날짜: {today}

## 담당 설비 (6대)
MTR-21A01-CNV01, MTR-21A09-CNV01, MTR-21A12-CNV01
MTR-22B01-CNV01, MTR-22B09-CNV01, MTR-22B12-CNV01

## 상태 판정 기준
PREDICT_VALUE > 0.9 → 정상
0.7 ~ 0.9          → 주의 (ACC UCL 1σ=10.116 이상)
0.5 ~ 0.7          → 경고 (ACC UCL 2σ=14.792 이상)
< 0.5              → 위험 (ACC UCL 3σ=19.469 이상)

## 이상 유형 3종
Spike: VEL 배율 > ACC 배율, 당일 급등 → 기계적 충격/이물질
Creep: VEL 7일 점진 상승, 선행 7일 경고 구간 존재 → 베어링 마모
Drift: ENV 배율 > ACC 배율, 장기 미복구 → 구조적 이완/열변형

## 도구 선택 원칙
전체 현황 조회     → get_equipment_status → (PM_API_UNAVAILABLE 시) summarize_equipment_status
이상 징후·추세     → analyze_trend
특정 설비 분석     → predict_single_equip + get_raw_sensor_data + get_feature_contribution
이상 유형 분류     → classify_fault_type
RUL 예측          → get_raw_sensor_data + estimate_rul
모델 성능 점검     → get_model_definitions + compare_model_metrics
데이터 품질 확인   → summarize_equipment_status + find_missing_features
작업 지시서 생성   → (분석 완료 후) make_work_order_draft
운영 장애 진단     → check_health → get_model_definitions

## 핵심 주의사항
- HuberRegressor, LinearSVR 계수는 절대 다른 선형 모델과 평균하지 말 것
- STATUS 태그는 예측 피처가 아닌 타겟임을 항상 인식
- MTR-22B09의 정상 ACC 평균(0.421)은 타 설비(3~10)와 매우 달라 개별 기준 적용
---
```

### 명령 3-D: SSE 스트리밍 엔드포인트

```
backend/agent/main.py를 구현해줘.

FastAPI 앱, 포트 8001.

엔드포인트:

POST /chat/stream
  Body: {"message": str, "thread_id": str (optional)}

  SSE 이벤트 순서:
  1. {"type": "thread_id", "content": thread_id}
  2. 도구 호출 시: {"type": "tool_call", "content": "[도구 호출] {tool_name}"}
  3. 도구 완료 시: {"type": "tool_result", "content": "[도구 결과] {preview}"}
  4. classify_fault_type 결과: {"type": "fault_card", "content": {fault_type, confidence, evidence}}
  5. estimate_rul 결과:        {"type": "rul_card", "content": {rul_days, confidence, basis}}
  6. LLM 토큰: {"type": "answer", "content": chunk}
  7. {"type": "done"}

GET /health
DELETE /chat/threads/{thread_id}

lifespan에서:
- 모든 pkl 파일 사전 로드 (Predictor.get_instance())
- graph = build_graph() 실행
- LangSmith 콜백 초기화
```

---

## Phase 4 — 프론트엔드

### 명령 4-0: UI 레퍼런스 주입 (Phase 4 시작 전 반드시 먼저 실행)

```
ui-preview/pm-agent-ui.html 파일을 읽어줘.
이 파일이 앞으로 만들 모든 Vue 컴포넌트의 유일한 디자인 기준이야.

확인 후 아래 내용을 그대로 지켜줘:

1. CSS 변수 — :root 의 모든 변수를 App.vue <style> 에 그대로 복사
   (--bg, --surface, --surface-2, --border, --brand, --success, --warning, --danger,
    --spike, --spike-soft, --creep, --creep-soft, --drift, --drift-soft 등 전부)

2. 클래스명 — HTML의 클래스명을 Vue scoped style에서 동일하게 사용
   임의로 바꾸지 말 것

3. 컴포넌트 매핑:
   .sidebar 전체          → SidebarPanel.vue
   .chat-panel 전체       → ChatPanel.vue
   .tool-step             → ToolStepCard.vue
   .result-card (fault)   → FaultTypeCard.vue
   .result-card (rul)     → RULCard.vue

4. 사이드바 레이아웃 비율 — HTML 그대로 유지
   sidebar-kpi, equip-section → flex-shrink: 0 (고정)
   scenario-section           → flex: 1 (나머지 공간 전부)
   monitor-section            → flex-shrink: 0 (고정)

5. SSE 이벤트 타입별 처리:
   fault_card → FaultTypeCard에 result prop 전달
   rul_card   → RULCard에 result prop 전달
   answer     → marked.parse()로 마크다운 렌더링 (스트리밍 누적)

내용 확인했으면 "UI 레퍼런스 확인 완료"라고만 말해줘. 코드는 아직 짜지 마.
```

---

### 명령 4-A: App.vue

```
ui-preview/pm-agent-ui.html을 기준으로 frontend/src/App.vue를 구현해줘.

- HTML의 :root CSS 변수 전체를 <style>의 :root에 복사
- .app, .topbar, .main 레이아웃 구조 동일하게 구현
- 탑바: 브랜드 아이콘+이름+서브텍스트 / 우측 네비게이션+상태점+아바타
- main: grid-template-columns: 260px 1fr, height: 100%
- SidebarPanel.vue, ChatPanel.vue 임포트 및 배치
- onMounted에서 dashboard 스토어 startPolling() 호출
```

---

### 명령 4-B: Pinia 스토어 2개

```
frontend/src/stores/chat.js와 dashboard.js를 구현해줘.

=== chat.js ===
state:
- threadId: generateId() 초기값 (crypto.randomUUID 12자)
- messages: []
  각 메시지 구조: { id, role, content, answer, steps, faultResult, rulResult, isLoading, time }
- isStreaming: false
- toolCallCount: 0
- abortController: null
- inputText: ''

actions:
- submitMessage(text)
  · addUserMessage → addAgentMessage → SSE fetch → handleSSEEvent 루프
  · finally: setStreaming(false), updateStats()

- handleSSEEvent(msgId, event)
  · tool_call  → steps 배열에 push, toolCallCount++
  · tool_result → steps 배열에 push
  · fault_card → 해당 message의 faultResult 에 저장
  · rul_card   → 해당 message의 rulResult 에 저장
  · answer     → 해당 message의 answer 에 누적 (스트리밍)
  · error      → answer에 오류 메시지
  · done       → 루프 종료

- stopStreaming(): abortController.abort()
- resetChat(): threadId 재생성, messages/toolCallCount 초기화
- fillInputText(text): inputText = text

=== dashboard.js ===
state:
- kpi: { total: 6, normal: 3, caution: 2, danger: 1 }  ← 초기 목업값
- faultDistribution: { spike: 3, creep: 2, drift: 1 }  ← 초기 목업값
- apiStatus: 'checking'
- lastUpdated: null

actions:
- fetchKPI(): GET {API_BASE}/predict/batch
  → 성공 시 kpi, faultDistribution, apiStatus='ok' 갱신
  → 실패 시 apiStatus='error' (기존 목업값 유지)
- startPolling(intervalMs = 30000): fetchKPI() 즉시 실행 후 interval 등록
```

---

### 명령 4-C: SidebarPanel.vue

```
ui-preview/pm-agent-ui.html의 <aside class="sidebar"> 구조를 기준으로
frontend/src/components/SidebarPanel.vue를 구현해줘.

HTML 구조를 그대로 Vue 템플릿으로 변환:

섹션 1 — .sidebar-kpi
  - KPI 4개 (.kpi-card.total/.ok/.warn/.crit) → dashboard 스토어 kpi 바인딩
  - 이상 유형 분포 (.fault-row × 3) → faultDistribution 바인딩
    각 .fault-bar-fill의 width는 max건수 기준 백분율로 계산

섹션 2 — .equip-section
  - 설비 6대 (.equip-row) → EQUIPMENTS 배열 v-for
  - 클릭 시 chat 스토어 fillInputText('{설비ID} 현재 상태 분석해줘') 호출

섹션 3 — .scenario-section
  - 시나리오 8개 (.scenario-btn) → SCENARIOS 배열 v-for
  - 클릭 시 chat 스토어 fillInputText(s.query) 호출
  - id가 4 또는 8인 버튼에만 <span class="s-tag new">신규</span> 표시

섹션 4 — .monitor-section
  - apiStatus → badge-ok / badge-err 동적 클래스
  - threadId → chat 스토어 바인딩

SCENARIOS, EQUIPMENTS, HINTS 배열은 HTML 파일의 JS 데이터 그대로 사용.
```

---

### 명령 4-D: ChatPanel.vue

```
ui-preview/pm-agent-ui.html의 <div class="chat-panel"> 구조를 기준으로
frontend/src/components/ChatPanel.vue를 구현해줘.

HTML 구조를 그대로 Vue 템플릿으로 변환:

.chat-header
  - 에이전트 아바타 + 이름 + 설명 텍스트
  - 초기화 버튼: chat 스토어 resetChat()
  - 중단 버튼: chat 스토어 stopStreaming(), isStreaming일 때만 .visible

.stat-bar
  - threadId, userMsgCount, toolCallCount → chat 스토어 바인딩

.messages (ref="messagesEl")
  - messages.length === 0 → 빈 상태 (.empty-state) 표시
  - messages v-for:
    role === 'user'  → .msg-row.user + .bubble-user
    role === 'agent' → .msg-row.agent + 아래 구조:
      1. .tool-steps → steps v-for → <ToolStepCard :type :content />
      2. .cards-area → faultResult 있으면 <FaultTypeCard :result />
                     → rulResult 있으면 <RULCard :result />
      3. .answer-block
           isLoading && !answer → .typing 표시
           answer 있으면 → .md-body v-html="renderMarkdown(answer)"

.input-area
  - textarea v-model="inputText" (chat 스토어)
  - Enter 전송 (Shift+Enter 줄바꿈)
  - 전송 버튼: submitMessage()
  - 힌트 칩 4개 → fillInputText()

메시지 추가 시마다 scrollToBottom() (nextTick + scrollTop = scrollHeight).
marked.parse(text, { breaks: true }) 로 마크다운 렌더링.
```

---

### 명령 4-E: ToolStepCard.vue

```
ui-preview/pm-agent-ui.html의 .tool-step 구조를 기준으로
frontend/src/components/ToolStepCard.vue를 구현해줘.

props: { type: String ('call' | 'result'), content: String }

- .step-icon의 클래스: type === 'call' ? 'call' : 'result' 동적 바인딩
- .step-head 클릭 시 isOpen ref 토글
- .step-body: v-show="isOpen"
- .step-toggle: :class="{ open: isOpen }"
- label 표시: content에서 "[도구 호출] " "[도구 결과] " 앞부분 제거 후 120자 자르기
- .step-body pre: content 전체 표시 (esc 처리)

HTML의 SVG 아이콘도 그대로 사용 (call: 시계, result: 체크)
```

---

### 명령 4-F: FaultTypeCard.vue

```
ui-preview/pm-agent-ui.html의 FaultTypeCard 구조를 기준으로
frontend/src/components/FaultTypeCard.vue를 구현해줘.

props: {
  result: {
    fault_type: String,        // 'Spike' | 'Creep' | 'Drift'
    confidence: Number,        // 0.0 ~ 1.0
    evidence: Array,           // 근거 문자열 배열
    recommended_action: String
  }
}

computed:
- faultClass: fault_type.toLowerCase() → 'spike' | 'creep' | 'drift'
- confPercent: Math.round(confidence * 100)
- icons: { spike: '⚡', creep: '📈', drift: '🌊' }
- labels: { spike: '급격형', creep: '점진형', drift: '누적형' }
- actions: {
    spike: '즉시 가동 중단 및 이물질·충격 원인 현장 점검',
    creep: '베어링 윤활 상태 확인 및 정밀 진단 예약',
    drift: '구조 이완·열변형 여부 확인, 정밀 측정 실시'
  }

HTML 클래스 동적 바인딩:
- .fault-card-head: :class="faultClass"
- .fault-type-badge: :class="faultClass"
- .conf-fill: :style="{ width: confPercent+'%', background: 'var(--'+faultClass+')' }"
- .fault-action: :class="faultClass"

evidence v-for로 .ev-item 렌더링 (최대 3개).
```

---

### 명령 4-G: RULCard.vue

```
ui-preview/pm-agent-ui.html의 RULCard 구조를 기준으로
frontend/src/components/RULCard.vue를 구현해줘.

props: {
  result: {
    rul_days: Number,
    recommended_maintenance_date: String,
    confidence: Number,
    basis: String,
    historical_reference: String  // optional
  }
}

computed:
- urgencyClass: rul_days <= 3 ? 'danger' : rul_days <= 7 ? 'warn' : 'safe'
- gaugeColor: urgencyClass === 'danger' ? 'var(--danger)' : urgencyClass === 'warn' ? 'var(--warning)' : 'var(--success)'
- gaugePct: Math.max(4, Math.min(100, (rul_days / 30) * 100))
- confPercent: Math.round(confidence * 100)
- maintDate: recommended_maintenance_date 있으면 그대로,
             없으면 오늘 + (rul_days - 2)일 계산 → M/D 형식

HTML 클래스 동적 바인딩:
- .rul-number: :class="urgencyClass"
- .rul-gauge-fill: :style="{ width: gaugePct+'%', background: gaugeColor }"
- 권고 정비일 .rul-dv: :class="urgencyClass"

historical_reference → v-if로 해당 .rul-detail-row 조건부 표시.
```

---

## Phase 5 — 통합 테스트

### 명령 5-A: 전체 서비스 실행 및 확인

```
docker-compose up --build -d 로 전체 서비스를 실행해줘.

30초 대기 후 아래 순서로 확인해줘:

1. 서비스 헬스체크
   curl http://localhost:8000/health   ← pm-api
   curl http://localhost:8001/health   ← agent-api

2. 프론트엔드 접속 확인
   curl -s -o /dev/null -w "%{http_code}" http://localhost:5173
   → 200이면 정상

3. SSE 스트리밍 8개 시나리오 순서대로 테스트
   (각 테스트 후 tool_call / answer / done 이벤트 포함 여부 확인)

   시나리오 1: "오늘 LN21 라인 설비 상태 요약해줘"
   시나리오 2: "최근 7일 설비별 센서 변화 추세 분석해줘"
   시나리오 3: "MTR-21A01-CNV01 왜 경고야? 원인 분석해줘"
   시나리오 4: "MTR-21A01-CNV01 이상이 베어링 문제야, 과부하야?"
              → fault_card 이벤트 반드시 확인
   시나리오 5: "현재 쓰는 예측 모델이 뭐고 성능은 어때?"
   시나리오 6: "최근 데이터에 누락된 센서 있어?"
   시나리오 7: "경고 설비 작업 지시서 초안 만들어줘"
   시나리오 8: "MTR-22B12 언제 교체해야 해? 앞으로 얼마나 버텨?"
              → rul_card 이벤트 반드시 확인

   테스트 명령:
   curl -N -X POST http://localhost:8001/chat/stream \
     -H "Content-Type: application/json" \
     -d '{"message": "질문내용", "thread_id": "test-001"}'

4. 실패한 항목이 있으면 원인 분석 후 즉시 수정해줘.
```

### 명령 5-B: 골든 데이터셋 평가

```
backend/evaluate/golden_test.py를 구현하고 실행해줘.

각 테스트 케이스 구조:
{
  "id": "scenario_01",
  "question": "오늘 LN21 라인 설비 상태 요약해줘",
  "expected_tools": ["get_equipment_status"],
  "expected_contains": ["LN21", "정상", "주의", "경고"],
  "expected_sse_events": ["tool_call", "tool_result", "answer", "done"],
  "expected_cards": []              ← fault_card / rul_card 필요 여부
}

시나리오 4는 expected_cards: ["fault_card"],
시나리오 8은 expected_cards: ["rul_card"] 로 설정.

평가 지표:
- 도구 선택 정확도 (expected_tools 일치율)
- 답변 키워드 통과율 (expected_contains)
- SSE 이벤트 완전성
- 카드 이벤트 발생 여부

결과를 마크다운 테이블로 출력:
| 시나리오 | 도구 정확도 | 키워드 통과 | 이벤트 완전성 | 카드 발생 | 종합 |
```

---

## 트러블슈팅 가이드

문제 발생 시 Claude Code에 줄 명령:

```
# 모델 로드 오류
backend/data/model_registry/ 폴더의 pkl 파일 목록을 확인하고
누락된 파일이 있으면 해당 Phase 2 명령을 다시 실행해줘.

# SSE 스트리밍이 끊기는 경우
agent/main.py의 event_generator() 각 yield 뒤에
await asyncio.sleep(0) 추가해줘.

# FaultTypeCard 또는 RULCard가 렌더링 안 될 때
ChatPanel.vue에서 fault_card / rul_card SSE 이벤트 수신 후
해당 message 객체의 faultResult / rulResult 가 반응형으로 업데이트되는지 확인.
message 객체를 reactive() 또는 ref()로 감싸야 Vue가 변경을 감지함.

# 도구가 잘못 선택되는 경우
system_prompt.py의 "도구 선택 원칙" 섹션을 확인하고
해당 시나리오 질문 문구를 더 구체적으로 수정해줘.

# 증강 데이터 STATUS=0 비율이 목표(25~30%)보다 낮은 경우
augment/run_augment.py에서 이상 에피소드 빈도를 높이거나
generate_drift_fault() 호출 횟수를 늘려줘.

# 사이드바 시나리오 영역이 너무 좁은 경우
SidebarPanel.vue의 .scenario-section이 flex: 1 인지 확인.
.sidebar-kpi, .equip-section, .monitor-section은 flex-shrink: 0 이어야 함.
```
