from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class KPIBlock(BaseModel):
    label: str
    value: float | int
    delta: float | None = None


class TrendPoint(BaseModel):
    date: datetime
    value: float


class DepartmentInsight(BaseModel):
    department: str
    avg_risk_score: float
    click_rate: float
    report_rate: float
    improvement_score: float


class BehaviorSignal(BaseModel):
    label: str
    value: int


class DepartmentBehaviorReport(BaseModel):
    department_id: str
    department: str
    employee_count: int
    avg_risk_score: float
    click_rate: float
    report_rate: float
    opened_email_rate: float
    training_completion_count: int
    risky_interactions: int
    report_events: int
    last_activity_at: datetime | None = None
    behavior_trend: list[TrendPoint]
    risk_trend: list[TrendPoint]
    top_behavior_signals: list[BehaviorSignal]


class RiskIntelligenceOverview(BaseModel):
    monitored_employees: int
    high_risk_employees: int
    average_risk_score: float
    improving_employees: int
    departments_flagged: int


class AdaptiveRecommendation(BaseModel):
    employee_id: str
    employee_name: str
    employee_email: str
    department: str | None = None
    current_risk_score: int
    weak_channel: str
    weak_triggers: list[str]
    recommended_theme: str
    recommended_channel: str
    recommended_difficulty: str
    estimated_fall_likelihood: float
    priority_score: float
    confidence: float
    risk_band: str
    recommended_action: str
    learning_objective: str
    retest_window_days: int
    reason_breakdown: dict[str, float | int]
    rationale: str
    evidence: list[str]


class RiskIntelligenceResponse(BaseModel):
    overview: RiskIntelligenceOverview
    department_reports: list[DepartmentBehaviorReport]
    adaptive_recommendations: list[AdaptiveRecommendation]


class DashboardResponse(BaseModel):
    kpis: list[KPIBlock]
    risk_distribution: list[dict[str, Any]]
    channel_performance: list[dict[str, Any]]
    vulnerable_departments: list[DepartmentInsight]
    trend: list[TrendPoint]
