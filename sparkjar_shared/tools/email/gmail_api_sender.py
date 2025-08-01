"""Gmail API sender tool with proper Google Cloud authentication.

Uses Google Cloud service account credentials for secure email delivery.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend import supabase_helper as sh

class GmailAPISender:
    """Gmail API email sender with service account authentication."""

    def __init__(self, client_id: str):
        """Initialize with client-specific credentials."""
        self.client_id = client_id
        self.service = None
        self._initialize_service()

    def _initialize_service(self):
        """Initialize Gmail API service with credentials."""
        try:
            # Fetch Google Cloud service account credentials from client_secrets
            creds_rows = sh.select_many(
                "client_secrets",
                {
                    "client_id": self.client_id,
                    "secret_key": "googleapis.service_account",
                },
            )

            if not creds_rows:
                raise ValueError(
                    f"No Google service account credentials found for client {self.client_id}"
                )

            # Get service account info from metadata field (JSON stored there)
            service_account_info = creds_rows[0]["metadata"]

            # Get admin email from secret_value field for user impersonation
            admin_email = creds_rows[0]["secret_value"]

            # Create credentials object with domain-wide delegation
            # Expanded scopes for full Google Workspace integration
            scopes = [
                "https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/documents",
                "https://www.googleapis.com/auth/calendar.events",
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/presentations",
                "https://www.googleapis.com/auth/contacts",
                "https://www.googleapis.com/auth/userinfo.profile",
                "https://www.googleapis.com/auth/userinfo.email",
            ]

            credentials = service_account.Credentials.from_service_account_info(
                service_account_info, scopes=scopes
            )

            # For Gmail API, we need to impersonate a user (domain-wide delegation)
            # Note: This requires the service account to have domain-wide delegation
            # enabled in Google Workspace Admin Console
            delegated_credentials = credentials.with_subject(admin_email)

            # Build Gmail API service
            self.service = build("gmail", "v1", credentials=delegated_credentials)

        except Exception as e:
            sh.log_open_item(f"Failed to initialize Gmail API service: {e}")
            raise

    def create_message(
        self,
        sender: str,
        to: str,
        subject: str,
        message_text: str,
        message_html: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Create a message for an email.

        Args:
            sender: Sender email address
            to: Recipient email address
            subject: Email subject
            message_text: Plain text content
            message_html: Optional HTML content
            attachments: Optional list of attachments with format:
                [{"filename": "report.txt", "content": "text content", "content_type": "text/plain"}]
        """
        if message_html or attachments:
            # Create multipart message for HTML + text + attachments
            message = MIMEMultipart("mixed")
            message["to"] = to
            message["from"] = sender
            message["subject"] = subject

            # Create content part (text/html)
            if message_html:
                content_part = MIMEMultipart("alternative")
                text_part = MIMEText(message_text, "plain")
                html_part = MIMEText(message_html, "html")
                content_part.attach(text_part)
                content_part.attach(html_part)
                message.attach(content_part)
            else:
                text_part = MIMEText(message_text, "plain")
                message.attach(text_part)

            # Add attachments
            if attachments:
                for attachment in attachments:
                    filename = attachment.get("filename", "attachment.txt")
                    content = attachment.get("content", "")
                    content_type = attachment.get("content_type", "text/plain")

                    # Create attachment part
                    attachment_part = MIMEBase(*content_type.split("/"))
                    attachment_part.set_payload(content.encode("utf-8"))
                    encoders.encode_base64(attachment_part)
                    attachment_part.add_header(
                        "Content-Disposition", f"attachment; filename= {filename}"
                    )
                    message.attach(attachment_part)
        else:
            # Create simple text message
            message = MIMEText(message_text)
            message["to"] = to
            message["from"] = sender
            message["subject"] = subject

        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return {"raw": raw_message}

    def send_message(
        self,
        sender: str,
        to: str,
        subject: str,
        message_text: str,
        message_html: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Send an email message.

        Args:
            sender: Sender email address
            to: Recipient email address
            subject: Email subject
            message_text: Plain text content
            message_html: Optional HTML content
            attachments: Optional list of attachments
        """
        try:
            # Create message
            message = self.create_message(
                sender, to, subject, message_text, message_html, attachments
            )

            # Send message
            result = (
                self.service.users()
                .messages()
                .send(userId="me", body=message)
                .execute()
            )

            sh.log_open_item(
                f"Gmail API: Email sent successfully to {to}, message ID: {result.get('id')}"
            )
            return {
                "status": "sent",
                "message_id": result.get("id"),
                "thread_id": result.get("threadId"),
            }

        except HttpError as error:
            sh.log_open_item(f"Gmail API HTTP error: {error}")
            return {"status": "failed", "error": str(error)}
        except Exception as error:
            sh.log_open_item(f"Gmail API error: {error}")
            return {"status": "failed", "error": str(error)}

    async def send_message_async(
        self,
        sender: str,
        to: str,
        subject: str,
        message_text: str,
        message_html: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Asynchronously send an email message."""
        return await asyncio.to_thread(
            self.send_message,
            sender,
            to,
            subject,
            message_text,
            message_html,
            attachments,
        )

    async def send_email_async(self, package: str, *, job_id: str) -> str:
        """Send email asynchronously (compatible with existing EmailSender interface)."""
        try:
            data = json.loads(package or "{}")
        except json.JSONDecodeError:
            data = {}

        recipient = data.get("recipient")
        sender = data.get(
            "sender", "noreply@yourcompany.com"
        )  # Use your verified domain
        subject = data.get("subject", "Research Report")
        message_text = data.get("markdown", "")
        message_html = data.get("html")  # Optional HTML version

        if not recipient:
            sh.log_open_item(f"No recipient specified for job {job_id}")
            return "email_failed"

        try:
            result = self.send_message(
                sender, recipient, subject, message_text, message_html
            )

            if result["status"] == "sent":
                # Update job status
                try:
                    await sh.update("jobs", {"id": job_id}, {"status": "email_sent"})
                except Exception:
                    pass
                return "email_sent"
            else:
                # Update job status with failure
                try:
                    await sh.update("jobs", {"id": job_id}, {"status": "email_failed"})
                except Exception:
                    pass
                return "email_failed"

        except Exception as e:
            sh.log_open_item(f"Failed to send email for job {job_id}: {e}")
            try:
                await sh.update("jobs", {"id": job_id}, {"status": "email_failed"})
            except Exception:
                pass
            return "email_failed"

def setup_google_cloud_credentials(client_id: str, service_account_json: str) -> bool:
    """
    Helper function to store Google Cloud service account credentials in client_secrets table.

    Args:
        client_id: The client UUID
        service_account_json: JSON string of service account credentials

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Validate JSON format
        json.loads(service_account_json)

        # Store in client_secrets table
        sh.upsert_row(
            "client_secrets",
            {
                "client_id": client_id,
                "secret_key": "google_service_account",
                "secret_value": service_account_json,
            },
        )

        sh.log_open_item(
            f"Google Cloud service account credentials stored for client {client_id}"
        )
        return True

    except Exception as e:
        sh.log_open_item(f"Failed to store Google Cloud credentials: {e}")
        return False

def setup_gmail_oauth_credentials(client_id: str, oauth_credentials_json: str) -> bool:
    """
    Helper function to store Gmail OAuth2 credentials in client_secrets table.

    Args:
        client_id: The client UUID
        oauth_credentials_json: JSON string of OAuth2 credentials

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Validate JSON format
        json.loads(oauth_credentials_json)

        # Store in client_secrets table
        sh.upsert_row(
            "client_secrets",
            {
                "client_id": client_id,
                "secret_key": "gmail_oauth",
                "secret_value": oauth_credentials_json,
            },
        )

        sh.log_open_item(f"Gmail OAuth2 credentials stored for client {client_id}")
        return True

    except Exception as e:
        sh.log_open_item(f"Failed to store Gmail OAuth credentials: {e}")
        return False
