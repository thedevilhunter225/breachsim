# Controlled email and QR tracking check — 6 October 2026

This is a synthetic local verification. It does not claim a message was delivered to
an external mailbox or a phone. No employee data or credentials were used.

| Observation | Result | Evidence |
| --- | --- | --- |
| Reopening one email recipient link | Exactly one `clicked_link` event; repeated visits remain idempotent | `test_email_link_tracking_records_one_click_without_claiming_an_open` |
| Email open status | No open event is inferred from link visits | Same test checks `OPENED_EMAIL` remains absent |
| Fetching a QR image through a mail image proxy | No `scanned_qr` event | `test_remote_qr_asset_decodes_and_only_destination_open_records_scan` |
| Opening the URL encoded in the QR | Exactly one scan event; repeated visits remain idempotent | Same QR test |
| Training-page behavior | A categorical choice is accepted without email, password, code, or arbitrary metadata | `test_public_event_privacy.py` and `training-simulator.test.tsx` |

The email tracking experiment is complete locally for link clicks and QR scans. The
platform does not claim reliable email opens: a mail client or image proxy can fetch
remote images without a human reading the message. A real Google Workspace pilot
still requires a verified sender domain, delegated sender mailbox, approved recipient
inbox and a public HTTPS landing hostname. Record provider acceptance, known bounce,
link/QR interaction, and the received message rendering separately in that pilot.
