# Data Flow Explanation

1. Admin or campaign manager imports employees with approved internal context.
2. A context profile is derived only from role, department, approved notes, and organization-provided summaries.
3. Scenario generation runs through the policy engine before and after content creation.
4. Approved scenarios are linked to campaigns and require explicit admin approval before activation.
5. Sandbox delivery creates tokenized previews and normalized delivery records.
6. Landing page interactions create event log rows with pseudonymous IDs.
7. Failure-reason analysis and risk scoring update employee and department views.
8. Micro-training assignments are created for risky interactions and can trigger adaptive retests.
9. Audit logs record sensitive actions such as approvals, policy changes, exports, and launches.
