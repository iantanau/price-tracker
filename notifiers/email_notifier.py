"""SMTP email notifier implementation."""

import html
import smtplib
from email.message import EmailMessage

from config.settings import Settings
from models.notification_payload import NotificationPayload
from models.price import Price
from notifiers.base import Notifier, NotifierError


class EmailNotifier(Notifier):
    """Send notification payloads via SMTP.

    All SMTP settings are read from :class:`Settings` so no provider-specific
    configuration (Gmail, Outlook, etc.) is hard-coded.

    Attributes:
        _settings: SMTP configuration.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialise the notifier with SMTP settings.

        Args:
            settings: Must contain smtp_host, smtp_port, smtp_security,
                smtp_username, smtp_password, smtp_from, and smtp_to.
        """
        self._settings = settings

    def send(self, payload: NotificationPayload) -> None:
        """Send the payload as an email.

        Args:
            payload: Notification to deliver.

        Raises:
            NotifierError: If SMTP settings are missing or delivery fails.
        """
        recipients = self._parse_recipients(payload)
        if not recipients:
            raise NotifierError("No recipients configured for email notification")

        sender = payload.recipient or self._settings.smtp_from
        if not sender:
            raise NotifierError("No sender configured for email notification")

        message = EmailMessage()
        message["Subject"] = payload.subject
        message["From"] = sender
        message["To"] = ", ".join(recipients)

        message.set_content(self._render_text(payload))
        message.add_alternative(self._render_html(payload), subtype="html")

        try:
            self._send_message(message)
        except smtplib.SMTPException as exc:
            raise NotifierError(f"Failed to send email: {exc}") from exc

    def _send_message(self, message: EmailMessage) -> None:
        """Open the SMTP transport selected by settings and send the message.

        Transport security is controlled by ``smtp_security``; credentials are
        used only for authentication and never to decide whether to encrypt.
        """
        security = self._settings.smtp_security
        host = self._settings.smtp_host
        port = self._settings.smtp_port

        server_factory = smtplib.SMTP_SSL if security == "SSL" else smtplib.SMTP

        with server_factory(host, port) as server:
            if security == "STARTTLS":
                server.starttls()
            if self._settings.smtp_username and self._settings.smtp_password:
                server.login(self._settings.smtp_username, self._settings.smtp_password)
            server.send_message(message)

    def _parse_recipients(self, payload: NotificationPayload) -> list[str]:
        """Return the list of recipient addresses.

        The payload recipient takes precedence; otherwise the comma-separated
        ``smtp_to`` setting is used.
        """
        raw = payload.recipient or self._settings.smtp_to
        if not raw:
            return []
        return [addr.strip() for addr in raw.split(",") if addr.strip()]

    def _format_price(self, price: Price | None) -> str:
        """Format a price value object for display."""
        if price is None:
            return "unknown price"
        return f"{price.value} {price.currency}"

    def _render_text(self, payload: NotificationPayload) -> str:
        """Render a plain-text body for the notification batch."""
        if not payload.items:
            return payload.subject

        lines = []
        for item in payload.items:
            lines.append(item.name)
            if item.target_price is not None:
                lines.append(f"  Target: {item.target_price}")
            for listing in item.listings:
                price = self._format_price(listing.price)
                line = f"  {listing.site_name}: {price}"
                if (
                    listing.price is not None
                    and item.best_price is not None
                    and listing.price == item.best_price
                ):
                    line += " (lowest)"
                lines.append(line)
                lines.append(f"    {listing.url}")
            if item.trigger == "target":
                lines.append("  Reason: at or below target price")
            elif item.trigger == "new_low":
                lines.append("  Reason: new all-time low")
            lines.append("")
        return "\n".join(lines)

    def _render_html(self, payload: NotificationPayload) -> str:
        """Render an HTML body for the notification batch."""
        if not payload.items:
            return f"<p>{html.escape(payload.subject)}</p>"

        blocks = []
        for item in payload.items:
            rows = []
            for listing in item.listings:
                price = self._format_price(listing.price)
                raw = f"{listing.site_name} - {price}"
                if (
                    listing.price is not None
                    and item.best_price is not None
                    and listing.price == item.best_price
                ):
                    raw += " (lowest)"
                url = html.escape(listing.url)
                rows.append(
                    f"<li>{html.escape(raw)}<br><a href=\"{url}\">{url}</a></li>"
                )

            reason = ""
            if item.trigger == "target":
                reason = " - at or below target"
            elif item.trigger == "new_low":
                reason = " - new all-time low"

            blocks.append(
                f"<p><strong>{html.escape(item.name)}</strong>{reason}</p>"
                "<ul>" + "".join(rows) + "</ul>"
            )
        return "".join(blocks)
