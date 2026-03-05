import requests
import logging
from CTFd.models import db
from ..models.config import ContainerConfig

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.webhook_url = None

    def _get_webhook_url(self):
        return ContainerConfig.get('container_discord_webhook_url', '')

    # -------------------------------------------------------------------------
    # WaSender helpers
    # -------------------------------------------------------------------------

    def _get_wa_config(self):
        """Return (api_key, group_id, image_url, audio_url) from ContainerConfig."""
        return (
            ContainerConfig.get('wasender_api_key', ''),
            ContainerConfig.get('wasender_group_id', ''),
            ContainerConfig.get('wasender_image_url', ''),
            ContainerConfig.get('wasender_audio_url', ''),
        )

    def _build_wa_text(self, title, message, fields=None):
        """Convert Discord embed-style data to plain WhatsApp text."""
        lines = [f"*{title}*", message]
        if fields:
            lines.append("")
            for f in fields:
                lines.append(f"*{f['name']}:* {f['value']}")
        return "\n".join(lines)

    def _send_whatsapp(self, text, api_key=None, group_id=None,
                       image_url=None, audio_url=None):
        """
        Send text (+ optional image/audio) to a WhatsApp group via WaSender.

        If api_key/group_id are not provided, they are read from ContainerConfig.
        Returns True if at least the text message was sent successfully.
        """
        _api_key, _group_id, _img_url, _aud_url = self._get_wa_config()

        api_key   = api_key   or _api_key
        group_id  = group_id  or _group_id
        image_url = image_url if image_url is not None else _img_url
        audio_url = audio_url if audio_url is not None else _aud_url

        if not api_key or not group_id:
            return False

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        base_url = "https://api.wasenderapi.com/api/send-message"

        try:
            # Message payload — include imageUrl if we have one
            payload = {"to": group_id, "text": text}
            if image_url:
                payload["imageUrl"] = image_url

            resp = requests.post(base_url, json=payload, headers=headers, timeout=10)
            success = resp.status_code == 200

            # Send audio as a separate POST (WaSender does not support caption+audio)
            if audio_url:
                audio_payload = {"to": group_id, "audioUrl": audio_url}
                requests.post(base_url, json=audio_payload, headers=headers, timeout=10)

            return success
        except Exception as e:
            logger.error(f"Failed to send WaSender notification: {e}")
            return False

    def upload_media(self, file_bytes, mime_type,
                     api_key=None):
        """
        Upload raw bytes to WaSender CDN via Base64 JSON body.

        Returns the publicUrl string on success, raises RuntimeError on failure.
        """
        _api_key, _, _, _ = self._get_wa_config()
        api_key = api_key or _api_key

        if not api_key:
            raise RuntimeError("WaSender API key is not configured")

        import base64
        b64 = base64.b64encode(file_bytes).decode()
        data_uri = f"data:{mime_type};base64,{b64}"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            "https://api.wasenderapi.com/api/upload",
            json={"base64": data_uri},
            headers=headers,
            timeout=30,
        )

        if resp.status_code != 200:
            raise RuntimeError(
                f"WaSender upload failed ({resp.status_code}): {resp.text}"
            )

        body = resp.json()
        if not body.get("success"):
            raise RuntimeError(f"WaSender upload error: {body}")

        return body["publicUrl"]

    def send_wa_test(self, api_key=None, group_id=None):
        """Send a plain-text test message to the WhatsApp group."""
        return self._send_whatsapp(
            "✅ *WaSender Connection Test*\nYour WhatsApp integration is configured correctly!",
            api_key=api_key,
            group_id=group_id,
            image_url="",
            audio_url="",
        )

    # -------------------------------------------------------------------------
    # Discord helpers
    # -------------------------------------------------------------------------

    def send_alert(self, title, message, color=0xff0000, fields=None):
        """
        Send an alert to Discord and WaSender.

        Args:
            title: Embed title
            message: Embed description
            color: Hex color integer (default red)
            fields: List of dicts {'name': str, 'value': str, 'inline': bool}
        """
        webhook_url = self._get_webhook_url()
        discord_ok = False
        if webhook_url:
            try:
                payload = {
                    "embeds": [{
                        "title": title,
                        "description": message,
                        "color": color,
                        "fields": fields or []
                    }]
                }
                response = requests.post(webhook_url, json=payload, timeout=5)
                discord_ok = response.status_code == 204
            except Exception as e:
                logger.error(f"Failed to send Discord notification: {e}")

        # Fire WaSender (fire-and-forget, don't let it block/fail the caller)
        try:
            wa_text = self._build_wa_text(title, message, fields)
            self._send_whatsapp(wa_text)
        except Exception as e:
            logger.error(f"WaSender alert failed: {e}")

        return discord_ok

    def notify_cheat(self, user, challenge, flag, owner):
        """Send cheat detection alert"""
        fields = [
            {"name": "User", "value": user.name if user else "Unknown", "inline": True},
            {"name": "Challenge", "value": challenge.name if challenge else "Unknown", "inline": True},
            {"name": "Flag Submitted", "value": f"`{flag}`", "inline": False},
            {"name": "Original Owner", "value": owner.name if owner else "Unknown", "inline": True},
            {"name": "Action Taken", "value": "User & Owner Banned", "inline": False}
        ]
        
        return self.send_alert(
            title="🚨 Cheating Detected!",
            message="A user submitted a flag belonging to another team/user.",
            color=0xff0000, # Red
            fields=fields
        )

    def notify_error(self, operation, error_msg):
        """Send system error alert"""
        fields = [
            {"name": "Operation", "value": operation, "inline": True},
            {"name": "Error", "value": f"```{error_msg}```", "inline": False}
        ]
        
        return self.send_alert(
            title="⚠️ Container Plugin Error",
            message="An error occurred in the container system.",
            color=0xffa500, # Orange
            fields=fields
        )

    def send_test(self, webhook_url=None):
        """Send a simple test message"""
        url_to_use = webhook_url or self._get_webhook_url()
        return self._send_raw(
            url_to_use,
            title="✅ Connection Test",
            message="Your Discord Webhook is configured correctly!",
            color=0x00ff00 # Green
        )

    def send_demo_cheat(self, webhook_url=None):
        """Send a demo cheat alert (Discord only)"""
        url_to_use = webhook_url or self._get_webhook_url()
        fields = [
            {"name": "User", "value": "demo_hacker", "inline": True},
            {"name": "Challenge", "value": "Demo Challenge", "inline": True},
            {"name": "Flag Submitted", "value": "`CTF{demo_flag_hash}`", "inline": False},
            {"name": "Original Owner", "value": "innocent_victim", "inline": True},
            {"name": "Action Taken", "value": "User & Owner Banned", "inline": False}
        ]
        return self._send_raw(
            url_to_use,
            title="🚨 Cheating Detected! (DEMO)",
            message="This is a DEMO alert. No actual banning occurred.",
            color=0xff0000, # Red
            fields=fields
        )

    def send_demo_error(self, webhook_url=None):
        """Send a demo error alert (Discord only)"""
        url_to_use = webhook_url or self._get_webhook_url()
        fields = [
            {"name": "Operation", "value": "Container Provisioning", "inline": True},
            {"name": "Error", "value": "```DockerException: Connection refused```", "inline": False}
        ]
        return self._send_raw(
            url_to_use,
            title="⚠️ Plugin Error (DEMO)",
            message="This is a DEMO alert.",
            color=0xffa500, # Orange
            fields=fields
        )

    def send_wa_demo_cheat(self, api_key=None, group_id=None):
        """Send a demo cheat alert to WhatsApp."""
        fields = [
            {"name": "User", "value": "demo_hacker"},
            {"name": "Challenge", "value": "Demo Challenge"},
            {"name": "Flag Submitted", "value": "CTF{demo_flag_hash}"},
            {"name": "Original Owner", "value": "innocent_victim"},
            {"name": "Action Taken", "value": "User & Owner Banned"},
        ]
        text = self._build_wa_text(
            "🚨 Cheating Detected! (DEMO)",
            "This is a DEMO alert. No actual banning occurred.",
            fields,
        )
        return self._send_whatsapp(text, api_key=api_key, group_id=group_id,
                                   image_url="", audio_url="")

    def send_wa_demo_error(self, api_key=None, group_id=None):
        """Send a demo error alert to WhatsApp."""
        fields = [
            {"name": "Operation", "value": "Container Provisioning"},
            {"name": "Error", "value": "DockerException: Connection refused"},
        ]
        text = self._build_wa_text(
            "⚠️ Plugin Error (DEMO)",
            "This is a DEMO alert.",
            fields,
        )
        return self._send_whatsapp(text, api_key=api_key, group_id=group_id,
                                   image_url="", audio_url="")

    def _send_raw(self, url, title, message, color, fields=None):
        """Internal method to send to a specific Discord URL"""
        if not url:
            return False
        
        try:
            payload = {
                "embeds": [{
                    "title": title,
                    "description": message,
                    "color": color,
                    "fields": fields or []
                }]
            }
            response = requests.post(url, json=payload, timeout=5)
            return response.status_code == 204
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False
