export const EQUIPMENTS = [
  { id: 'MTR-21A01-CNV01', val: 0.83, status: 'crit', badge: '경고' },
  { id: 'MTR-21A09-CNV01', val: 0.74, status: 'warn', badge: '주의' },
  { id: 'MTR-21A12-CNV01', val: 0.95, status: 'ok', badge: '정상' },
  { id: 'MTR-22B01-CNV01', val: 0.92, status: 'ok', badge: '정상' },
  { id: 'MTR-22B09-CNV01', val: 0.78, status: 'warn', badge: '주의' },
  { id: 'MTR-22B12-CNV01', val: 0.96, status: 'ok', badge: '정상' },
]

export const SCENARIOS = [
  { id: 1, label: '전체 설비 현황 조회', tag: null, query: '오늘 LN21 라인 설비 상태 요약해줘' },
  { id: 2, label: '이상 징후 추세 분석', tag: null, query: '최근 7일 설비별 센서 변화 추세 분석해줘. 이상 징후 있는 설비 먼저 알려줘.' },
  { id: 3, label: '특정 설비 경고 원인 분석', tag: null, query: 'MTR-21A01-CNV01 왜 경고야? 원인 분석해줘' },
  { id: 4, label: '이상 유형 자동 분류', tag: '신규', query: 'MTR-21A01-CNV01 이상이 베어링 문제야, 과부하야? 어떤 타입이야?' },
  { id: 5, label: '모델 성능 점검', tag: null, query: '현재 쓰는 예측 모델이 뭐고 성능은 어때?' },
  { id: 6, label: '데이터 품질 확인', tag: null, query: '최근 데이터에 누락된 센서 있어? 데이터 이상한 거 없어?' },
  { id: 7, label: '작업 지시서 초안 생성', tag: null, query: '경고 설비 작업 지시서 초안 만들어줘' },
  { id: 8, label: '잔여 수명(RUL) 예측', tag: '신규', query: 'MTR-22B12 언제 교체해야 해? 앞으로 얼마나 버텨?' },
]

export const HINTS = [
  '전체 설비 현황 요약해줘',
  'MTR-21A01 왜 경고야?',
  'MTR-21A01 이상 유형 분류해줘',
  'MTR-22B12 잔여 수명 예측해줘',
  '경고 설비 작업 지시서 초안',
  '최근 센서 추세 분석해줘',
]