"""Email sender tool (stub).

Listens for `send_email` events and logs a placeholder message.
"""

from __future__ import annotations

import json

import smtplib
from email.message import EmailMessage
from crewai.flow import listen

from backend import supabase_helper as sh

class EmailSender:
    """Flow step that stubs out Gmail email sending."""

    @listen("send_email")
    async def send_email(
        self,
        package: str,
        *,
        job_id: str,
        client_id: str,
    ) -> str:
        """Parse package, log email and mark job complete."""
        try:
            data = json.loads(package or "{}")
        except json.JSONDecodeError:
            data = {}

        recipient = data.get("recipient")

        creds = sh.select_many(
            "client_secrets", {"client_id": client_id, "secret_key": "gmail"}
        )
        password = creds[0]["secret_value"] if creds else None

        status = "email_sent_stub"
        if recipient and password:
            msg = EmailMessage()
            msg["Subject"] = data.get("subject", "Research Report")
            msg["From"] = data.get("sender", "noreply@example.com")
            msg["To"] = recipient
            msg.set_content(data.get("markdown", ""))
            try:
                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                    smtp.login(data.get("sender"), password)
                    smtp.send_message(msg)
                status = "email_sent"
            except Exception as exc:  # pragma: no cover - network
                sh.log_open_item(f"email error: {exc}")
                status = "email_failed"
        else:
            sh.log_open_item(f"send_email to {recipient} using {bool(password)}")

        try:
            await sh.update("jobs", {"id": job_id}, {"status": status})
        except Exception:
            pass

        return status
