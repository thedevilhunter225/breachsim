from __future__ import annotations

from dataclasses import dataclass
from html import escape


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    text_body: str
    html_body: str


def personalize_locally(value: str, *, employee, organization) -> str:
    first_name = employee.full_name.split()[0] if employee.full_name.split() else "Colleague"
    department = employee.department.name if employee.department else "your department"
    replacements = {
        "{{first_name}}": first_name,
        "{{full_name}}": employee.full_name,
        "{{company_name}}": organization.name,
        "{{department}}": department,
    }
    rendered = value
    for placeholder, local_value in replacements.items():
        rendered = rendered.replace(placeholder, local_value)
    return rendered


def render_campaign_email(
    *,
    employee,
    organization,
    branding_snapshot: dict,
    scenario_snapshot: dict,
    landing_url: str,
    qr_image_url: str | None,
) -> RenderedEmail:
    subject = personalize_locally(scenario_snapshot["subject"], employee=employee, organization=organization)
    body = personalize_locally(scenario_snapshot["body_copy"], employee=employee, organization=organization)
    cta_text = personalize_locally(
        scenario_snapshot.get("cta_text") or "Review securely",
        employee=employee,
        organization=organization,
    )
    first_name = employee.full_name.split()[0] if employee.full_name.split() else "Colleague"

    primary = branding_snapshot.get("primary_color", "#173B73")
    accent = branding_snapshot.get("accent_color", "#175CD3")
    sender_name = branding_snapshot.get("sender_name") or organization.name
    legal_footer = branding_snapshot.get("legal_footer") or "Authorized security-awareness simulation."
    logo_url = branding_snapshot.get("logo_url")
    logo = (
        f'<img src="{escape(str(logo_url), quote=True)}" width="150" alt="{escape(sender_name)}" '
        'style="display:block;max-width:150px;height:auto;margin:0 auto 14px;">'
        if logo_url
        else ""
    )

    if qr_image_url:
        action_html = f"""
          <p style="margin:0 0 18px;font-weight:600;">Scan the QR code below with your phone camera to continue.</p>
          <div style="margin:0 0 24px;">
            <img src="{escape(qr_image_url, quote=True)}" width="360" height="360" alt="QR code for this training request"
                 style="display:block;width:360px;max-width:100%;height:auto;border:1px solid #d8dde5;background:#fff;padding:12px;">
          </div>
        """
        text_action = "Scan the QR code displayed in the HTML version of this message."
    else:
        action_html = f"""
          <p style="margin:26px 0;">
            <a href="{escape(landing_url, quote=True)}"
               style="display:inline-block;background:{accent};color:#fff;padding:12px 20px;border-radius:6px;text-decoration:none;font-weight:700;">{escape(cta_text)}</a>
          </p>
        """
        text_action = f"{cta_text}: {landing_url}"

    html = f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f4f6f8;color:#202124;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f4f6f8;">
      <tr><td align="center" style="padding:32px 12px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
               style="max-width:680px;background:#fff;border:1px solid #dfe3e8;border-radius:8px;">
          <tr><td style="padding:30px 38px 18px;text-align:center;border-bottom:1px solid #edf0f2;">
            {logo}
            <div style="font-size:12px;letter-spacing:1.3px;text-transform:uppercase;color:#667085;">{escape(sender_name)}</div>
            <h1 style="margin:10px 0 0;font-size:25px;line-height:34px;color:{primary};">{escape(subject)}</h1>
          </td></tr>
          <tr><td style="padding:30px 38px 36px;font-size:16px;line-height:25px;">
            <p style="margin:0 0 22px;">Dear {escape(first_name)},</p>
            <p style="margin:0 0 24px;">{escape(body).replace(chr(10), '<br>')}</p>
            {action_html}
            <p style="margin:24px 0 0;font-size:13px;line-height:20px;color:#667085;">
              If images or buttons are blocked, use this link:<br>
              <a href="{escape(landing_url, quote=True)}" style="color:{accent};word-break:break-all;">{escape(landing_url)}</a>
            </p>
          </td></tr>
          <tr><td style="padding:18px 38px;background:#f8fafc;border-top:1px solid #edf0f2;font-size:12px;line-height:19px;color:#667085;">
            {escape(legal_footer)}
          </td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""
    text = f"Dear {first_name},\n\n{body}\n\n{text_action}\n\nFallback link: {landing_url}\n\n{legal_footer}"
    return RenderedEmail(subject=subject, text_body=text, html_body=html)
