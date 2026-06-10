from agent.tools.api_tools import (
    check_health,
    get_equipment_status,
    get_model_definitions,
    get_raw_sensor_data,
    predict_single_equip,
)
from agent.tools.data_tools import (
    analyze_trend,
    classify_fault_type,
    compare_model_metrics,
    find_missing_features,
    get_feature_contribution,
    summarize_equipment_status,
)
from agent.tools.report_tools import estimate_rul, make_work_order_draft

ALL_TOOLS = [
    check_health,
    get_equipment_status,
    get_raw_sensor_data,
    predict_single_equip,
    get_model_definitions,
    summarize_equipment_status,
    find_missing_features,
    compare_model_metrics,
    get_feature_contribution,
    analyze_trend,
    classify_fault_type,
    estimate_rul,
    make_work_order_draft,
]