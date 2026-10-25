from __future__ import annotations


def test_import_employees(client, admin_headers):
    response = client.post(
        "/api/v1/employees/import",
        headers=admin_headers,
        json={
            "rows": [
                {
                    "employee_id": "EMP-9090",
                    "full_name": "Demo Import",
                    "email": "demo.import@northwind.example.com",
                    "phone": "+923001111111",
                    "department": "Finance",
                    "role_title": "Finance Analyst",
                    "approved_context_summary": "Imported approved context for finance workflow.",
                    "consent_status": "consented",
                }
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["created"] == 1
    assert payload["errors"] == []


def test_import_reports_invalid_rows_without_rejecting_the_file(client, admin_headers):
    response = client.post(
        "/api/v1/employees/import",
        headers=admin_headers,
        json={
            "rows": [
                {
                    "employee_id": "EMP-9191",
                    "full_name": "Valid Import",
                    "email": "valid.import@northwind.example.com",
                    "department": "Finance",
                    "role_title": "Finance Analyst",
                },
                {
                    "employee_id": "EMP-9192",
                    "full_name": "Broken Import",
                    "email": "not-an-email",
                    "department": "Finance",
                    "role_title": "Finance Analyst",
                },
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["created"] == 1
    assert len(payload["errors"]) == 1
    assert payload["errors"][0]["row"] == 2
    assert "email" in payload["errors"][0]["error"]
