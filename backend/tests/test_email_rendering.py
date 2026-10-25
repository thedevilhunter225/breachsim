from types import SimpleNamespace

from app.services.email_rendering import render_campaign_email


def _render(cta_text):
    employee = SimpleNamespace(full_name="Quinn Tester", department=SimpleNamespace(name="Finance"))
    organization = SimpleNamespace(name="Northwind")
    return render_campaign_email(
        employee=employee,
        organization=organization,
        branding_snapshot={},
        scenario_snapshot={"subject": "Review", "body_copy": "Hi {{first_name}}", "cta_text": cta_text},
        landing_url="https://training.example.com/l/token",
        qr_image_url=None,
    )


def test_internal_cta_marker_is_never_shown_to_recipients():
    rendered = _render("clickhere")
    assert "clickhere" not in rendered.html_body.lower()
    assert "clickhere" not in rendered.text_body.lower()
    assert "Review securely" in rendered.html_body


def test_custom_cta_text_is_kept():
    assert "Open the reconciliation" in _render("Open the reconciliation").html_body
