"use client";

import { useEffect, useState } from "react";
import { Building2, FileUp, Pencil, Plus, Search, ShieldAlert, UserRound, UsersRound, X, type LucideIcon } from "lucide-react";

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
  const [composer, setComposer] = useState<"department" | "employee" | "import" | null>(null);
  const [search, setSearch] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  async function loadData() {
    if (!session) return;
    setLoading(true);
    setLoadError(null);
    try {
      const [employeeRows, departmentRows] = await Promise.all([
        getEmployees(session.access_token),
        getDepartments(session.access_token),
      ]);
      setEmployees(employeeRows);
      setDepartments(departmentRows);
      if (!form.department_id && departmentRows[0]) {
        setForm((current) => ({ ...current, department_id: departmentRows[0].id }));
      }
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Unable to load the employee directory.");
    } finally {
      setLoading(false);
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
    setComposer(null);
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
    setComposer(null);
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
    setComposer("employee");
  }

  function cancelEditing() {
    setEditingEmployeeId(null);
    setForm({ ...emptyForm, department_id: departments[0]?.id ?? "" });
    setMessage("Edit cancelled.");
    setComposer(null);
  }

  const hasDepartments = departments.length > 0;
  const hasEmployees = employees.length > 0;
  const filteredEmployees = employees.filter((employee) => {
    if (departmentFilter && employee.department_id !== departmentFilter) return false;
    const query = search.trim().toLowerCase();
    if (!query) return true;
    return [employee.full_name, employee.email, employee.employee_id, employee.department_name, employee.role_title]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });

  return (
    <>
      <section className="workspace-page-header">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="section-title">Organization directory</div>
            <h1 className="display-font mt-2 text-2xl font-semibold tracking-[-0.035em] text-ink">People and departments</h1>
            <p className="mt-1.5 text-sm text-slate">Your people, their departments, and the support they need.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => setComposer("department")} className="app-secondary-button">
              <Building2 size={15} /> New department
            </button>
            <button type="button" onClick={() => setComposer("import")} className="app-secondary-button">
              <FileUp size={15} /> Import CSV
            </button>
            <button type="button" onClick={() => setComposer("employee")} className="app-primary-button" disabled={!hasDepartments}>
              <Plus size={15} /> Add employee
            </button>
          </div>
        </div>
      </section>

      {loadError ? <div className="workspace-error" role="alert"><span>{loadError}</span><button type="button" className="app-secondary-button" onClick={() => void loadData()}>Retry</button></div> : null}

      <section className="grid gap-3 sm:grid-cols-3">
        <DirectoryStat icon={UsersRound} label="Employees" value={employees.length} />
        <DirectoryStat icon={Building2} label="Departments" value={departments.length} />
        <DirectoryStat icon={ShieldAlert} label="Elevated risk" value={employees.filter((employee) => employee.risk_score >= 60).length} />
      </section>

      <div className={composer ? "grid gap-4 xl:grid-cols-[380px_minmax(0,1fr)]" : "grid gap-4"}>
        {composer ? <Panel className="self-start xl:sticky xl:top-[88px] xl:max-h-[calc(100vh-112px)] xl:overflow-y-auto">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="section-title">Directory management</div>
              <h2 className="display-font mt-2 text-lg font-semibold text-ink">
                {composer === "department" ? "Create department" : composer === "import" ? "Import employees" : editingEmployeeId ? "Edit employee" : "Add employee"}
              </h2>
            </div>
            <button type="button" onClick={() => { setComposer(null); setEditingEmployeeId(null); }} className="app-icon-button" aria-label="Close editor"><X size={16} /></button>
          </div>
          <div className="mt-4 grid gap-4">
            {composer === "department" ? <div className="rounded-xl border border-ink/10 bg-white/70 p-4">
              <div className="text-sm font-semibold text-ink">Create Department</div>
              <div className="mt-3 grid gap-3">
                <input value={departmentForm.name} onChange={(event) => setDepartmentForm({ ...departmentForm, name: event.target.value })} placeholder="Department name" className="rounded-lg border border-ink/10 bg-white px-3 py-2.5 outline-none" />
                <input value={departmentForm.code} onChange={(event) => setDepartmentForm({ ...departmentForm, code: event.target.value.toUpperCase() })} placeholder="Department code" className="rounded-lg border border-ink/10 bg-white px-3 py-2.5 outline-none" />
                <button onClick={handleCreateDepartment} className="app-primary-button">Save department</button>
              </div>
            </div> : null}

            {composer === "employee" ? <div className="rounded-xl border border-ink/10 bg-white/70 p-4">
              <div className="text-sm font-semibold text-ink">{editingEmployeeId ? "Edit Employee" : "Add Employee"}</div>
              <div className="mt-3 grid gap-4">
                {!hasDepartments ? (
                  <div className="rounded-2xl bg-sand px-4 py-4 text-sm leading-7 text-slate">
                    Create at least one department first. Employee onboarding stays disabled until a department exists.
                  </div>
                ) : null}
                <input value={form.employee_id} onChange={(event) => setForm({ ...form, employee_id: event.target.value })} placeholder="Employee ID" disabled={Boolean(editingEmployeeId)} className="rounded-lg border border-ink/10 bg-white px-3 py-2.5 outline-none disabled:bg-sand disabled:text-slate" />
                <input value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} placeholder="Full name" className="rounded-lg border border-ink/10 bg-white px-3 py-2.5 outline-none" />
                <input value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="Email address" className="rounded-lg border border-ink/10 bg-white px-3 py-2.5 outline-none" />
                <input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} placeholder="Phone number" className="rounded-lg border border-ink/10 bg-white px-3 py-2.5 outline-none" />
                <select value={form.department_id} onChange={(event) => setForm({ ...form, department_id: event.target.value })} disabled={!hasDepartments} className="rounded-lg border border-ink/10 bg-white px-3 py-2.5 outline-none disabled:bg-sand disabled:text-slate">
                  {departments.map((department) => (
                    <option key={department.id} value={department.id}>{department.name}</option>
                  ))}
                </select>
                <input value={form.role_title} onChange={(event) => setForm({ ...form, role_title: event.target.value })} placeholder="Role title" className="rounded-lg border border-ink/10 bg-white px-3 py-2.5 outline-none" />
                <textarea value={form.approved_context_summary} onChange={(event) => setForm({ ...form, approved_context_summary: event.target.value })} placeholder="Approved targeting context" className="min-h-24 rounded-lg border border-ink/10 bg-white px-3 py-2.5 outline-none" />
                <textarea value={form.approved_public_profile_summary} onChange={(event) => setForm({ ...form, approved_public_profile_summary: event.target.value })} placeholder="Optional provided profile summary" className="min-h-20 rounded-lg border border-ink/10 bg-white px-3 py-2.5 outline-none" />
                <div className="flex flex-wrap gap-3">
                  <button onClick={handleCreate} disabled={!hasDepartments} className="app-primary-button">{editingEmployeeId ? "Update employee" : "Save employee"}</button>
                  {editingEmployeeId ? (
                    <button onClick={cancelEditing} className="app-secondary-button">Cancel</button>
                  ) : null}
                </div>
              </div>
            </div> : null}

            {composer === "import" ? <div className="rounded-xl border border-ink/10 bg-white/70 p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="text-sm font-semibold text-ink">CSV Import</div>
                <label className="app-secondary-button cursor-pointer">
                  <FileUp size={15} /> Upload CSV
                  <input type="file" accept=".csv,text/csv" className="hidden" onChange={(event) => void handleFileUpload(event.target.files?.[0] ?? null)} />
                </label>
              </div>
              <textarea value={csvText} onChange={(event) => setCsvText(event.target.value)} className="mt-3 min-h-52 w-full rounded-lg border border-ink/10 bg-white px-3 py-2.5 font-mono text-xs outline-none" />
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
              <button onClick={handleImport} className="app-primary-button mt-4">Import employees</button>
            </div> : null}

            {message ? <div className="rounded-2xl bg-moss/10 px-4 py-3 text-sm text-moss">{message}</div> : null}
          </div>
        </Panel> : null}

        <Panel flush className="overflow-hidden">
          <div className="flex flex-col gap-3 border-b border-ink/[0.08] px-5 py-4 md:flex-row md:items-center md:justify-between md:px-6">
            <div>
              <div className="text-sm font-semibold text-ink">Employee records</div>
              <div className="mt-0.5 text-xs text-slate">{filteredEmployees.length} of {employees.length} people</div>
            </div>
            <div className="flex w-full flex-col gap-2 sm:flex-row md:w-auto">
            <select className="field sm:!w-44" aria-label="Filter by department" value={departmentFilter} onChange={(event) => setDepartmentFilter(event.target.value)}>
              <option value="">All departments</option>
              {departments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}
            </select>
            <label className="relative block w-full md:w-64">
              <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate" />
              <input aria-label="Search employee records" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, email or role…" className="h-10 w-full rounded-lg border border-ink/10 bg-white pl-9 pr-3 text-sm outline-none" />
            </label>
            </div>
          </div>
          {hasEmployees || loading || loadError ? (
            <div className="overflow-x-auto">
              <table className="data-table min-w-full text-left text-sm">
                <thead>
                  <tr>
                    <th className="px-5 py-3 md:px-6">Employee</th>
                    <th className="px-4 py-3">Department</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Risk</th>
                    <th className="px-5 py-3 text-right md:px-6">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? <tr><td colSpan={5}><div className="py-8 text-center text-muted" role="status">Loading employee records…</div></td></tr> : loadError && !hasEmployees ? <tr><td colSpan={5} className="text-center text-muted">Employee records are unavailable. Use Retry above to reload them.</td></tr> : filteredEmployees.length === 0 ? <tr><td colSpan={5}><div className="py-10 text-center"><Search size={22} className="mx-auto mb-3 text-subtle" /><p className="font-medium">No people match these filters</p><p className="mt-1 text-xs text-muted">Try another name or choose a different department.</p><button type="button" onClick={() => { setSearch(""); setDepartmentFilter(""); }} className="workspace-text-link mt-4">Clear filters</button></div></td></tr> : filteredEmployees.map((employee) => (
                    <tr key={employee.id}>
                      <td className="px-5 py-3.5 md:px-6">
                        <div className="flex items-center gap-3">
                          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-tide/[0.08] text-xs font-bold text-tide">
                            {employee.full_name.split(" ").map((part) => part[0] ?? "").join("").slice(0, 2).toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <div className="font-semibold text-ink">{employee.full_name}</div>
                            <div className="mt-0.5 max-w-[280px] truncate text-xs text-slate">{employee.email} · {employee.role_title}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-slate">{employee.department_name ?? "Unassigned"}</td>
                      <td className="px-4 py-3.5"><StatusBadge value={employee.status} /></td>
                      <td className="px-4 py-3.5"><span className="font-semibold text-ink">{employee.risk_score}</span><span className="ml-1 text-xs text-slate">/100</span></td>
                      <td className="px-5 py-3.5 md:px-6">
                        <div className="flex justify-end gap-2">
                          <button onClick={() => startEditing(employee)} className="app-icon-button" title="Edit employee" aria-label={`Edit ${employee.full_name}`}>
                            <Pencil size={15} />
                          </button>
                          <button
                            onClick={() => void loadEmployeeReport(employee.id)}
                            className="app-secondary-button whitespace-nowrap"
                          >
                            {reportLoadingId === employee.id ? "Loading..." : "Risk profile"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="grid min-h-[300px] place-items-center px-6 py-10 text-center">
              <div className="max-w-md">
                <div className="mx-auto grid h-12 w-12 place-items-center rounded-xl bg-tide/[0.08] text-tide"><UserRound size={21} /></div>
                <h3 className="display-font mt-4 text-xl font-semibold text-ink">Build your company directory</h3>
                <p className="mt-2 text-sm leading-6 text-slate">Create a department, then add employees manually or import a validated CSV.</p>
                <button type="button" onClick={() => setComposer("department")} className="app-primary-button mt-5"><Plus size={15} /> Create first department</button>
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

function DirectoryStat({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: number }) {
  return (
    <div className="app-surface flex items-center gap-3 rounded-xl px-4 py-3.5">
      <div className="grid h-9 w-9 place-items-center rounded-lg bg-tide/[0.08] text-tide"><Icon size={16} /></div>
      <div>
        <div className="display-font text-lg font-semibold text-ink">{value}</div>
        <div className="text-[0.65rem] font-semibold uppercase tracking-[0.1em] text-slate">{label}</div>
      </div>
    </div>
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
