# Render 배포 가이드

이 저장소는 `render.yaml` Blueprint로 Render에 배포할 수 있습니다.

## 생성되는 서비스

```text
pm-agent-pm-api       FastAPI PM API
pm-agent-agent-api    LangGraph Agent API
pm-agent-frontend     Vue 정적 프론트엔드
```

## 배포 절차

1. Render Dashboard에서 **New +** → **Blueprint**를 선택합니다.
2. GitHub 저장소 `SOOOYEONCHOI/Predictive-Asset-Maintenance-System`를 연결합니다.
3. `render.yaml`을 감지하면 Blueprint 생성을 진행합니다.
4. 생성 중 `OPENAI_API_KEY`, `LANGCHAIN_API_KEY` 값을 입력합니다.
   - `OPENAI_API_KEY`는 필수입니다.
   - `LANGCHAIN_API_KEY`는 LangSmith 추적을 쓸 때만 입력합니다.
5. 배포 완료 후 프론트엔드 URL로 접속합니다.

## Render 설정 방식

백엔드는 Render 빌드 단계에서 증강 데이터와 모델 파일을 생성합니다.

```bash
python -m augment.run_augment
python -m train.train_predictor
python -m train.train_fault_classifier
python -m train.train_rul_model
```

프론트엔드는 빌드 시 다음 환경변수를 사용합니다.

```text
VITE_AGENT_API_BASE=https://pm-agent-agent-api.onrender.com
VITE_PM_API_BASE=https://pm-agent-pm-api.onrender.com
```

만약 Render가 서비스 URL에 suffix를 붙이면, `pm-agent-frontend` 서비스의 환경변수를 실제 URL로 수정한 뒤 재배포해야 합니다.

## 무료 플랜 주의사항

- 무료 Web Service는 사용하지 않으면 sleep 될 수 있습니다.
- 첫 요청은 cold start로 느릴 수 있습니다.
- SQLite 파일은 Render 무료 인스턴스에서 영구 저장소로 보장하지 않습니다.
- 생성 데이터와 모델 파일은 빌드 산출물이므로 재배포 시 다시 생성됩니다.
