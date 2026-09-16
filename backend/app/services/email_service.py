import logging
import httpx
from app.config import get_settings

log = logging.getLogger(__name__)

_BRAND = "#dc2626"
_BG = "#0a0a0a"
_SURFACE = "#111111"
_FG = "#f5f5f5"
_MUTED = "#71717a"
_BORDER = "#27272a"


def _base_template(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background:{_BG};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:{_BG};padding:40px 16px;">
    <tr><td align="center">
      <table width="100%" style="max-width:520px;" cellpadding="0" cellspacing="0">

        <!-- Logo -->
        <tr><td style="padding-bottom:28px;text-align:center;">
          <span style="font-size:11px;font-weight:900;letter-spacing:0.2em;text-transform:uppercase;color:{_BRAND};">manga-dl</span>
        </td></tr>

        <!-- Card -->
        <tr><td style="background:{_SURFACE};border:1px solid {_BORDER};border-radius:16px;padding:36px 32px;">
          {body_html}
        </td></tr>

        <!-- Footer -->
        <tr><td style="padding-top:24px;text-align:center;">
          <p style="margin:0;font-size:11px;color:{_MUTED};">manga-dl &middot; Your manga, everywhere.</p>
          <p style="margin:6px 0 0;font-size:11px;color:{_MUTED};">You received this because you have a manga-dl account.</p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def welcome_email(username: str | None = None) -> tuple[str, str]:
    """Returns (subject, html) for the welcome / username confirmation email."""
    username_block = ""
    if username:
        username_block = f"""
        <tr><td style="padding:16px;background:rgba(220,38,38,0.08);border:1px solid rgba(220,38,38,0.2);border-radius:10px;margin-top:20px;">
          <p style="margin:0;font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:0.1em;color:{_MUTED};">Your username</p>
          <p style="margin:6px 0 0;font-size:20px;font-weight:800;color:{_FG};font-family:monospace;">@{username}</p>
          <p style="margin:6px 0 0;font-size:12px;color:{_MUTED};">This cannot be changed — keep it safe.</p>
        </td></tr>
        <tr><td style="height:20px;"></td></tr>"""

    body = f"""
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr><td>
            <p style="margin:0 0 6px;font-size:10px;font-weight:900;letter-spacing:0.15em;text-transform:uppercase;color:{_BRAND};">Welcome</p>
            <h1 style="margin:0 0 12px;font-size:24px;font-weight:800;color:{_FG};line-height:1.2;">You're in.</h1>
            <p style="margin:0 0 24px;font-size:13px;color:{_MUTED};line-height:1.7;">
              Your manga-dl account is ready. Search across 50+ sources, build your library, and read anywhere — on web, desktop, or Android.
            </p>
          </td></tr>
          {username_block}
          <tr><td>
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
              <tr>
                <td style="width:33%;padding:12px 8px;text-align:center;background:rgba(255,255,255,0.03);border:1px solid {_BORDER};border-radius:10px;">
                  <p style="margin:0;font-size:11px;font-weight:700;color:{_FG};">Library</p>
                  <p style="margin:4px 0 0;font-size:10px;color:{_MUTED};">Cloud + local</p>
                </td>
                <td style="width:4px;"></td>
                <td style="width:33%;padding:12px 8px;text-align:center;background:rgba(255,255,255,0.03);border:1px solid {_BORDER};border-radius:10px;">
                  <p style="margin:0;font-size:11px;font-weight:700;color:{_FG};">50+ sources</p>
                  <p style="margin:4px 0 0;font-size:10px;color:{_MUTED};">All in one place</p>
                </td>
                <td style="width:4px;"></td>
                <td style="width:33%;padding:12px 8px;text-align:center;background:rgba(255,255,255,0.03);border:1px solid {_BORDER};border-radius:10px;">
                  <p style="margin:0;font-size:11px;font-weight:700;color:{_FG};">3 devices</p>
                  <p style="margin:4px 0 0;font-size:10px;color:{_MUTED};">Sync anywhere</p>
                </td>
              </tr>
            </table>
          </td></tr>
          <tr><td style="text-align:center;">
            <a href="https://manga-dl.web.app" style="display:inline-block;padding:12px 32px;background:{_BRAND};color:#fff;font-size:13px;font-weight:800;text-decoration:none;border-radius:10px;letter-spacing:0.05em;">
              Open manga-dl
            </a>
          </td></tr>
        </table>"""

    subject = "Welcome to manga-dl" + (f" — @{username}" if username else "")
    return subject, _base_template("Welcome to manga-dl", body)


def support_ticket_email(ticket_id: int, name: str, email: str | None, category: str, message: str) -> tuple[str, str]:
    """Returns (subject, html) for a support ticket notification."""
    from_user = name + (f" &lt;{_esc(email)}&gt;" if email else "")
    body = f"""
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr><td>
            <p style="margin:0 0 6px;font-size:10px;font-weight:900;letter-spacing:0.15em;text-transform:uppercase;color:{_BRAND};">Support Ticket #{ticket_id}</p>
            <h1 style="margin:0 0 20px;font-size:22px;font-weight:800;color:{_FG};">New {_esc(category.title())} ticket</h1>
          </td></tr>
          <tr><td style="padding-bottom:8px;">
            <p style="margin:0;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:{_MUTED};">From</p>
            <p style="margin:4px 0 0;font-size:13px;color:{_FG};">{from_user}</p>
          </td></tr>
          <tr><td style="padding-bottom:16px;">
            <p style="margin:0;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:{_MUTED};">Message</p>
            <div style="margin-top:8px;padding:14px 16px;background:rgba(255,255,255,0.03);border-left:3px solid {_BRAND};border-radius:0 8px 8px 0;">
              <p style="margin:0;font-size:13px;color:{_FG};line-height:1.7;">{_esc(message).replace(chr(10), '<br>')}</p>
            </div>
          </td></tr>
          <tr><td>
            <p style="margin:0;font-size:11px;color:{_MUTED};">View in Supabase Table Editor &rarr; support_tickets</p>
          </td></tr>
        </table>"""

    subject = f"[{category.title()}] New support ticket #{ticket_id}"
    return subject, _base_template(f"Ticket #{ticket_id}", body)


def _esc(text: str) -> str:
    return (text
        .replace("&", "&amp;").replace("<", "&lt;")
        .replace(">", "&gt;").replace('"', "&quot;")
        .replace("'", "&#x27;"))


async def send_email(to: str, subject: str, html: str) -> bool:
    settings = get_settings()
    if not settings.RESEND_API_KEY:
        log.debug("Resend not configured — skipping email to %s", to)
        return False
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={"from": settings.RESEND_FROM_EMAIL, "to": [to], "subject": subject, "html": html},
                timeout=10,
            )
            if r.status_code not in (200, 201):
                log.warning("Resend returned %s: %s", r.status_code, r.text[:200])
                return False
            return True
    except Exception as e:
        log.warning("Resend send failed: %s", e)
        return False
