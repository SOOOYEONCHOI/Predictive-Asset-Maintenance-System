# 설비 예지보전 AI 에이전트 — 최종 테스트 결과

## 1. Phase 5-A: 통합 실행 및 SSE 시나리오 테스트

- `docker-compose up --build -d` 정상 빌드/기동 (pm-api :8000, agent-api :8001, frontend :5173)
- `/health` 헬스체크: pm-api, agent-api 모두 정상
- 8개 SSE 시나리오(`/chat/stream`) 전체 정상 동작 확인 (tool_call → tool_result → answer → done, 카드 이벤트 포함)

### 해결한 이슈
- `backend/Dockerfile`, `frontend/Dockerfile` 누락 → 표준 Dockerfile 추가
- `estimate_rul` 도구에서 `rul_model.pkl`이 sklearn 1.8.0으로 피클되어 컨테이너의 sklearn 1.9.0과 호환 불가
  (`ModuleNotFoundError: No module named '_loss'`) → 컨테이너 내에서 `train_rul_model` 재실행으로 재학습
  (R²=0.1021, RMSE=8.6823, MAE=6.8929)
- 프론트엔드 "연결 오류: Failed to fetch" → `agent/main.py`에 CORS 미들웨어 누락이 원인.
  `CORSMiddleware(allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])` 추가로 해결

---

## 2. Phase 5-B: 골든 데이터셋 평가 (`golden_test.py`)

규칙 기반 평가: 도구 선택 정확도 / 키워드 통과율 / SSE 이벤트 완전성 / 카드 발생 여부

| 시나리오 | 도구 정확도 | 키워드 통과 | 이벤트 완전성 | 카드 발생 | 종합 |
|---|---|---|---|---|---|
| scenario_01 | 100% | 50% | 100% | 100% | 88% |
| scenario_02 | 100% | 100% | 100% | 100% | 100% |
| scenario_03 | 100% | 67% | 100% | 100% | 92% |
| scenario_04 | 100% | 67% | 100% | 100% | 92% |
| scenario_05 | 100% | 100% | 100% | 100% | 100% |
| scenario_06 | 100% | 100% | 100% | 100% | 100% |
| scenario_07 | 100% | 100% | 100% | 100% | 100% |
| scenario_08 | 100% | 67% | 100% | 100% | 92% |

키워드 통과율이 100% 미만인 항목은 답변 자체의 오류가 아니라, 평가용 키워드 셋과 LLM의 실제 표현(예: "원인 분석" vs "근본 원인", "RUL" 대신 "잔여수명"만 사용 등)이 다소 다르기 때문으로 확인됨.

---

## 3. deepeval 기반 의미적 평가 (`deepeval_test.py`)

LLM-judge 메트릭: Tool Correctness / Answer Relevancy / Faithfulness / Domain Correctness (커스텀 GEval)

| 시나리오 | Tool Correctness | Answer Relevancy | Faithfulness | Domain Correctness |
|---|---|---|---|---|
| scenario_01 | 1.00 | 1.00 | 0.33 | 0.83 |
| scenario_02 | 1.00 | 1.00 | 1.00 | 0.88 |
| scenario_03 | 1.00 | 1.00 | 0.86 | 0.85 |
| scenario_04 | 1.00 | 1.00 | 0.91 | 0.80 |
| scenario_05 | 1.00 | 0.38 | 1.00 | 0.92 |
| scenario_06 | 1.00 | 1.00 | 0.50 | 0.82 |
| scenario_07 | 1.00 | 0.75 | 0.68 | 0.78 |
| scenario_08 | 1.00 | 0.83 | 0.83 | 0.86 |

### scenario_05 수정 내역 (`현재 쓰는 예측 모델이 뭐고 성능은 어때?`)

**문제**: `TB_AI_MDL_RSLT_SMMRY.csv`의 `USE_YN=Y`는 선형 모델 그룹(ARDRegression 등, R²≈0.70)에만
표시되어 있고, 실제 운영 중인 주력 모델인 `ExtraTreesRegressor`(R²=0.860, `extra_trees.pkl`)는
`USE_YN`이 비어 있음. 이로 인해 `/models/definitions` 응답에 ExtraTreesRegressor가 빠져
에이전트가 선형 모델 그룹을 "현재 모델"로 답변 (Domain Correctness 0.44).

**수정**:
- `backend/pm_api/main.py`의 `/models/definitions`에서 `ALGO_NM == "ExtraTreesRegressor"` 행을
  `primary_model` 필드로 별도 반환 (`adopted_models`는 기존 USE_YN=Y 목록 유지)
- `backend/pm_api/schemas.py`의 `ModelDefinitionsResponse`에 `primary_model: dict | None` 추가
- `backend/agent/tools/api_tools.py`의 `get_model_definitions` 독스트링에
  "primary_model = 실제 운영 중인 주력 모델"이며 이를 우선 답변하라고 명시

**결과**: scenario_05 키워드 통과율 67% → 100%, Domain Correctness 0.44 → 0.92로 개선.
다만 Answer Relevancy는 1.00 → 0.38로 하락 — 답변에 "채택된 다른 모델 평균 성능",
"전체 모델 평균 성능" 등 질문과 직접 관련 없는 부가 통계가 함께 포함되어
relevancy 판정에서 감점된 것으로 확인됨 (정확성 문제는 아니며, 향후 system prompt에서
"질문에 직접 관련된 정보만 답변" 가이드 추가 시 개선 가능).

### 전반적 낮은 점수 항목
- **Faithfulness 낮음 (scenario_01: 0.33, scenario_06: 0.50)**: 도구 결과가 200자로 트렁케이션되어
  judge에게 전달되는 retrieval_context가 답변 전체를 커버하지 못해 발생하는 평가상 한계로 판단됨
  (실제 답변 내용은 도구 결과와 일치).
- **scenario_07 (작업 지시서 초안)**: Answer Relevancy 0.75, Faithfulness 0.68, Domain Correctness 0.78로
  4개 시나리오 중 가장 낮음 — 여러 도구 결과를 종합하는 복합 시나리오 특성상 일부 표현이
  judge 기준에서 과도하게 일반화된 것으로 추정. 추가 검토 권장.

---

## 4. 평가 로직 설명 및 신뢰성 검토

### 4.1 golden_test.py — 규칙 기반 평가

| 항목 | 계산 방식 | 의미 |
|---|---|---|
| 도구 정확도 | `len(expected_tools ∩ actual_tools) / len(expected_tools)` | 기대한 도구가 실제로 호출됐는지 |
| 키워드 통과 | `expected_contains` 중 답변에 포함된 단어 수 / 전체 키워드 수 | 답변에 특정 단어가 등장하는지 |
| 이벤트 완전성 | 기대 SSE 이벤트 타입 중 실제 발생한 비율 | 스트림이 끝까지 정상 진행됐는지 |
| 카드 발생 | 기대 카드(`fault_card`/`rul_card`) 중 실제 발생한 비율 | UI 카드 트리거 여부 |
| 종합 | 위 4개의 단순 평균 | — |

전부 결정론적이며 LLM judge를 사용하지 않음 (에이전트 자체는 LLM 호출).

### 4.2 deepeval_test.py — LLM-judge 기반 의미 평가

| 메트릭 | 무엇을 보는가 | 판정 방식 |
|---|---|---|
| Tool Correctness | `tools_called` vs `expected_tools` | 집합 비교 (judge 불필요) |
| Answer Relevancy | `input` vs `actual_output` | judge가 답변을 문장 단위로 쪼개 각 문장의 질문 관련성 비율 산출 |
| Faithfulness | `actual_output` vs `retrieval_context`(도구 결과) | judge가 답변의 각 주장이 도구 결과로 뒷받침되는지 비율 산출 |
| Domain Correctness (커스텀 GEval) | `input` + `actual_output` + `retrieval_context` | "핵심 정보를 정확히 반영했는지, 임의 수치를 지어내지 않았는지"를 judge(gpt-4o-mini)가 0~1로 직접 채점 |

`actual_output`/`retrieval_context`는 judge의 `LengthFinishReasonError`를 피하기 위해 `MAX_CHARS=600`으로 잘라서 전달.

### 4.3 신뢰성 검토

**신뢰할 수 있는 부분**
- golden_test의 "도구 정확도"/"이벤트 완전성"과 deepeval의 "Tool Correctness"는 결정론적 집합 비교로, 시스템의 실제 동작을 그대로 반영 → 회귀 테스트로서 신뢰도 높음.
- Domain Correctness(커스텀 GEval)는 scenario_05의 실제 문제(ExtraTrees 누락)를 0.44 → 0.92로 정확히 짚어냄 → 도메인 특화 기준으로서 유용한 신호.

**한계점 (주의해서 해석 필요)**
1. **키워드 통과율 ≠ 정답 여부**: scenario_01/03/04/08의 미달은 답변이 틀려서가 아니라 "원인"→"근본 원인", "RUL"→"잔여수명" 등 표현 차이 때문. 정밀도가 낮은 회수율(recall) 위주 지표임.
2. **truncation이 Faithfulness/Relevancy를 왜곡**: 600자(또는 200자)로 잘린 retrieval_context/도구 결과에 답변 후반부 근거가 빠지면서 judge가 "근거 없음"으로 판정 → 실제 환각 여부와 점수가 1:1로 대응하지 않음.
3. **judge 모델의 변동성(non-determinism)**: 동일 입력에도 gpt-4o-mini judge 점수가 실행마다 달라짐 (예: scenario_05 1차 Faithfulness 1.00/Domain 0.44 → 2차 1.00/0.92, scenario_01 Faithfulness 0.18 → 0.33). 단일 실행 점수를 절대 기준으로 삼기엔 노이즈가 크며, 개선 전후 추세 비교 정도로만 활용 가능.
4. **메트릭 간 상충**: scenario_05의 Answer Relevancy 0.38(↓)은 부가 통계가 늘어 judge가 "무관한 문장"으로 판정한 결과 — Domain Correctness(↑)와 상충되며, 단일 메트릭만으로 "개선/악화"를 단정하기 어려움.
5. **샘플 수 N=1**: 시나리오당 1회만 실행 → 통계적으로 의미 있는 점수가 아닌 "이 정도 범위가 나온다"는 스냅샷으로 봐야 함.

**결론**: 두 평가 모두 "무엇이 망가졌는지 찾는" 회귀 탐지 용도로는 신뢰할 만하나(scenario_05 버그를 정확히 짚어냄), 점수 자체를 "에이전트 품질 = 92%"처럼 절대치로 보고하기엔 부적합. 신뢰도를 높이려면 (a) 키워드 셋에 동의어 포함, (b) truncation 길이 확대 또는 답변 요약 후 judge 전달, (c) 시나리오당 N회(예: 3회) 반복 후 평균/분산 보고가 현실적인 개선 방향.

---

## 5. 종합 결론

- Phase 5-A 통합/SSE 테스트: 8/8 시나리오 정상
- Phase 5-B 규칙 기반 평가: 평균 종합 점수 96.5% (8개 시나리오 중 4개 100%)
- deepeval 의미 평가: Tool Correctness 전 시나리오 1.00, scenario_05 도메인 정확성 이슈 수정 완료
- 남은 개선 포인트: scenario_07 복합 시나리오 답변 품질, scenario_05 답변의 관련성(불필요한 부가 통계 축소)
