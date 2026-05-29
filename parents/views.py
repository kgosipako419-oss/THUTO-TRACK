"""WhatsApp webhook (Twilio-compatible).

Configure Twilio's WhatsApp sandbox / sender to POST to:
    https://<your-host>/whatsapp/webhook/

Set ``WHATSAPP_AUTH_TOKEN`` in the environment to your Twilio auth token to
enable request signature validation. When unset, validation is skipped — fine
for local development but DO NOT deploy to production without it.
"""

import base64
import hmac
from hashlib import sha1
from xml.sax.saxutils import escape

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from core.whatsapp import handle_inbound


def _twilio_signature_valid(request) -> bool:
    """Validate Twilio's X-Twilio-Signature header.

    Per Twilio's docs: HMAC-SHA1 of (full_url + sorted_post_params), keyed with
    the account auth token, base64-encoded.
    """
    token = getattr(settings, "WHATSAPP_AUTH_TOKEN", "") or ""
    if not token:
        return True  # validation disabled
    sent = request.headers.get("X-Twilio-Signature", "")
    if not sent:
        return False
    url = request.build_absolute_uri(request.path)
    params = sorted(request.POST.items())
    payload = url + "".join(f"{k}{v}" for k, v in params)
    digest = hmac.new(token.encode("utf-8"), payload.encode("utf-8"), sha1).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, sent)


def _twiml(text: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<Response><Message>{escape(text)}</Message></Response>"
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    if request.method == "GET":
        # Twilio sometimes pings with GET on save; respond clearly.
        return HttpResponse(
            "ThutoTrack WhatsApp webhook is live. POST a message here.",
            content_type="text/plain",
        )

    if not _twilio_signature_valid(request):
        return HttpResponseForbidden("Invalid signature")

    from_field = request.POST.get("From", "")
    body = request.POST.get("Body", "")
    phone = from_field.replace("whatsapp:", "").strip()

    reply = handle_inbound(phone, body)
    return HttpResponse(_twiml(reply), content_type="application/xml; charset=utf-8")
