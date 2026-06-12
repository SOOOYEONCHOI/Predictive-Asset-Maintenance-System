"""deepeval 기반 의미적 평가 (golden_test.py의 규칙 기반 평가를 보강).

8개 시나리오에 대해 LLM-judge 메트릭으로
- 도구 호출 정확성 (ToolCorrectnessMetric)
- 답변 관련성 (AnswerRelevancyMetric)
- 도구 결과 충실성 (FaithfulnessMetric)
- 도메인 정확성 (커스텀 GEval)
을 평가한다.
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from golden_test import TEST_CASES, run_scenario  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from deepeval.metrics import (  # noqa: E402
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    GEval,
    ToolCorrectnessMetric,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams, ToolCall  # noqa: E402

JUDGE_MODEL = "gpt-4o-mini"
MAX_CHARS = 600


def truncate(text: str) -> str:
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS] + " ...(생략)"

domain_metric = GEval(
    name="DomainCorrectness",
    criteria=(
        "설비 예지보전 도메인 관점에서 답변을 평가하라. "
        "도구 실행 결과(Retrieval Context)에 등장하는 설비 코드, 수치, 상태, "
        "이상 유형, 잔여수명 등 핵심 정보를 답변이 정확히 반영하고 있는지, "
        "임의로 지어낸 수치나 결론이 없는지를 중점적으로 확인하라."
    ),
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.RETRIEVAL_CONTEXT,
    ],
    model=JUDGE_MODEL,
    threshold=0.5,
)


def build_test_case(case: dict, result: dict) -> LLMTestCase:
    return LLMTestCase(
        input=case["question"],
        actual_output=truncate(result["answer"]),
        tools_called=[ToolCall(name=t) for t in result["tool_calls"]],
        expected_tools=[ToolCall(name=t) for t in case["expected_tools"]],
        retrieval_context=[truncate(t) for t in result["tool_results"]] or [""],
    )


def main() -> None:
    tool_metric = ToolCorrectnessMetric(threshold=0.5)
    relevancy_metric = AnswerRelevancyMetric(threshold=0.5, model=JUDGE_MODEL)
    faithfulness_metric = FaithfulnessMetric(threshold=0.5, model=JUDGE_MODEL)

    rows = []
    for case in TEST_CASES:
        print(f"평가 중: {case['id']} - {case['question']}")
        result = run_scenario(case)
        tc = build_test_case(case, result)

        tool_metric.measure(tc)
        relevancy_metric.measure(tc)
        faithfulness_metric.measure(tc)
        domain_metric.measure(tc)

        rows.append((
            case["id"],
            tool_metric.score,
            relevancy_metric.score,
            faithfulness_metric.score,
            domain_metric.score,
        ))

    print()
    print("| 시나리오 | Tool Correctness | Answer Relevancy | Faithfulness | Domain Correctness |")
    print("|---|---|---|---|---|")
    for sid, t, r, f, d in rows:
        print(f"| {sid} | {t:.2f} | {r:.2f} | {f:.2f} | {d:.2f} |")


if __name__ == "__main__":
    main()