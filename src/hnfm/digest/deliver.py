"""Emailing a digest to a Send-to-Kindle address.

HTTP-API providers only, keyed from the environment — no SMTP, no personal
mailbox credentials. Adding a provider means one function and one entry in
`_PROVIDERS`; nothing above this module knows which one is in use.

Send to Kindle rules that shape this, and that fail *silently* when broken —
Amazon accepts the mail and simply never delivers the book, so there is no
bounce to debug:

  * The From address must be on the Approved Personal Document E-mail List in
    your Amazon account. This is the usual reason a correct-looking send never
    arrives, so `send_digest` refuses to run without DIGEST_FROM_EMAIL set
    rather than letting a provider default address fail quietly.
  * The destination must be the @kindle.com address, not your Amazon login.
  * EPUB, PDF, DOC/DOCX, TXT and HTML are accepted; MOBI/AZW3 no longer are.
  * 50 MB per message, before base64 expansion.
"""

import base64
import logging
import os
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# Amazon's documented ceiling. Enforced before the request because a provider
# rejects an oversize payload with an opaque error, if it reports one at all.
MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024

_MIME = {
    ".epub": "application/epub+zip",
    ".html": "text/html",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}


class DeliveryError(RuntimeError):
    """The digest was not accepted for delivery."""


def _send_resend(
    api_key: str, sender: str, to: str, subject: str, body: str,
    filename: str, payload: bytes, content_type: str,
) -> str:
    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        json={
            "from": sender,
            "to": [to],
            "subject": subject,
            "text": body,
            "attachments": [{
                "filename": filename,
                "content": base64.b64encode(payload).decode(),
                "content_type": content_type,
            }],
        },
        timeout=120,
    )
    if r.status_code >= 300:
        raise DeliveryError(f"resend {r.status_code}: {r.text[:300]}")
    return (r.json() or {}).get("id", "")


def _send_postmark(
    api_key: str, sender: str, to: str, subject: str, body: str,
    filename: str, payload: bytes, content_type: str,
) -> str:
    r = requests.post(
        "https://api.postmarkapp.com/email",
        headers={"X-Postmark-Server-Token": api_key,
                 "Accept": "application/json",
                 "Content-Type": "application/json"},
        json={
            "From": sender,
            "To": to,
            "Subject": subject,
            "TextBody": body,
            "Attachments": [{
                "Name": filename,
                "Content": base64.b64encode(payload).decode(),
                "ContentType": content_type,
            }],
        },
        timeout=120,
    )
    if r.status_code >= 300:
        raise DeliveryError(f"postmark {r.status_code}: {r.text[:300]}")
    return str((r.json() or {}).get("MessageID", ""))


def _send_mailgun(
    api_key: str, sender: str, to: str, subject: str, body: str,
    filename: str, payload: bytes, content_type: str,
) -> str:
    domain = os.getenv("MAILGUN_DOMAIN", "").strip()
    if not domain:
        raise DeliveryError("MAILGUN_DOMAIN is required for the mailgun provider")
    r = requests.post(
        f"https://api.mailgun.net/v3/{domain}/messages",
        auth=("api", api_key),
        data={"from": sender, "to": to, "subject": subject, "text": body},
        files=[("attachment", (filename, payload, content_type))],
        timeout=120,
    )
    if r.status_code >= 300:
        raise DeliveryError(f"mailgun {r.status_code}: {r.text[:300]}")
    return (r.json() or {}).get("id", "")


def _send_brevo(
    api_key: str, sender: str, to: str, subject: str, body: str,
    filename: str, payload: bytes, content_type: str,
) -> str:
    r = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={"api-key": api_key, "accept": "application/json",
                 "content-type": "application/json"},
        json={
            "sender": {"email": sender},
            "to": [{"email": to}],
            "subject": subject,
            "textContent": body,
            # Brevo takes attachments as base64 under `content`.
            "attachment": [{
                "name": filename,
                "content": base64.b64encode(payload).decode(),
            }],
        },
        timeout=120,
    )
    if r.status_code >= 300:
        raise DeliveryError(f"brevo {r.status_code}: {r.text[:300]}")
    return (r.json() or {}).get("messageId", "")


def _send_mailjet(
    api_key: str, sender: str, to: str, subject: str, body: str,
    filename: str, payload: bytes, content_type: str,
) -> str:
    secret = os.getenv("MAILJET_SECRET_KEY", "").strip()
    if not secret:
        raise DeliveryError("MAILJET_SECRET_KEY is required for the mailjet provider")
    r = requests.post(
        "https://api.mailjet.com/v3.1/send",
        auth=(api_key, secret),
        json={"Messages": [{
            "From": {"Email": sender},
            "To": [{"Email": to}],
            "Subject": subject,
            "TextPart": body,
            "Attachments": [{
                "ContentType": content_type,
                "Filename": filename,
                "Base64Content": base64.b64encode(payload).decode(),
            }],
        }]},
        timeout=120,
    )
    if r.status_code >= 300:
        raise DeliveryError(f"mailjet {r.status_code}: {r.text[:300]}")
    msgs = (r.json() or {}).get("Messages") or [{}]
    return str((msgs[0].get("To") or [{}])[0].get("MessageID", ""))


# brevo first: it is the only entry here that needs neither a credit card nor a
# domain you own — it verifies a single sender address, which is what Amazon's
# approved-sender list wants anyway.
_PROVIDERS = {
    "brevo": ("BREVO_API_KEY", _send_brevo),
    "mailjet": ("MAILJET_API_KEY", _send_mailjet),
    "resend": ("RESEND_API_KEY", _send_resend),
    "postmark": ("POSTMARK_API_KEY", _send_postmark),
    "mailgun": ("MAILGUN_API_KEY", _send_mailgun),
}


def delivery_config() -> Tuple[bool, str]:
    """(ready, reason) — whether a send could succeed, without sending.

    Lets the UI and /api/services/status show a configuration problem before
    someone waits for a book that was never going to arrive.
    """
    provider = os.getenv("EMAIL_PROVIDER", "resend").strip().lower()
    if provider not in _PROVIDERS:
        return False, f"EMAIL_PROVIDER={provider!r} is not one of {sorted(_PROVIDERS)}"
    key_env, _fn = _PROVIDERS[provider]
    if not os.getenv(key_env):
        return False, f"{key_env} is not set"
    if not os.getenv("DIGEST_FROM_EMAIL"):
        return False, "DIGEST_FROM_EMAIL is not set (must be Amazon-approved)"
    if not os.getenv("KINDLE_EMAIL"):
        return False, "KINDLE_EMAIL is not set"
    return True, f"{provider} → {os.getenv('KINDLE_EMAIL')}"


def send_digest(
    file_path: str,
    subject: Optional[str] = None,
    to: Optional[str] = None,
) -> str:
    """Email `file_path` to the Kindle address. Returns the provider message id."""
    ready, reason = delivery_config()
    if not ready:
        raise DeliveryError(f"email delivery is not configured: {reason}")

    provider = os.getenv("EMAIL_PROVIDER", "resend").strip().lower()
    key_env, fn = _PROVIDERS[provider]
    destination = to or os.getenv("KINDLE_EMAIL")
    sender = os.getenv("DIGEST_FROM_EMAIL")

    with open(file_path, "rb") as f:
        payload = f.read()
    if len(payload) > MAX_ATTACHMENT_BYTES:
        raise DeliveryError(
            f"{file_path} is {len(payload)} bytes, over Send to Kindle's 50 MB limit"
        )

    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()
    content_type = _MIME.get(ext, "application/octet-stream")

    # Amazon takes the document title from the filename, and largely ignores
    # the body — so the subject is what shows up while it converts.
    message_id = fn(
        os.getenv(key_env), sender, destination,
        subject or os.path.splitext(filename)[0],
        "Sent by hn.fm.", filename, payload, content_type,
    )
    logger.info(
        f"digest: sent {filename} ({len(payload)} bytes) to {destination} "
        f"via {provider} (id={message_id})"
    )
    return message_id
