from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import Campaign, Department, DeliveryAttempt, Employee, EventLog, RiskScore, Scenario, TrainingCompletion
from app.models.enums import PROTECTIVE_EVENT_TYPES, RISKY_EVENT_TYPES, Channel, EventType
from app.schemas.analytics import (
    AdaptiveRecommendation,
    BehaviorSignal,
    DashboardResponse,
    DepartmentBehaviorReport,
    DepartmentInsight,
    KPIBlock,
    RiskIntelligenceOverview,
    RiskIntelligenceResponse,
    TrendPoint,
)
from app.services.events import FAILURE_REASON_BY_TRIGGER
from app.services.scoring import department_risk_rows


def build_dashboard(db: Session, organization_id) -> DashboardResponse:
    total_campaigns = db.query(Campaign).filter(Campaign.organization_id == organization_id).count()
    total_events = db.query(EventLog).filter(EventLog.organization_id == organization_id).count()
    delivered = db.query(EventLog).filter(EventLog.organization_id == organization_id, EventLog.event_type == EventType.DELIVERED).count()
    clicked = db.query(EventLog).filter(EventLog.organization_id == organization_id, EventLog.event_type == EventType.CLICKED_LINK).count()
    reported = db.query(EventLog).filter(EventLog.organization_id == organization_id, EventLog.event_type == EventType.CLICKED_REPORT).count()
    kpis = [
        KPIBlock(label="Total Campaigns", value=total_campaigns),
        KPIBlock(label="Delivery Success", value=round((delivered / total_events * 100), 1) if total_events else 0),
        KPIBlock(label="Click Rate", value=round((clicked / delivered * 100), 1) if delivered else 0),
        KPIBlock(label="Report Rate", value=round((reported / delivered * 100), 1) if delivered else 0),
    ]

    employees = db.query(Employee).filter(Employee.organization_id == organization_id).all()
    risk_distribution = [
        {"band": "0-25", "count": sum(1 for employee in employees if employee.risk_score <= 25)},
        {"band": "26-50", "count": sum(1 for employee in employees if 26 <= employee.risk_score <= 50)},
        {"band": "51-75", "count": sum(1 for employee in employees if 51 <= employee.risk_score <= 75)},
        {"band": "76-100", "count": sum(1 for employee in employees if employee.risk_score >= 76)},
    ]

    channel_counter = Counter()
    for row in db.query(EventLog.channel, EventLog.event_type, func.count(EventLog.id)).filter(EventLog.organization_id == organization_id).group_by(EventLog.channel, EventLog.event_type):
        channel_counter[(row[0].value if row[0] else "unknown", row[1].value)] = row[2]

    # Each channel fails and succeeds in its own vocabulary: a click on email, a scan on
    # QR, a disclosure on a call, trusting a fake on deepfake. Roll them up so the chart
    # compares like with like across all five.
    #
    # Rates are computed over distinct *people*, not events. An interactive voice or
    # deepfake simulation records several decisions per target, so an event-over-delivery
    # ratio would exceed 100% and make the channels incomparable.
    risky_people: dict[str, set] = defaultdict(set)
    protective_people: dict[str, set] = defaultdict(set)
    reached_people: dict[str, set] = defaultdict(set)
    for event in db.query(EventLog).filter(EventLog.organization_id == organization_id).all():
        if not event.employee_id:
            continue
        channel_key = event.channel.value if event.channel else "unknown"
        if event.event_type == EventType.DELIVERED:
            reached_people[channel_key].add(event.employee_id)
        elif event.event_type in RISKY_EVENT_TYPES:
            risky_people[channel_key].add(event.employee_id)
        elif event.event_type in PROTECTIVE_EVENT_TYPES and event.event_type != EventType.TRAINING_COMPLETED:
            protective_people[channel_key].add(event.employee_id)

    channel_performance = []
    for channel in [channel_enum.value for channel_enum in Channel]:
        delivered_count = channel_counter.get((channel, "delivered"), 0)
        risky = sum(
            channel_counter.get((channel, event_type.value), 0) for event_type in RISKY_EVENT_TYPES
        )
        protective = sum(
            channel_counter.get((channel, event_type.value), 0)
            for event_type in PROTECTIVE_EVENT_TYPES
            if event_type != EventType.TRAINING_COMPLETED
        )
        reached = len(reached_people.get(channel, set())) or delivered_count
        failed_people = risky_people.get(channel, set())
        # Someone who both complied and resisted counts as a failure, not resilience.
        resisted_people = protective_people.get(channel, set()) - failed_people
        channel_performance.append(
            {
                "channel": channel,
                "delivered": delivered_count,
                "clicks": risky,
                "risky_actions": risky,
                "reports": protective,
                "protective_actions": protective,
                "failure_rate": round(len(failed_people) / reached * 100, 1) if reached else 0.0,
                "resilience_rate": round(len(resisted_people) / reached * 100, 1) if reached else 0.0,
            }
        )

    dept_rows = department_risk_rows(db, organization_id)
    vulnerable_departments = [
        DepartmentInsight(
            department=name,
            avg_risk_score=avg,
            click_rate=0,
            report_rate=0,
            improvement_score=max(0.0, 100.0 - avg),
        )
        for name, avg in dept_rows
    ]
    vulnerable_departments.sort(key=lambda row: row.avg_risk_score, reverse=True)

    trend = []
    now = datetime.now(timezone.utc)
    for day_offset in range(6, -1, -1):
        day = now - timedelta(days=day_offset)
        count = (
            db.query(EventLog)
            .filter(
                EventLog.organization_id == organization_id,
                EventLog.occurred_at >= day.replace(hour=0, minute=0, second=0, microsecond=0),
                EventLog.occurred_at < day.replace(hour=23, minute=59, second=59, microsecond=999999),
            )
            .count()
        )
        trend.append(TrendPoint(date=day, value=float(count)))

    return DashboardResponse(
        kpis=kpis,
        risk_distribution=risk_distribution,
        channel_performance=channel_performance,
        vulnerable_departments=vulnerable_departments[:5],
        trend=trend,
    )


def build_risk_intelligence(db: Session, organization_id) -> RiskIntelligenceResponse:
    employees = db.query(Employee).filter(Employee.organization_id == organization_id).all()
    departments = db.query(Department).filter(Department.organization_id == organization_id).all()
    events = db.query(EventLog).filter(EventLog.organization_id == organization_id).all()
    adaptive_recommendations = build_adaptive_recommendations(db, organization_id, employees, events)
    risk_scores = db.query(RiskScore).filter(RiskScore.organization_id == organization_id).all()
    completions = (
        db.query(TrainingCompletion)
        .join(Employee, TrainingCompletion.employee_id == Employee.id)
        .filter(Employee.organization_id == organization_id)
        .all()
    )

    employee_map = {str(employee.id): employee for employee in employees}
    employees_by_department: dict[str, list[Employee]] = defaultdict(list)
    for employee in employees:
        if employee.department_id:
            employees_by_department[str(employee.department_id)].append(employee)

    events_by_department: dict[str, list[EventLog]] = defaultdict(list)
    for event in events:
        if not event.employee_id:
            continue
        employee = employee_map.get(str(event.employee_id))
        if employee and employee.department_id:
            events_by_department[str(employee.department_id)].append(event)

    scores_by_department: dict[str, list[RiskScore]] = defaultdict(list)
    scores_by_employee: dict[str, list[RiskScore]] = defaultdict(list)
    for score in risk_scores:
        if score.department_id:
            scores_by_department[str(score.department_id)].append(score)
        if score.employee_id:
            scores_by_employee[str(score.employee_id)].append(score)

    completions_by_department: dict[str, list[TrainingCompletion]] = defaultdict(list)
    for completion in completions:
        employee = employee_map.get(str(completion.employee_id))
        if employee and employee.department_id:
            completions_by_department[str(employee.department_id)].append(completion)

    improving_employees = 0
    for employee in employees:
        history = sorted(scores_by_employee.get(str(employee.id), []), key=lambda item: item.calculated_at)
        if len(history) >= 2 and history[-1].score < history[0].score:
            improving_employees += 1

    department_reports: list[DepartmentBehaviorReport] = []
    now = datetime.now(timezone.utc)

    for department in departments:
        department_id = str(department.id)
        department_employees = employees_by_department.get(department_id, [])
        department_events = events_by_department.get(department_id, [])
        department_scores = scores_by_department.get(department_id, [])
        department_completions = completions_by_department.get(department_id, [])

        delivered = sum(1 for event in department_events if event.event_type == EventType.DELIVERED)
        opened = sum(1 for event in department_events if event.event_type == EventType.OPENED_EMAIL)
        clicked = sum(1 for event in department_events if event.event_type == EventType.CLICKED_LINK)
        submitted = sum(1 for event in department_events if event.event_type == EventType.SUBMITTED_FORM_BOOLEAN)
        reported = sum(1 for event in department_events if event.event_type in PROTECTIVE_EVENT_TYPES and event.event_type != EventType.TRAINING_COMPLETED)
        scanned = sum(1 for event in department_events if event.event_type == EventType.SCANNED_QR)
        risky_interactions = sum(1 for event in department_events if event.event_type in RISKY_EVENT_TYPES)

        event_counter = Counter(
            event.event_type.value
            for event in department_events
            if event.event_type not in {EventType.DELIVERED, EventType.BOUNCED}
        )
        top_behavior_signals = [
            BehaviorSignal(label=label, value=value)
            for label, value in event_counter.most_common(4)
        ]

        behavior_trend: list[TrendPoint] = []
        risk_trend: list[TrendPoint] = []
        for day_offset in range(6, -1, -1):
            day = now - timedelta(days=day_offset)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
            behavior_count = sum(
                1
                for event in department_events
                if day_start
                <= (event.occurred_at.astimezone(timezone.utc) if event.occurred_at.tzinfo else event.occurred_at.replace(tzinfo=timezone.utc))
                <= day_end
                and event.event_type not in {EventType.DELIVERED, EventType.BOUNCED}
            )
            behavior_trend.append(TrendPoint(date=day, value=float(behavior_count)))

            day_scores = [
                score.score
                for score in department_scores
                if day_start
                <= (score.calculated_at.astimezone(timezone.utc) if score.calculated_at.tzinfo else score.calculated_at.replace(tzinfo=timezone.utc))
                <= day_end
            ]
            fallback_avg = sum(employee.risk_score for employee in department_employees) / len(department_employees) if department_employees else 0.0
            risk_trend.append(TrendPoint(date=day, value=float(sum(day_scores) / len(day_scores)) if day_scores else float(fallback_avg)))

        avg_risk_score = sum(employee.risk_score for employee in department_employees) / len(department_employees) if department_employees else 0.0
        last_activity_at = max((event.occurred_at for event in department_events), default=None)

        department_reports.append(
            DepartmentBehaviorReport(
                department_id=department_id,
                department=department.name,
                employee_count=len(department_employees),
                avg_risk_score=avg_risk_score,
                click_rate=round((clicked / delivered * 100), 1) if delivered else 0.0,
                report_rate=round((reported / delivered * 100), 1) if delivered else 0.0,
                opened_email_rate=round((opened / delivered * 100), 1) if delivered else 0.0,
                training_completion_count=len(department_completions),
                risky_interactions=risky_interactions,
                report_events=reported,
                last_activity_at=last_activity_at,
                behavior_trend=behavior_trend,
                risk_trend=risk_trend,
                top_behavior_signals=top_behavior_signals,
            )
        )

    department_reports.sort(key=lambda report: report.avg_risk_score, reverse=True)
    average_risk_score = sum(employee.risk_score for employee in employees) / len(employees) if employees else 0.0

    return RiskIntelligenceResponse(
        overview=RiskIntelligenceOverview(
            monitored_employees=len(employees),
            high_risk_employees=sum(1 for employee in employees if employee.risk_score >= 60),
            average_risk_score=round(average_risk_score, 1),
            improving_employees=improving_employees,
            departments_flagged=sum(1 for report in department_reports if report.avg_risk_score >= 40),
        ),
        department_reports=department_reports,
        adaptive_recommendations=adaptive_recommendations,
    )


def build_adaptive_recommendations(db: Session, organization_id, employees: list[Employee], events: list[EventLog]) -> list[AdaptiveRecommendation]:
    risky_events = RISKY_EVENT_TYPES
    positive_events = PROTECTIVE_EVENT_TYPES

    delivery_ids = [event.delivery_attempt_id for event in events if event.delivery_attempt_id]
    attempts = (
        db.query(DeliveryAttempt)
        .filter(DeliveryAttempt.id.in_(delivery_ids))
        .all()
        if delivery_ids
        else []
    )
    attempt_map = {attempt.id: attempt for attempt in attempts}

    scenario_ids = [attempt.scenario_id for attempt in attempts if attempt.scenario_id]
    scenarios = db.query(Scenario).filter(Scenario.id.in_(scenario_ids)).all() if scenario_ids else []
    scenario_map = {scenario.id: scenario for scenario in scenarios}

    events_by_employee: dict[str, list[EventLog]] = defaultdict(list)
    for event in events:
        if event.employee_id:
            events_by_employee[str(event.employee_id)].append(event)

    recommendations: list[AdaptiveRecommendation] = []
    for employee in employees:
        employee_events = events_by_employee.get(str(employee.id), [])
        risky = [event for event in employee_events if event.event_type in risky_events]
        positives = [event for event in employee_events if event.event_type in positive_events]
        event_counter = Counter(event.event_type for event in employee_events)

        channel_counter: Counter[str] = Counter()
        trigger_counter: Counter[str] = Counter()
        evidence: list[str] = []

        for event in risky:
            channel_counter[event.channel.value if event.channel else "email"] += _channel_signal_weight(event.event_type)
            attempt = attempt_map.get(event.delivery_attempt_id)
            scenario = scenario_map.get(attempt.scenario_id) if attempt and attempt.scenario_id else None
            triggers = scenario.detected_persuasion_triggers if scenario else []
            for trigger in triggers:
                trigger_counter[FAILURE_REASON_BY_TRIGGER.get(trigger, trigger)] += 1
            evidence.append(f"{_event_label(event.event_type)} on {event.channel.value if event.channel else 'unknown'}")

        weak_channel = channel_counter.most_common(1)[0][0] if channel_counter else _fallback_channel(employee)
        weak_triggers = [trigger for trigger, _ in trigger_counter.most_common(3)] or _fallback_triggers(employee, weak_channel)
        recommended_theme = _theme_for_weakness(employee, weak_channel, weak_triggers)
        recommended_channel = weak_channel
        recommended_difficulty = _difficulty_for_employee(employee, len(risky), len(positives))
        likelihood = _estimate_fall_likelihood(employee.risk_score, len(risky), len(positives), trigger_counter)
        priority_score = _priority_score(employee, employee_events, event_counter, trigger_counter)
        confidence = _confidence_score(employee, employee_events, trigger_counter)
        risk_band = _risk_band(employee.risk_score)
        recommended_action = _recommended_action(len(risky), len(positives), event_counter, priority_score, recommended_channel)
        learning_objective = _learning_objective(weak_triggers, recommended_theme)
        retest_window_days = _retest_window_days(priority_score, recommended_difficulty)
        reason_breakdown = {
            "current_risk_score": employee.risk_score,
            "risky_actions": len(risky),
            "positive_actions": len(positives),
            "dominant_weakness_count": max(trigger_counter.values(), default=0),
            "recent_activity": _recent_activity_count(employee_events),
        }

        if not evidence:
            evidence = [
                "No risky interactions yet; using role, department, and current risk score as the cold-start signal.",
            ]

        recommendations.append(
            AdaptiveRecommendation(
                employee_id=str(employee.id),
                employee_name=employee.full_name,
                employee_email=employee.email,
                department=employee.department.name if employee.department else None,
                current_risk_score=employee.risk_score,
                weak_channel=weak_channel,
                weak_triggers=weak_triggers,
                recommended_theme=recommended_theme,
                recommended_channel=recommended_channel,
                recommended_difficulty=recommended_difficulty,
                estimated_fall_likelihood=likelihood,
                priority_score=priority_score,
                confidence=confidence,
                risk_band=risk_band,
                recommended_action=recommended_action,
                learning_objective=learning_objective,
                retest_window_days=retest_window_days,
                reason_breakdown=reason_breakdown,
                rationale=_recommendation_rationale(weak_channel, weak_triggers, recommended_theme, len(risky), len(positives)),
                evidence=evidence[:5],
            )
        )

    recommendations.sort(key=lambda item: (item.priority_score, item.estimated_fall_likelihood, item.current_risk_score), reverse=True)
    return recommendations[:8]


def _channel_signal_weight(event_type: EventType) -> int:
    if event_type in {EventType.TRUSTED_SYNTHETIC_MEDIA, EventType.DISCLOSED_ON_CALL}:
        return 5
    if event_type == EventType.SUBMITTED_FORM_BOOLEAN:
        return 4
    if event_type in {EventType.CLICKED_LINK, EventType.SCANNED_QR, EventType.REPLIED_SMS}:
        return 3
    return 1


def _event_label(event_type: EventType) -> str:
    labels = {
        EventType.CLICKED_LINK: "Clicked simulation link",
        EventType.SCANNED_QR: "Scanned simulation QR",
        EventType.SUBMITTED_FORM_BOOLEAN: "Entered simulated verification flow",
        EventType.REPLIED_SMS: "Replied to simulation SMS",
        EventType.VISITED_LANDING_PAGE: "Visited landing page",
        EventType.CLICKED_REPORT: "Reported suspicious message",
        EventType.TRAINING_COMPLETED: "Completed training",
        EventType.ANSWERED_CALL: "Engaged with simulated caller",
        EventType.DISCLOSED_ON_CALL: "Disclosed on an unverified call",
        EventType.VERIFIED_CALLER: "Challenged caller identity",
        EventType.ENDED_CALL_SAFELY: "Ended unverified call",
        EventType.PLAYED_SYNTHETIC_MEDIA: "Played synthetic media",
        EventType.TRUSTED_SYNTHETIC_MEDIA: "Acted on synthetic media",
        EventType.FLAGGED_SYNTHETIC_MEDIA: "Flagged synthetic media",
        EventType.VERIFIED_OUT_OF_BAND: "Verified out of band",
    }
    return labels.get(event_type, event_type.value.replace("_", " ").title())


def _fallback_channel(employee: Employee) -> str:
    preferences = employee.training_preferences or []
    if "qr" in preferences:
        return Channel.QR.value
    if "sms" in preferences:
        return Channel.SMS.value
    return Channel.EMAIL.value


def _fallback_triggers(employee: Employee, channel: str) -> list[str]:
    if channel == Channel.QR.value:
        return ["qr_lure", "habit_autopilot"]
    if channel == Channel.SMS.value:
        return ["sms_trust", "urgency"]
    if channel == Channel.VISHING.value:
        return ["voice_pressure", "authority"]
    if channel == Channel.DEEPFAKE.value:
        return ["synthetic_likeness", "authority"]
    role_text = f"{employee.role_title} {employee.approved_context_summary or ''}".lower()
    if "finance" in role_text or "invoice" in role_text or "payment" in role_text:
        return ["authority", "role_relevance"]
    if "it" in role_text or "password" in role_text:
        return ["urgency", "habit_autopilot"]
    return ["curiosity", "role_relevance"]


def _theme_for_weakness(employee: Employee, channel: str, triggers: list[str]) -> str:
    trigger_set = set(triggers)
    role_text = f"{employee.role_title} {employee.approved_context_summary or ''}".lower()
    if channel == Channel.QR.value or "qr_lure" in trigger_set:
        return "qr verification"
    if channel == Channel.SMS.value or "sms_trust" in trigger_set:
        return "policy update"
    if channel == Channel.DEEPFAKE.value or "synthetic_likeness" in trigger_set:
        return "executive approval request"
    if channel == Channel.VISHING.value or "voice_pressure" in trigger_set:
        return "vendor payment release"
    if "authority" in trigger_set or "role_relevance" in trigger_set:
        if "finance" in role_text or "invoice" in role_text or "payment" in role_text:
            return "invoice/payment approval"
        return "document review"
    if "urgency" in trigger_set or "habit_autopilot" in trigger_set:
        return "password reset"
    if "curiosity" in trigger_set:
        return "client contract"
    return "document review"


def _difficulty_for_employee(employee: Employee, risky_count: int, positive_count: int) -> str:
    if employee.risk_score >= 60 or risky_count >= 3:
        return "high"
    if employee.risk_score >= 25 or risky_count >= 1 or positive_count == 0:
        return "medium"
    return "low"


def _estimate_fall_likelihood(risk_score: int, risky_count: int, positive_count: int, trigger_counter: Counter[str]) -> float:
    repeated_trigger_boost = max(trigger_counter.values(), default=0) * 6
    estimate = 30 + (risk_score * 0.45) + (risky_count * 8) + repeated_trigger_boost - (positive_count * 7)
    return round(max(5, min(95, estimate)), 1)


def _priority_score(employee: Employee, events: list[EventLog], event_counter: Counter[EventType], trigger_counter: Counter[str]) -> float:
    click_weight = event_counter.get(EventType.CLICKED_LINK, 0) * 8
    qr_weight = event_counter.get(EventType.SCANNED_QR, 0) * 7
    verification_weight = event_counter.get(EventType.SUBMITTED_FORM_BOOLEAN, 0) * 10
    report_credit = event_counter.get(EventType.CLICKED_REPORT, 0) * 8
    training_credit = event_counter.get(EventType.TRAINING_COMPLETED, 0) * 6
    report_gap = 12 if event_counter.get(EventType.DELIVERED, 0) and not event_counter.get(EventType.CLICKED_REPORT, 0) else 0
    repeated_trigger_boost = max(trigger_counter.values(), default=0) * 5
    recent_boost = min(_recent_activity_count(events) * 4, 12)

    score = (
        employee.risk_score * 0.45
        + click_weight
        + qr_weight
        + verification_weight
        + report_gap
        + repeated_trigger_boost
        + recent_boost
        - report_credit
        - training_credit
    )
    return round(max(0, min(100, score)), 1)


def _confidence_score(employee: Employee, events: list[EventLog], trigger_counter: Counter[str]) -> float:
    signal_strength = min(len(events), 12) * 4
    trigger_strength = 12 if trigger_counter else 0
    profile_strength = 8 if employee.department_id else 0
    context_strength = 8 if employee.approved_context_summary else 0
    confidence = 35 + signal_strength + trigger_strength + profile_strength + context_strength
    return round(max(30, min(95, confidence)), 1)


def _recent_activity_count(events: list[EventLog]) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    count = 0
    for event in events:
        occurred_at = event.occurred_at.astimezone(timezone.utc) if event.occurred_at.tzinfo else event.occurred_at.replace(tzinfo=timezone.utc)
        if occurred_at >= cutoff and event.event_type not in {EventType.DELIVERED, EventType.BOUNCED}:
            count += 1
    return count


def _risk_band(score: int) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "elevated"
    return "baseline"


def _recommended_action(risky_count: int, positive_count: int, event_counter: Counter[EventType], priority_score: float, channel: str) -> str:
    if risky_count == 0 and positive_count == 0:
        return "Run a baseline simulation and collect first-party behavior signals."
    if event_counter.get(EventType.CLICKED_REPORT, 0) and positive_count >= risky_count:
        return "Validate retention with a lower-pressure scenario and keep normal cadence."
    if channel == Channel.QR.value:
        return "Assign QR micro-training, then retest with a different QR placement."
    if channel == Channel.SMS.value:
        return "Retest mobile trust behavior with an adjacent SMS workflow."
    if channel == Channel.DEEPFAKE.value:
        return "Assign synthetic-media training, then retest with a different persona and modality."
    if channel == Channel.VISHING.value:
        return "Drill the hang-up-and-call-back procedure, then retest with a new pretext."
    if priority_score >= 70:
        return "Schedule targeted micro-training and a short-window retest."
    return "Run a role-relevant retest and compare reporting response."


def _learning_objective(triggers: list[str], theme: str) -> str:
    trigger_set = set(triggers)
    if "qr_lure" in trigger_set:
        return "Verify QR source, destination, and placement before scanning."
    if "sms_trust" in trigger_set:
        return "Confirm mobile alerts through a known company channel before acting."
    if "synthetic_likeness" in trigger_set:
        return "Treat a familiar voice or face as a claim, and verify it on a channel you chose."
    if "voice_pressure" in trigger_set:
        return "End unverified calls and call back on a number from the internal directory."
    if "urgency" in trigger_set:
        return "Slow down urgent workflow requests and verify through the official system."
    if "authority" in trigger_set:
        return "Validate sender authority instead of trusting title, tone, or department language."
    if "role_relevance" in trigger_set:
        return f"Challenge role-relevant {theme} requests when they arrive outside the expected workflow."
    if "curiosity" in trigger_set:
        return "Treat unexpected document or reward prompts as verification-required."
    return f"Practice safe response behavior for {theme} requests."


def _retest_window_days(priority_score: float, difficulty: str) -> int:
    if priority_score >= 75 or difficulty == "high":
        return 7
    if priority_score >= 50 or difficulty == "medium":
        return 14
    return 30


def _recommendation_rationale(channel: str, triggers: list[str], theme: str, risky_count: int, positive_count: int) -> str:
    trigger_text = ", ".join(trigger.replace("_", " ") for trigger in triggers)
    if risky_count:
        return (
            f"Employee previously showed weakness on {channel} interactions with {trigger_text} cues. "
            f"Next simulation should retest {theme} at a controlled difficulty."
        )
    if positive_count:
        return (
            f"Employee has positive reporting/training behavior. Use a lower-pressure {theme} scenario to validate retention."
        )
    return (
        f"Cold-start recommendation based on role context. Start with {theme} over {channel}, then adapt after first interaction."
    )
