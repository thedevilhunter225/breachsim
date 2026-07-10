"use client";

import { useEffect, useState } from "react";

import { TrendChart } from "@/components/charts";
import { Panel } from "@/components/panel";
import { StatusBadge } from "@/components/status-badge";
import { useSession } from "@/components/session-provider";
import {
  createDepartment,
  createEmployee,
  Department,
  Employee,
  EmployeeImportResult,
  EmployeeRiskReport,
  getDepartments,
  getEmployeeReport,
  getEmployees,
  importEmployees,
  updateEmployee,
} from "@/lib/client-api";

const emptyForm = {
  employee_id: "",
  full_name: "",
  email: "",
  phone: "",
  department_id: "",
  role_title: "",
  approved_context_summary: "",
  approved_public_profile_summary: "",
};

export function EmployeesConsole() {
  const { session } = useSession();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [editingEmployeeId, setEditingEmployeeId] = useState<string | null>(null);
  const [departmentForm, setDepartmentForm] = useState({ name: "", code: "" });
  const [csvText, setCsvText] = useState(
    "employee_id,full_name,email,phone,department,role_title,approved_context_summary,consent_status\n"
  );
  const [message, setMessage] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<EmployeeImportResult | null>(null);
  const [selectedReport, setSelectedReport] = useState<EmployeeRiskReport | null>(null);
  const [reportLoadingId, setReportLoadingId] = useState<string | null>(null);

  async function loadData() {
    if (!session) return;
    const [employeeRows, departmentRows] = await Promise.all([
      getEmployees(session.access_token),
      getDepartments(session.access_token),
    ]);
    setEmployees(employeeRows);
    setDepartments(departmentRows);
    if (!form.department_id && departmentRows[0]) {
      setForm((current) => ({ ...current, department_id: departmentRows[0].id }));
    }
  }

  useEffect(() => {
    void loadData();
  }, [session]);

  async function handleCreate() {
    if (!session) return;
    if (editingEmployeeId) {
      const reportEmployeeId = editingEmployeeId;
      await updateEmployee(session.access_token, editingEmployeeId, {
        full_name: form.full_name,
        email: form.email,
        phone: form.phone || null,
        department_id: form.department_id || null,
        role_title: form.role_title,
        approved_context_summary: form.approved_context_summary || null,
        approved_public_profile_summary: form.approved_public_profile_summary || null,
      });
      setMessage("Employee updated successfully.");
      setEditingEmployeeId(null);
      if (selectedReport?.employee.id === reportEmployeeId) {
        await loadEmployeeReport(reportEmployeeId);
      }
    } else {
      await createEmployee(session.access_token, {
        ...form,
        phone: form.phone || null,
        approved_context_summary: form.approved_context_summary || null,
        approved_public_profile_summary: form.approved_public_profile_summary || null,
        training_preferences: ["email", "micro-card"],
        consent_status: "consented",
        status: "active",
      });
      setMessage("Employee added successfully.");
    }
    setForm({ ...emptyForm, department_id: departments[0]?.id ?? "" });
    setImportResult(null);
    await loadData();
  }

  async function handleCreateDepartment() {
    if (!session) return;
    const department = await createDepartment(session.access_token, {
      name: departmentForm.name,
      code: departmentForm.code,
    });
    setDepartmentForm({ name: "", code: "" });
    setMessage("Department created successfully.");
    setImportResult(null);
    await loadData();
    setForm((current) => ({ ...current, department_id: department.id }));
  }

  async function handleImport() {
    if (!session) return;
    const rows = parseCsv(csvText);
    const result = await importEmployees(session.access_token, { rows });
    setImportResult(result);
    setMessage(`CSV import finished. ${result.created} created, ${result.updated} updated.`);
    await loadData();
  }

  async function handleFileUpload(file: File | null) {
    if (!file) return;
    setCsvText(await file.text());
  }

  async function loadEmployeeReport(employeeId: string) {
    if (!session) return;
    setReportLoadingId(employeeId);
    try {
      const report = await getEmployeeReport(session.access_token, employeeId);
      setSelectedReport(report);
      setMessage(`Loaded risk report for ${report.employee.full_name}.`);
    } finally {
      setReportLoadingId(null);
    }
  }

  function startEditing(employee: Employee) {
    setEditingEmployeeId(employee.id);
    setForm({
      employee_id: employee.employee_id,
      full_name: employee.full_name,
      email: employee.email,
      phone: employee.phone ?? "",
      department_id: employee.department_id ?? departments[0]?.id ?? "",
      role_title: employee.role_title,
      approved_context_summary: employee.approved_context_summary ?? "",
      approved_public_profile_summary: employee.approved_public_profile_summary ?? "",
    });
    setMessage(`Editing ${employee.full_name}. Save to update context and targeting data.`);
  }

  function cancelEditing() {
    setEditingEmployeeId(null);
    setForm({ ...emptyForm, department_id: departments[0]?.id ?? "" });
    setMessage("Edit cancelled.");
  }

  const hasDepartments = departments.length > 0;
  const hasEmployees = employees.length > 0;

  return (
    <>
      <Panel>
        <div className="section-title">Organization Directory</div>
        <div className="mt-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-3xl font-semibold">Build the directory from company-owned data</h2>
            <p className="mt-2 max-w-2xl text-sm leading-7 text-slate">
              No sample departments or employees are preloaded now. The company admin creates departments, adds employees, and controls the entire phishing simulation directory from this workspace.
            </p>
          </div>
          <div className="rounded-[1.5rem] bg-white/70 px-4 py-3 text-sm text-slate">
            Live employee count: <span className="font-semibold text-ink">{employees.length}</span>
          </div>
        </div>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <Panel>
          <div className="section-title">Admin Inputs</div>
          <div className="mt-4 grid gap-4">
            <div className="rounded-[1.5rem] border border-ink/10 bg-white/70 p-4">
              <div className="text-sm font-semibold text-ink">Create Department</div>
              <div className="mt-3 grid gap-3">
                <input value={departmentForm.name} onChange={(event) => setDepartmentForm({ ...departmentForm, name: event.target.value })} placeholder="Department name" className="rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none" />
                <input value={departmentForm.code} onChange={(event) => setDepartmentForm({ ...departmentForm, code: event.target.value.toUpperCase() })} placeholder="Department code" className="rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none" />
                <button onClick={handleCreateDepartment} className="rounded-2xl bg-tide px-4 py-3 font-semibold text-white">Save Department</button>
              </div>
            </div>

            <div className="rounded-[1.5rem] border border-ink/10 bg-white/70 p-4">
              <div className="text-sm font-semibold text-ink">{editingEmployeeId ? "Edit Employee" : "Add Employee"}</div>
              <div className="mt-3 grid gap-4">
                {!hasDepartments ? (
                  <div className="rounded-2xl bg-sand px-4 py-4 text-sm leading-7 text-slate">
                    Create at least one department first. Employee onboarding stays disabled until a department exists.
                  </div>
                ) : null}
                <input value={form.employee_id} onChange={(event) => setForm({ ...form, employee_id: event.target.value })} placeholder="Employee ID" disabled={Boolean(editingEmployeeId)} className="rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none disabled:bg-sand disabled:text-slate" />
                <input value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} placeholder="Full name" className="rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none" />
                <input value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="Email address" className="rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none" />
                <input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} placeholder="Phone number" className="rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none" />
                <select value={form.department_id} onChange={(event) => setForm({ ...form, department_id: event.target.value })} disabled={!hasDepartments} className="rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none disabled:bg-sand disabled:text-slate">
                  {departments.map((department) => (
                    <option key={department.id} value={department.id}>{department.name}</option>
                  ))}
                </select>
                <input value={form.role_title} onChange={(event) => setForm({ ...form, role_title: event.target.value })} placeholder="Role title" className="rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none" />
                <textarea value={form.approved_context_summary} onChange={(event) => setForm({ ...form, approved_context_summary: event.target.value })} placeholder="Approved context summary" className="min-h-28 rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none" />
                <textarea value={form.approved_public_profile_summary} onChange={(event) => setForm({ ...form, approved_public_profile_summary: event.target.value })} placeholder="Optional provided profile summary" className="min-h-24 rounded-2xl border border-ink/10 bg-white px-4 py-3 outline-none" />
                <div className="flex flex-wrap gap-3">
                  <button onClick={handleCreate} disabled={!hasDepartments} className="rounded-2xl bg-ink px-4 py-3 font-semibold text-mist disabled:bg-slate/40 disabled:text-white/70">{editingEmployeeId ? "Update Employee" : "Save Employee"}</button>
                  {editingEmployeeId ? (
                    <button onClick={cancelEditing} className="rounded-2xl border border-ink/10 bg-white px-4 py-3 font-semibold text-ink">Cancel Edit</button>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="rounded-[1.5rem] border border-ink/10 bg-white/70 p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="text-sm font-semibold text-ink">CSV Import</div>
                <label className="rounded-2xl border border-ink/10 bg-white px-4 py-2 text-sm font-semibold text-ink">
                  Upload CSV
                  <input type="file" accept=".csv,text/csv" className="hidden" onChange={(event) => void handleFileUpload(event.target.files?.[0] ?? null)} />
                </label>
              </div>
              <textarea value={csvText} onChange={(event) => setCsvText(event.target.value)} className="mt-3 min-h-44 rounded-2xl border border-ink/10 bg-white px-4 py-3 font-mono text-xs outline-none" />
              <div className="mt-3 text-xs leading-6 text-slate">
                Expected columns: `employee_id, full_name, email, phone, department, role_title, approved_context_summary, consent_status`
              </div>
              {importResult ? (
                <div className="mt-3 rounded-2xl bg-sand px-4 py-3 text-sm text-slate">
                  Created: <span className="font-semibold text-ink">{importResult.created}</span> · Updated: <span className="font-semibold text-ink">{importResult.updated}</span> · Errors: <span className="font-semibold text-ink">{importResult.errors.length}</span>
                </div>
              ) : null}
              {importResult?.errors?.length ? (
                <div className="mt-3 rounded-2xl bg-ember/10 px-4 py-3 text-sm text-ember">
                  {importResult.errors.map((error, index) => (
                    <div key={index}>Row {String(error.row ?? "?")}: {String(error.error ?? "Unknown error")}</div>
                  ))}
                </div>
              ) : null}
              <button onClick={handleImport} className="mt-4 rounded-2xl bg-moss px-4 py-3 font-semibold text-white">Import CSV</button>
            </div>

            {message ? <div className="rounded-2xl bg-moss/10 px-4 py-3 text-sm text-moss">{message}</div> : null}
          </div>
        </Panel>

        <Panel className="overflow-hidden p-0">
          {hasEmployees ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-white/80">
                  <tr className="text-slate">
                    <th className="px-5 py-4">Employee</th>
                    <th className="px-5 py-4">Department</th>
                    <th className="px-5 py-4">Status</th>
                    <th className="px-5 py-4">Risk</th>
                    <th className="px-5 py-4">Themes</th>
                    <th className="px-5 py-4">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {employees.map((employee) => (
                    <tr key={employee.id} className="border-t border-ink/10 bg-white/55">
                      <td className="px-5 py-4">
                        <div className="font-semibold">{employee.full_name}</div>
                        <div className="text-slate">{employee.email}</div>
                        <div className="mt-1 text-xs uppercase tracking-[0.18em] text-slate">{employee.role_title}</div>
                      </td>
                      <td className="px-5 py-4">{employee.department_name}</td>
                      <td className="px-5 py-4"><StatusBadge value={employee.status} /></td>
                      <td className="px-5 py-4 font-semibold text-ember">{employee.risk_score}</td>
                      <td className="px-5 py-4 text-slate">{employee.latest_context_profile?.likely_scenario_themes?.join(", ")}</td>
                      <td className="px-5 py-4">
                        <div className="flex flex-wrap gap-2">
                          <button onClick={() => startEditing(employee)} className="rounded-2xl border border-ink/10 bg-white px-3 py-2 text-sm font-semibold text-ink">
                            Edit Context
                          </button>
                          <button
                            onClick={() => void loadEmployeeReport(employee.id)}
                            className="rounded-2xl bg-tide px-3 py-2 text-sm font-semibold text-white"
                          >
                            {reportLoadingId === employee.id ? "Loading..." : "View Risk Report"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="grid min-h-[340px] place-items-center bg-white/55 px-6 py-10 text-center">
              <div className="max-w-xl">
                <div className="text-xs uppercase tracking-[0.2em] text-slate">Empty Directory</div>
                <h3 className="mt-4 text-3xl font-semibold text-ink">No employees have been added yet</h3>
                <p className="mt-3 text-sm leading-7 text-slate">
                  Start by creating a department, then add employees manually or import them with CSV. Risk reports and phishing targeting will appear once the directory has real company data.
                </p>
              </div>
            </div>
          )}
        </Panel>
      </div>

      {selectedReport ? (
        <Panel>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="section-title">Employee Risk Report</div>
              <h2 className="mt-3 text-3xl font-semibold">{selectedReport.employee.full_name}</h2>
              <p className="mt-2 text-sm leading-7 text-slate">
                {selectedReport.employee.email} · {selectedReport.employee.department_name ?? "No department"} · {selectedReport.employee.role_title}
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <div className="rounded-[1.5rem] bg-white/70 px-4 py-3 text-sm text-slate">
                Current risk: <span className="font-semibold text-ink">{selectedReport.current_risk_score}/100</span>
              </div>
              <div className={`rounded-[1.5rem] px-4 py-3 text-sm font-semibold ${trendClassName(selectedReport.trend)}`}>
                Trend: {humanizeKey(selectedReport.trend)}
              </div>
              <button onClick={() => setSelectedReport(null)} className="rounded-[1.5rem] border border-ink/10 bg-white px-4 py-3 text-sm font-semibold text-ink">
                Close Report
              </button>
            </div>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-3 xl:grid-cols-6">
            <MetricCard label="Opened Emails" value={selectedReport.behavior_summary.opened_emails} />
            <MetricCard label="Clicked Links" value={selectedReport.behavior_summary.clicked_links} />
            <MetricCard label="Visited Pages" value={selectedReport.behavior_summary.visited_landing_pages} />
            <MetricCard label="Reported Suspicious" value={selectedReport.behavior_summary.reported} />
            <MetricCard label="Training Completed" value={selectedReport.behavior_summary.training_completed} />
            <MetricCard
              label="Last Activity"
              value={selectedReport.behavior_summary.last_event_at ? formatDateTime(selectedReport.behavior_summary.last_event_at, "short") : "No events"}
            />
          </div>

          <div className="mt-6 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-[1.5rem] border border-ink/10 bg-white/70 p-4">
              <div className="text-sm font-semibold text-ink">Risk Trend Over Time</div>
              <div className="mt-4">
                {selectedReport.risk_history.length ? (
                  <TrendChart
                    data={selectedReport.risk_history.map((point) => ({
                      date: point.date,
                      value: point.score,
                    }))}
                  />
                ) : (
                  <div className="rounded-2xl bg-sand px-4 py-5 text-sm text-slate">
                    No risk history has been recorded yet. Once the employee opens, clicks, submits, or completes training, the timeline appears here.
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-[1.5rem] border border-ink/10 bg-white/70 p-4">
              <div className="text-sm font-semibold text-ink">Why This Score Changed</div>
              <div className="mt-4 flex flex-wrap gap-2">
                {Object.entries(selectedReport.latest_breakdown).length ? (
                  Object.entries(selectedReport.latest_breakdown).map(([reason, score]) => (
                    <span
                      key={reason}
                      className={`rounded-full px-3 py-2 text-sm font-semibold ${Number(score) > 0 ? "bg-ember/10 text-ember" : "bg-moss/15 text-moss"}`}
                    >
                      {humanizeKey(reason)} {Number(score) > 0 ? `+${score}` : score}
                    </span>
                  ))
                ) : (
                  <span className="rounded-full bg-sand px-3 py-2 text-sm text-slate">No risk breakdown available yet.</span>
                )}
              </div>
              <div className="mt-6 rounded-2xl bg-sand px-4 py-4 text-sm leading-7 text-slate">
                Behavior analysis summarizes how the employee interacts with simulated phishing content over time. Positive behaviors like reporting suspicious messages and completing training reduce score; risky behaviors like clicking or submitting increase it.
              </div>
            </div>
          </div>

          <div className="mt-6 grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-[1.5rem] border border-ink/10 bg-white/70 p-4">
              <div className="text-sm font-semibold text-ink">Behavior Timeline</div>
              <div className="mt-4 grid gap-3">
                {selectedReport.events.length ? (
                  selectedReport.events.map((event) => (
                    <div key={event.id} className="rounded-2xl border border-ink/10 bg-white px-4 py-3">
                      <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                        <div className="font-semibold text-ink">{humanizeKey(event.event_type)}</div>
                        <div className="text-xs uppercase tracking-[0.18em] text-slate">
                          {event.channel ? `${event.channel} · ` : ""}
                          {formatDateTime(event.occurred_at)}
                        </div>
                      </div>
                      <div className="mt-2 text-sm leading-7 text-slate">
                        {formatMetadata(event.metadata)}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl bg-sand px-4 py-5 text-sm text-slate">No tracked events yet for this employee.</div>
                )}
              </div>
            </div>

            <div className="rounded-[1.5rem] border border-ink/10 bg-white/70 p-4">
              <div className="text-sm font-semibold text-ink">Training and Retest</div>
              <div className="mt-4 grid gap-3">
                {selectedReport.training_assignments.length ? (
                  selectedReport.training_assignments.map((assignment) => (
                    <div key={assignment.id} className="rounded-2xl border border-ink/10 bg-white px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="font-semibold text-ink">{assignment.module_title}</div>
                        <StatusBadge value={assignment.status} />
                      </div>
                      <p className="mt-2 text-sm leading-7 text-slate">{assignment.module_body}</p>
                      {assignment.assigned_reason_codes.length ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {assignment.assigned_reason_codes.map((reason) => (
                            <span key={reason} className="rounded-full bg-sand px-3 py-1 text-xs font-semibold text-ink">
                              {humanizeKey(reason)}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      {assignment.guidance_points.length ? (
                        <div className="mt-3 text-sm leading-7 text-slate">
                          {assignment.guidance_points.join(" · ")}
                        </div>
                      ) : null}
                      {assignment.retest_scheduled_for ? (
                        <div className="mt-3 text-xs uppercase tracking-[0.18em] text-slate">
                          Retest scheduled: {formatDateTime(assignment.retest_scheduled_for)}
                        </div>
                      ) : null}
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl bg-sand px-4 py-5 text-sm text-slate">
                    No targeted training has been assigned yet. After a risky interaction, adaptive micro-training appears here.
                  </div>
                )}
              </div>
            </div>
          </div>
        </Panel>
      ) : null}
    </>
  );
}

function MetricCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-[1.5rem] border border-ink/10 bg-white/70 px-4 py-4">
      <div className="text-xs uppercase tracking-[0.18em] text-slate">{label}</div>
      <div className="mt-3 text-2xl font-semibold text-ink">{value}</div>
    </div>
  );
}

function parseCsv(raw: string) {
  const lines = raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length < 2) {
    return [];
  }

  const headers = parseCsvLine(lines[0]).map((value) => value.trim());
  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    const row = Object.fromEntries(headers.map((header, index) => [header, values[index]?.trim() ?? ""]));
    return {
      employee_id: row.employee_id,
      full_name: row.full_name,
      email: row.email,
      phone: row.phone || null,
      department: row.department,
      role_title: row.role_title,
      approved_context_summary: row.approved_context_summary || null,
      consent_status: row.consent_status || "consented",
    };
  });
}

function parseCsvLine(line: string) {
  const values: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === '"') {
      const nextChar = line[index + 1];
      if (inQuotes && nextChar === '"') {
        current += '"';
        index += 1;
        continue;
      }
      inQuotes = !inQuotes;
      continue;
    }
    if (char === "," && !inQuotes) {
      values.push(current);
      current = "";
      continue;
    }
    current += char;
  }

  values.push(current);
  return values;
}

function humanizeKey(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
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

function formatDateTime(value: string, style: "full" | "short" = "full") {
  const date = new Date(value);
  return date.toLocaleString(undefined, style === "short" ? { month: "short", day: "numeric" } : {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatMetadata(metadata: Record<string, unknown>) {
  const entries = Object.entries(metadata ?? {});
  if (!entries.length) {
    return "No additional metadata captured for this event.";
  }
  return entries
    .map(([key, value]) => {
      const normalizedValue = typeof value === "string" ? value : JSON.stringify(value);
      return `${humanizeKey(key)}: ${normalizedValue}`;
    })
    .join(" · ");
}
