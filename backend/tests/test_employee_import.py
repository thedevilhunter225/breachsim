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
