"""골든 데이터셋 기반 에이전트 평가 스크립트.

8개 대표 시나리오에 대해 /chat/stream SSE 응답을 수집하고
도구 선택 정확도 / 키워드 통과율 / 이벤트 완전성 / 카드 발생 여부를 평가한다.
"""
import json
import os

import httpx

AGENT_API_BASE = os.environ.get("AGENT_API_BASE", "http://localhost:8001")

TEST_CASES = [
    {
        "id": "scenario_01",
        "question": "오늘 LN21 라인 설비 상태 요약해줘",
        "expected_tools": ["get_equipment_status"],
        "expected_contains": ["LN21", "정상", "주의", "경고"],
        "expected_sse_events": ["tool_call", "tool_result", "answer", "done"],
        "expected_cards": [],
    },
    {
        "id": "scenario_02",
        "question": "최근 7일 설비별 센서 변화 추세 분석해줘",
        "expected_tools": ["analyze_trend"],
        "expected_contains": ["VEL", "ACC", "변화율"],
        "expected_sse_events": ["tool_call", "tool_result", "answer", "done"],
        "expected_cards": [],
    },
    {
        "id": "scenario_03",
        "question": "MTR-21A01-CNV01 왜 경고야? 원인 분석해줘",
        "expected_tools": ["predict_single_equip", "get_raw_sensor_data", "classify_fault_type"],
        "expected_contains": ["MTR-21A01-CNV01", "원인", "이상 유형"],
        "expected_sse_events": ["tool_call", "tool_result", "answer", "done"],
        "expected_cards": [],
    },
    {
        "id": "scenario_04",
        "question": "MTR-21A01-CNV01 이상이 베어링 문제야, 과부하야?",
        "expected_tools": ["predict_single_equip", "get_raw_sensor_data", "classify_fault_type"],
        "expected_contains": ["이상 유형", "신뢰도", "권장 조치"],
        "expected_sse_events": ["tool_call", "tool_result", "answer", "done"],
        "expected_cards": ["fault_card"],
    },
    {
        "id": "scenario_05",
        "question": "현재 쓰는 예측 모델이 뭐고 성능은 어때?",
        "expected_tools": ["get_model_definitions"],
        "expected_contains": ["ExtraTrees", "R²", "RMSE"],
        "expected_sse_events": ["tool_call", "tool_result", "answer", "done"],
        "expected_cards": [],
    },
    {
        "id": "scenario_06",
        "question": "최근 데이터에 누락된 센서 있어?",
        "expected_tools": ["find_missing_features"],
        "expected_contains": ["누락", "ACC", "ENV", "VEL"],
        "expected_sse_events": ["tool_call", "tool_result", "answer", "done"],
        "expected_cards": [],
    },
    {
        "id": "scenario_07",
        "question": "경고 설비 작업 지시서 초안 만들어줘",
        "expected_tools": ["get_equipment_status", "classify_fault_type", "estimate_rul", "make_work_order_draft"],
        "expected_contains": ["작업 지시서", "조치"],
        "expected_sse_events": ["tool_call", "tool_result", "answer", "done"],
        "expected_cards": [],
    },
    {
        "id": "scenario_08",
        "question": "MTR-22B12 언제 교체해야 해? 앞으로 얼마나 버텨?",
        "expected_tools": ["estimate_rul"],
        "expected_contains": ["RUL", "잔여", "교체"],
        "expected_sse_events": ["tool_call", "tool_result", "answer", "done"],
        "expected_cards": ["rul_card"],
    },
]


def run_scenario(case: dict) -> dict:
    payload = {"message": case["question"], "thread_id": f"golden-{case['id']}"}
    tool_calls = []
    tool_results = []
    event_types = set()
    cards = []
    answer_text = ""

    with httpx.stream(
        "POST", f"{AGENT_API_BASE}/chat/stream", json=payload, timeout=180
    ) as resp:
        for line in resp.iter_lines():
            line = line.strip()
            if not line.startswith("data: "):
                continue
            event = json.loads(line[len("data: "):])
            etype = event["type"]
            event_types.add(etype)
            if etype == "tool_call":
                tool_calls.append(event["content"].replace("[도구 호출]", "").strip())
            elif etype == "tool_result":
                tool_results.append(event["content"].replace("[도구 결과]", "").strip())
            elif etype == "answer":
                answer_text += event["content"]
            elif etype in ("fault_card", "rul_card"):
                cards.append(etype)

    return {
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "event_types": event_types,
        "cards": cards,
        "answer": answer_text,
    }


def evaluate(case: dict, result: dict) -> dict:
    expected_tools = set(case["expected_tools"])
    actual_tools = set(result["tool_calls"])
    tool_acc = (
        len(expected_tools & actual_tools) / len(expected_tools)
        if expected_tools else 1.0
    )

    expected_kw = case["expected_contains"]
    kw_hits = sum(1 for kw in expected_kw if kw in result["answer"])
    kw_pass = kw_hits / len(expected_kw) if expected_kw else 1.0

    expected_events = set(case["expected_sse_events"])
    event_completeness = (
        len(expected_events & result["event_types"]) / len(expected_events)
        if expected_events else 1.0
    )

    expected_cards = set(case["expected_cards"])
    actual_cards = set(result["cards"])
    card_pass = (
        len(expected_cards & actual_cards) / len(expected_cards)
        if expected_cards else 1.0
    )

    overall = (tool_acc + kw_pass + event_completeness + card_pass) / 4

    return {
        "tool_acc": tool_acc,
        "kw_pass": kw_pass,
        "event_completeness": event_completeness,
        "card_pass": card_pass,
        "overall": overall,
    }


def main() -> None:
    rows = []
    for case in TEST_CASES:
        print(f"실행 중: {case['id']} - {case['question']}")
        result = run_scenario(case)
        scores = evaluate(case, result)
        rows.append((case["id"], scores))

    print()
    print("| 시나리오 | 도구 정확도 | 키워드 통과 | 이벤트 완전성 | 카드 발생 | 종합 |")
    print("|---|---|---|---|---|---|")
    for sid, s in rows:
        print(
            f"| {sid} | {s['tool_acc']:.0%} | {s['kw_pass']:.0%} | "
            f"{s['event_completeness']:.0%} | {s['card_pass']:.0%} | {s['overall']:.0%} |"
        )


if __name__ == "__main__":
    main()