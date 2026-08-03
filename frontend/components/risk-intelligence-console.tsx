"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { TrendChart } from "@/components/charts";
import { Panel } from "@/components/panel";
import { StatusBadge } from "@/components/status-badge";
import { useSession } from "@/components/session-provider";
import {
  DepartmentBehaviorReport,
  Employee,
  EmployeeRiskReport,
  getEmployeeReport,
  getEmployees,
  getRiskIntelligence,
  RiskIntelligenceData,
} from "@/lib/client-api";

export function RiskIntelligenceConsole() {
  const { session } = useSession();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [riskIntel, setRiskIntel] = useState<RiskIntelligenceData | null>(null);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string>("");
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<string>("");
  const [employeeReport, setEmployeeReport] = useState<EmployeeRiskReport | null>(null);
  const [employeeLoading, setEmployeeLoading] = useState(false);

  useEffect(() => {
    if (!session) return;
    void loadRiskIntelligence();
  }, [session]);

  useEffect(() => {
    if (!session || !selectedEmployeeId) {
      setEmployeeReport(null);
      return;
    }

    setEmployeeLoading(true);
    void getEmployeeReport(session.access_token, selectedEmployeeId)
      .then(setEmployeeReport)
      .finally(() => setEmployeeLoading(false));
  }, [session, selectedEmployeeId]);

  async function loadRiskIntelligence() {
    if (!session) return;
    const [employeeRows, intelligence] = await Promise.all([
      getEmployees(session.access_token),
      getRiskIntelligence(session.access_token),
    ]);

    const sortedEmployees = [...employeeRows].sort((left, right) => right.risk_score - left.risk_score);
    setEmployees(sortedEmployees);
    setRiskIntel(intelligence);
    setSelectedEmployeeId((current) => current || sortedEmployees[0]?.id || "");
    setSelectedDepartmentId((current) => current || intelligence.department_reports[0]?.department_id || "");
  }

  const selectedDepartment = useMemo<DepartmentBehaviorReport | null>(() => {
    if (!riskIntel) return null;
    return (
      riskIntel.department_reports.find((report) => report.department_id === selectedDepartmentId)
      ?? riskIntel.department_reports[0]
      ?? null
    );
  }, [riskIntel, selectedDepartmentId]);

  if (!riskIntel) {
    return <Panel>Loading risk intelligence...</Panel>;
  }

  const noDirectory = employees.length === 0;
  const topRecommendation = riskIntel.adaptive_recommendations?.[0] ?? null;

  return (
    <>
      <section className="app-surface rounded-xl p-5 md:p-6">
        <div className="grid gap-5 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <div className="section-title">Adaptive intelligence</div>
            <h1 className="display-font mt-2 text-2xl font-semibold tracking-[-0.035em] text-ink">Human risk engine</h1>
            <p className="mt-1.5 max-w-2xl text-sm text-slate">Explainable employee risk, department exposure and evidence-based retesting.</p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3 lg:min-w-[620px]">
            <HeroPill label="Priority Employee" value={topRecommendation?.employee_name ?? employees[0]?.full_name ?? "No employees yet"} />
            <HeroPill label="Priority Department" value={selectedDepartment?.department ?? "No departments yet"} />
            <HeroPill label="Next Test" value={topRecommendation ? `${topRecommendation.recommended_channel.toUpperCase()} / ${topRecommendation.recommended_theme}` : "Run first campaign"} />
          </div>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <OverviewCard label="Monitored Employees" value={riskIntel.overview.monitored_employees} tone="ink" detail="Active directory users." />
        <OverviewCard label="High Risk Employees" value={riskIntel.overview.high_risk_employees} tone="ember" detail="Employees in the elevated band." />
        <OverviewCard label="Average Risk Score" value={`${riskIntel.overview.average_risk_score}/100`} tone="tide" detail="Organization-wide average." />
        <OverviewCard label="Improving Employees" value={riskIntel.overview.improving_employees} tone="moss" detail="Scores trending downward." />
        <OverviewCard label="Flagged Departments" value={riskIntel.overview.departments_flagged} tone="ember" detail="Teams with concentrated risk." />
      </div>

      <Panel>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="section-title">Adaptive Risk Engine</div>
            <h2 className="display-font mt-2 text-xl font-semibold tracking-[-0.03em] text-ink">Priority retest queue</h2>
            <p className="mt-1.5 max-w-3xl text-sm leading-6 text-slate">Ranked from campaign behavior, weak triggers, training response and recency.</p>
          </div>
          <Link href="/scenario-lab" className="app-primary-button">
            Create recommended scenario
          </Link>
        </div>

        <div className={(riskIntel.adaptive_recommendations ?? []).length > 1 ? "mt-6 grid gap-4 xl:grid-cols-2" : "mt-6 grid gap-4"}>
          {(riskIntel.adaptive_recommendations ?? []).length ? (
            riskIntel.adaptive_recommendations.slice(0, 4).map((recommendation) => (
              <section key={recommendation.employee_id} className="rounded-xl border border-ink/10 bg-white/85 p-4 md:p-5">
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div>
                    <div className="text-xs uppercase tracking-[0.18em] text-slate">Target Employee</div>
                    <h4 className="mt-2 display-font text-xl font-semibold text-ink">{recommendation.employee_name}</h4>
                    <p className="mt-1 text-sm text-slate">{recommendation.employee_email}</p>
                  </div>
                  <div className="rounded-xl bg-ember/10 px-4 py-3 text-center">
                    <div className="text-xs uppercase tracking-[0.16em] text-ember">Predicted Risk</div>
                    <div className="mt-1 text-2xl font-semibold text-ember">{recommendation.estimated_fall_likelihood}%</div>
                  </div>
                </div>

                <div className="mt-5 grid gap-3 md:grid-cols-3">
                  <AiSignal label="Priority" value={`${recommendation.priority_score}/100`} />
                  <AiSignal label="Confidence" value={`${recommendation.confidence}%`} />
                  <AiSignal label="Risk Band" value={humanizeKey(recommendation.risk_band)} />
                </div>

                <div className="mt-3 grid gap-3 md:grid-cols-4">
                  <AiSignal label="Weak Channel" value={recommendation.weak_channel.toUpperCase()} />
                  <AiSignal label="Next Theme" value={recommendation.recommended_theme} />
                  <AiSignal label="Difficulty" value={recommendation.recommended_difficulty.toUpperCase()} />
                  <AiSignal label="Retest Window" value={`${recommendation.retest_window_days} days`} />
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  {recommendation.weak_triggers.map((trigger) => (
                    <span key={trigger} className="rounded-full bg-tide/10 px-3 py-1 text-xs font-semibold text-tide">
                      {humanizeKey(trigger)}
                    </span>
                  ))}
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <div className="rounded-2xl border border-ink/10 bg-white px-4 py-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-slate">Recommended Action</div>
                    <p className="mt-2 text-sm leading-7 text-ink">{recommendation.recommended_action}</p>
                  </div>
                  <div className="rounded-2xl border border-ink/10 bg-white px-4 py-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-slate">Learning Objective</div>
                    <p className="mt-2 text-sm leading-7 text-ink">{recommendation.learning_objective}</p>
                  </div>
                </div>

                <p className="mt-4 text-sm leading-6 text-slate">{recommendation.rationale}</p>

                <div className="mt-4 rounded-lg bg-sand px-4 py-3 text-sm text-slate">
                  <span className="font-semibold text-ink">Evidence:</span> {recommendation.evidence.join(" / ")}
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  {Object.entries(recommendation.reason_breakdown).map(([reason, value]) => (
                    <span key={reason} className="rounded-full border border-ink/10 bg-white px-3 py-1.5 text-xs font-semibold text-slate">
                      {humanizeKey(reason)}: {value}
                    </span>
                  ))}
                </div>
              </section>
            ))
          ) : (
            <div className="rounded-[1.5rem] border border-ink/10 bg-white/80 p-5 text-sm leading-7 text-slate">
              No AI recommendations yet. Add employees and run at least one campaign; after clicks, QR scans, reports, or training events, the adaptive engine will recommend the next best simulation.
            </div>
          )}
        </div>
      </Panel>

      {noDirectory ? (
        <Panel>
          <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <div>
              <div className="section-title">First Run</div>
              <h3 className="mt-4 text-3xl font-semibold">No employees or departments are preloaded anymore</h3>
              <p className="mt-3 text-sm leading-7 text-slate">
                This instance now starts like a real company workspace. The admin creates departments, adds employees, then launches campaigns. Risk intelligence becomes active after people are added and events start arriving.
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <Link href="/employees" className="rounded-[1.5rem] bg-ink px-4 py-3 text-sm font-semibold text-mist">
                  Open Directory Setup
                </Link>
                <Link href="/scenario-lab" className="rounded-[1.5rem] border border-ink/10 bg-white px-4 py-3 text-sm font-semibold text-ink">
                  Open Scenario Lab
                </Link>
              </div>
            </div>
            <div className="grid gap-4">
              <OnboardingStep step="1" title="Create departments" description="Add the company teams first so employees can be assigned correctly." />
              <OnboardingStep step="2" title="Import or add employees" description="Use the directory page for manual onboarding or CSV import." />
              <OnboardingStep step="3" title="Launch a simulation" description="Once the first employee interacts, this page starts showing risk movement and behavior trends." />
            </div>
          </div>
        </Panel>
      ) : (
        <>
          <Panel>
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div className="section-title">Employee Intelligence</div>
                <h3 className="display-font mt-2 text-xl font-semibold tracking-[-0.03em] text-ink">Employee behavior over time</h3>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <label className="flex min-w-[320px] flex-col gap-2 text-xs uppercase tracking-[0.18em] text-slate">
                  Select Employee
                  <select
                    value={selectedEmployeeId}
                    onChange={(event) => setSelectedEmployeeId(event.target.value)}
                    className="rounded-2xl border border-ink/10 bg-white px-4 py-3 text-sm font-medium text-ink outline-none"
                  >
                    {employees.map((employee) => (
                      <option key={employee.id} value={employee.id}>
                        {employee.full_name} / {employee.email}
                      </option>
                    ))}
                  </select>
                </label>
                <button onClick={() => void loadRiskIntelligence()} className="rounded-2xl border border-ink/10 bg-white px-4 py-3 text-sm font-semibold text-ink">
                  Refresh
                </button>
              </div>
            </div>

            {!employeeReport || employeeLoading ? (
              <div className="mt-6 rounded-[1.5rem] bg-white/70 px-4 py-8 text-sm text-slate">Loading employee report...</div>
            ) : (
              <div className="mt-6 grid gap-4 xl:grid-cols-[320px_1fr]">
                <div className="grid gap-4">
                  <section className="rounded-[1.5rem] border border-ink/10 bg-white/80 p-5">
                    <div className="text-xs uppercase tracking-[0.18em] text-slate">Selected Employee</div>
                    <h4 className="mt-3 text-2xl font-semibold text-ink">{employeeReport.employee.full_name}</h4>
                    <p className="mt-2 text-sm leading-7 text-slate">
                      {employeeReport.employee.email}<br />
                      {employeeReport.employee.department_name ?? "No department"} - {employeeReport.employee.role_title}
                    </p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <StatusBadge value={employeeReport.employee.status} />
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${trendClassName(employeeReport.trend)}`}>
                        {humanizeKey(employeeReport.trend)}
                      </span>
                    </div>
                  </section>

                  <section className="rounded-[1.5rem] border border-ink/10 bg-ink p-5 text-mist">
                    <div className="text-xs uppercase tracking-[0.18em] text-mist/65">Current Score</div>
                    <div className="mt-3 text-5xl font-semibold">{employeeReport.current_risk_score}</div>
                    <p className="mt-3 text-sm leading-7 text-mist/70">
                      This number updates after clicks, reports, QR scans, landing-page visits, and training completions.
                    </p>
                  </section>

                  <section className="rounded-[1.5rem] border border-ink/10 bg-white/80 p-5">
                    <div className="text-xs uppercase tracking-[0.18em] text-slate">Behavior Snapshot</div>
                    <div className="mt-4 grid gap-3">
                      <SummaryRow label="Opened Emails" value={employeeReport.behavior_summary.opened_emails} />
                      <SummaryRow label="Clicked Links" value={employeeReport.behavior_summary.clicked_links} />
                      <SummaryRow label="Reported Messages" value={employeeReport.behavior_summary.reported} />
                      <SummaryRow label="Training Completed" value={employeeReport.behavior_summary.training_completed} />
                      <SummaryRow
                        label="Last Activity"
                        value={employeeReport.behavior_summary.last_event_at ? formatDateTime(employeeReport.behavior_summary.last_event_at) : "No activity yet"}
                      />
                    </div>
                  </section>
                </div>

                <div className="grid gap-4">
                  <div className="grid gap-4 md:grid-cols-4">
                    <SignalCard label="Visits" value={employeeReport.behavior_summary.visited_landing_pages} tone="tide" />
                    <SignalCard label="Clicks" value={employeeReport.behavior_summary.clicked_links} tone="ember" />
                    <SignalCard label="Reports" value={employeeReport.behavior_summary.reported} tone="moss" />
                    <SignalCard label="Training" value={employeeReport.behavior_summary.training_completed} tone="ink" />
                  </div>

                  <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
                    <section className="rounded-[1.5rem] border border-ink/10 bg-white/80 p-5">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-xs uppercase tracking-[0.18em] text-slate">Score Movement</div>
                          <h4 className="mt-2 text-xl font-semibold text-ink">Risk score trend over time</h4>
                        </div>
                      </div>
                      <div className="mt-4">
                        {employeeReport.risk_history.length ? (
                          <TrendChart data={employeeReport.risk_history.map((point) => ({ date: point.date, value: point.score }))} />
                        ) : (
                          <EmptyPlotMessage message="No score history exists yet. Once a simulation event is tracked, the chart begins plotting." />
                        )}
                      </div>
                    </section>

                    <section className="rounded-[1.5rem] border border-ink/10 bg-white/80 p-5">
                      <div className="text-xs uppercase tracking-[0.18em] text-slate">Score Drivers</div>
                      <h4 className="mt-2 text-xl font-semibold text-ink">Latest reasons behind the score</h4>
                      <div className="mt-4 flex flex-wrap gap-2">
                        {Object.entries(employeeReport.latest_breakdown).filter(([, score]) => Number(score) !== 0).length ? (
                          Object.entries(employeeReport.latest_breakdown).filter(([, score]) => Number(score) !== 0).map(([reason, score]) => (
                            <span
                              key={reason}
                              className={`rounded-full px-3 py-2 text-sm font-semibold ${Number(score) > 0 ? "bg-ember/10 text-ember" : "bg-moss/15 text-moss"}`}
                            >
                              {humanizeKey(reason)} {Number(score) > 0 ? `+${score}` : score}
                            </span>
                          ))
                        ) : (
                          <span className="rounded-full bg-sand px-3 py-2 text-sm text-slate">No score changes recorded yet.</span>
                        )}
                      </div>
                      <p className="mt-5 text-sm leading-7 text-slate">
                        Positive behaviors like reporting and completing training reduce risk. High-risk actions like clicking, scanning, or continuing through a suspicious workflow increase it.
                      </p>
                    </section>
                  </div>

                  <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
                    <section className="rounded-[1.5rem] border border-ink/10 bg-white/80 p-5">
                      <div className="text-xs uppercase tracking-[0.18em] text-slate">Timeline</div>
                      <h4 className="mt-2 text-xl font-semibold text-ink">Recent employee behavior</h4>
                      <div className="mt-4 grid gap-3">
                        {employeeReport.events.length ? (
                          employeeReport.events.slice(0, 6).map((event) => (
                            <div key={event.id} className="rounded-2xl border border-ink/10 bg-white px-4 py-3">
                              <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                                <div className="font-semibold text-ink">{humanizeKey(event.event_type)}</div>
                                <div className="text-xs uppercase tracking-[0.18em] text-slate">
                                  {event.channel ? `${event.channel} - ` : ""}
                                  {formatDateTime(event.occurred_at)}
                                </div>
                              </div>
                              <div className="mt-2 text-sm leading-7 text-slate">{formatMetadata(event.metadata)}</div>
                            </div>
                          ))
                        ) : (
                          <EmptyPlotMessage message="No tracked events exist yet for this employee." />
                        )}
                      </div>
                    </section>

                    <section className="rounded-[1.5rem] border border-ink/10 bg-white/80 p-5">
                      <div className="text-xs uppercase tracking-[0.18em] text-slate">Training Response</div>
                      <h4 className="mt-2 text-xl font-semibold text-ink">Assigned micro-training and retest status</h4>
                      <div className="mt-4 grid gap-3">
                        {employeeReport.training_assignments.length ? (
                          employeeReport.training_assignments.slice(0, 3).map((assignment) => (
                            <div key={assignment.id} className="rounded-2xl border border-ink/10 bg-white px-4 py-3">
                              <div className="flex items-center justify-between gap-3">
                                <div className="font-semibold text-ink">{assignment.module_title}</div>
                                <StatusBadge value={assignment.status} />
                              </div>
                              <p className="mt-2 text-sm leading-7 text-slate">{assignment.module_body}</p>
                              {assignment.retest_scheduled_for ? (
                                <div className="mt-3 text-xs uppercase tracking-[0.18em] text-slate">
                                  Retest scheduled: {formatDateTime(assignment.retest_scheduled_for)}
                                </div>
                              ) : null}
                            </div>
                          ))
                        ) : (
                          <EmptyPlotMessage message="No adaptive training has been assigned to this employee yet." />
                        )}
                      </div>
                    </section>
                  </div>
                </div>
              </div>
            )}
          </Panel>

          <Panel>
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div className="section-title">Department Intelligence</div>
                <h3 className="display-font mt-2 text-xl font-semibold tracking-[-0.03em] text-ink">Department behavior report</h3>
              </div>
              <label className="flex min-w-[320px] flex-col gap-2 text-xs uppercase tracking-[0.18em] text-slate">
                Select Department
                <select
                  value={selectedDepartmentId}
                  onChange={(event) => setSelectedDepartmentId(event.target.value)}
                  className="rounded-2xl border border-ink/10 bg-white px-4 py-3 text-sm font-medium text-ink outline-none"
                >
                  {riskIntel.department_reports.map((report) => (
                    <option key={report.department_id} value={report.department_id}>
                      {report.department} / Avg Risk {report.avg_risk_score.toFixed(1)}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {selectedDepartment ? (
              <div className="mt-6 grid gap-4">
                <div className="grid gap-4 xl:grid-cols-[300px_1fr]">
                  <section className="grid gap-4 rounded-[1.5rem] border border-ink/10 bg-white/80 p-5">
                    <div>
                      <div className="text-xs uppercase tracking-[0.18em] text-slate">Selected Department</div>
                      <h4 className="mt-3 text-3xl font-semibold text-ink">{selectedDepartment.department}</h4>
                      <p className="mt-2 text-sm leading-7 text-slate">
                        Department-level risk and behavior report built from phishing interaction events, reporting actions, and training completions.
                      </p>
                    </div>
                    <div className={`rounded-[1.5rem] px-4 py-4 text-sm font-semibold ${riskTone(selectedDepartment.avg_risk_score)}`}>
                      Department risk score: {selectedDepartment.avg_risk_score.toFixed(1)}
                    </div>
                    <div className="grid gap-3">
                      <SummaryRow label="Employees" value={selectedDepartment.employee_count} />
                      <SummaryRow label="Click Rate" value={`${selectedDepartment.click_rate}%`} />
                      <SummaryRow label="Report Rate" value={`${selectedDepartment.report_rate}%`} />
                      <SummaryRow label="Opened Email Rate" value={`${selectedDepartment.opened_email_rate}%`} />
                      <SummaryRow label="Training Completions" value={selectedDepartment.training_completion_count} />
                    </div>
                  </section>

                  <section className="grid gap-4">
                    <div className="grid gap-4 md:grid-cols-4">
                      <SignalCard label="Employees" value={selectedDepartment.employee_count} tone="ink" />
                      <SignalCard label="Risky Actions" value={selectedDepartment.risky_interactions} tone="ember" />
                      <SignalCard label="Reports" value={selectedDepartment.report_events} tone="moss" />
                      <SignalCard label="Last Activity" value={selectedDepartment.last_activity_at ? shortDate(selectedDepartment.last_activity_at) : "None"} tone="tide" />
                    </div>

                    <div className="grid gap-4 xl:grid-cols-2">
                      <section className="rounded-[1.5rem] border border-ink/10 bg-white/80 p-5">
                        <div className="text-xs uppercase tracking-[0.18em] text-slate">Department Risk Trend</div>
                        <h4 className="mt-2 text-xl font-semibold text-ink">How the average score is moving</h4>
                        <div className="mt-4">
                          <TrendChart data={selectedDepartment.risk_trend.map((point) => ({ date: point.date, value: point.value }))} />
                        </div>
                      </section>

                      <section className="rounded-[1.5rem] border border-ink/10 bg-white/80 p-5">
                        <div className="text-xs uppercase tracking-[0.18em] text-slate">Behavior Trend</div>
                        <h4 className="mt-2 text-xl font-semibold text-ink">Interaction volume over the last week</h4>
                        <div className="mt-4">
                          <TrendChart data={selectedDepartment.behavior_trend.map((point) => ({ date: point.date, value: point.value }))} />
                        </div>
                      </section>
                    </div>
                  </section>
                </div>

                <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
                  <section className="rounded-[1.5rem] border border-ink/10 bg-white/80 p-5">
                    <div className="text-xs uppercase tracking-[0.18em] text-slate">Behavior Signals</div>
                    <h4 className="mt-2 text-xl font-semibold text-ink">What is happening inside this team</h4>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {selectedDepartment.top_behavior_signals.length ? (
                        selectedDepartment.top_behavior_signals.map((signal) => (
                          <span key={signal.label} className="rounded-full bg-sand px-3 py-2 text-sm font-semibold text-ink">
                            {humanizeKey(signal.label)} {signal.value}
                          </span>
                        ))
                      ) : (
                        <span className="rounded-full bg-sand px-3 py-2 text-sm text-slate">No department signals recorded yet.</span>
                      )}
                    </div>
                    <p className="mt-5 text-sm leading-7 text-slate">
                      Use these signals to explain the dominant department behavior pattern, such as frequent clicks, consistent reporting, or low engagement with training.
                    </p>
                  </section>

                  <section className="rounded-[1.5rem] border border-ink/10 bg-white/80 p-5">
                    <div className="text-xs uppercase tracking-[0.18em] text-slate">Department Scoreboard</div>
                    <h4 className="mt-2 text-xl font-semibold text-ink">Compare every team at a glance</h4>
                    <div className="mt-4 overflow-x-auto">
                      <table className="min-w-full text-left text-sm">
                        <thead className="text-slate">
                          <tr>
                            <th className="py-3 pr-4">Department</th>
                            <th className="py-3 pr-4">Avg Risk</th>
                            <th className="py-3 pr-4">Click</th>
                            <th className="py-3 pr-4">Report</th>
                          </tr>
                        </thead>
                        <tbody>
                          {riskIntel.department_reports.map((report) => (
                            <tr
                              key={report.department_id}
                              className={`border-t border-ink/10 ${report.department_id === selectedDepartment.department_id ? "bg-tide/10" : ""}`}
                            >
                              <td className="py-3 pr-4 font-semibold text-ink">{report.department}</td>
                              <td className="py-3 pr-4">{report.avg_risk_score.toFixed(1)}</td>
                              <td className="py-3 pr-4">{report.click_rate}%</td>
                              <td className="py-3 pr-4">{report.report_rate}%</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                </div>
              </div>
            ) : (
              <div className="mt-6 rounded-[1.5rem] bg-white/70 px-4 py-8 text-sm text-slate">
                No department behavior data exists yet. Departments appear here once the admin creates them and employees start interacting with campaigns.
              </div>
            )}
          </Panel>
        </>
      )}
    </>
  );
}

function HeroPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-ink/10 bg-sand/55 px-3 py-2.5">
      <div className="text-[0.6rem] font-semibold uppercase tracking-[0.12em] text-slate">{label}</div>
      <div className="mt-1.5 line-clamp-2 text-sm font-semibold leading-5 text-ink">{value}</div>
    </div>
  );
}

function OverviewCard({
  label,
  value,
  tone,
  detail,
}: {
  label: string;
  value: string | number;
  tone: "ink" | "ember" | "tide" | "moss";
  detail: string;
}) {
  const toneMap = {
    ink: "text-ink",
    ember: "text-ember",
    tide: "text-tide",
    moss: "text-moss",
  };

  return (
    <div className="app-surface rounded-xl p-4" title={detail}>
      <div className="text-[0.62rem] font-semibold uppercase tracking-[0.13em] text-slate">{label}</div>
      <div className={`mt-2.5 display-font text-2xl font-semibold tracking-[-0.03em] ${toneMap[tone]}`}>{value}</div>
    </div>
  );
}

function SignalCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone: "ink" | "ember" | "tide" | "moss";
}) {
  const toneMap = {
    ink: "text-ink bg-white/80",
    ember: "text-ember bg-ember/5",
    tide: "text-tide bg-tide/5",
    moss: "text-moss bg-moss/10",
  };

  return (
    <div className={`rounded-xl border border-ink/10 px-4 py-3.5 ${toneMap[tone]}`}>
      <div className="text-xs uppercase tracking-[0.18em] text-slate">{label}</div>
      <div className="mt-2 display-font text-2xl font-semibold">{value}</div>
    </div>
  );
}

function AiSignal({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-ink/10 bg-sand px-3 py-2.5">
      <div className="text-xs uppercase tracking-[0.18em] text-slate">{label}</div>
      <div className="mt-2 text-sm font-semibold text-ink">{value}</div>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg bg-sand px-4 py-3">
      <div className="text-sm text-slate">{label}</div>
      <div className="text-sm font-semibold text-ink">{value}</div>
    </div>
  );
}

function EmptyPlotMessage({ message }: { message: string }) {
  return <div className="rounded-2xl bg-sand px-4 py-6 text-sm leading-7 text-slate">{message}</div>;
}

function OnboardingStep({ step, title, description }: { step: string; title: string; description: string }) {
  return (
    <div className="rounded-[1.5rem] border border-ink/10 bg-white/80 p-5">
      <div className="text-xs uppercase tracking-[0.18em] text-slate">Step {step}</div>
      <div className="mt-3 text-xl font-semibold text-ink">{title}</div>
      <p className="mt-3 text-sm leading-7 text-slate">{description}</p>
    </div>
  );
}

function humanizeKey(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function shortDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function formatMetadata(metadata: Record<string, unknown>) {
  const entries = Object.entries(metadata ?? {});
  if (!entries.length) {
    return "No additional metadata captured for this event.";
  }
  return entries
    .map(([key, value]) => `${humanizeKey(key)}: ${typeof value === "string" ? value : JSON.stringify(value)}`)
    .join(" / ");
}

function trendClassName(trend: string) {
  if (trend === "improving") {
    return "bg-moss/15 text-moss";
  }
  if (trend === "worsening") {
    return "bg-ember/10 text-ember";
  }
  return "bg-sand text-ink";
}

function riskTone(score: number) {
  if (score >= 60) {
    return "bg-ember/10 text-ember";
  }
  if (score >= 30) {
    return "bg-warning/15 text-amber-700";
  }
  return "bg-moss/15 text-moss";
}
