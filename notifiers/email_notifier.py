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
        try:
            value = f"{price.value:,.2f}"
        except (TypeError, ValueError):
            value = str(price.value)
        return f"{price.currency} {value}"

    @staticmethod
    def _item_currency(item) -> str:
        """Return the best available currency code for an item."""
        if item.best_price is not None:
            return item.best_price.currency
        for listing in item.listings:
            if listing.price is not None:
                return listing.price.currency
        return "AUD"

    def _render_text(self, payload: NotificationPayload) -> str:
        """Render a plain-text body for the notification batch."""
        if not payload.items:
            return payload.subject

        lines = []
        for item in payload.items:
            lines.append(item.name)
            if item.best_price is not None:
                lines.append(f"  Best price: {self._format_price(item.best_price)}")
            if item.target_price is not None:
                currency = self._item_currency(item)
                lines.append(f"  Target: {currency} {item.target_price:,.2f}")
            for listing in item.listings:
                price = self._format_price(listing.price)
                lowest = (
                    listing.price is not None
                    and item.best_price is not None
                    and listing.price == item.best_price
                )
                line = f"  - {listing.site_name}: {price}"
                if lowest:
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
                lowest = (
                    listing.price is not None
                    and item.best_price is not None
                    and listing.price == item.best_price
                )
                site = html.escape(listing.site_name)
                if lowest:
                    site = f"✓ {site}"
                price_html = html.escape(price)
                if lowest:
                    price_html = f"<strong>{price_html}</strong>"
                url = html.escape(listing.url)
                rows.append(
                    f"<tr><td>{site}</td><td>{price_html}</td>"
                    f"<td><a href=\"{url}\">View</a></td></tr>"
                )

            summary = ""
            if item.best_price is not None:
                summary += (
                    "Best price: "
                    f"<strong>{html.escape(self._format_price(item.best_price))}</strong><br>"
                )
            if item.target_price is not None:
                currency = self._item_currency(item)
                summary += f"Target: {currency} {item.target_price:,.2f}<br>"

            reason = ""
            if item.trigger == "target":
                reason = "At or below target price"
            elif item.trigger == "new_low":
                reason = "New all-time low"
            reason_html = f"<p><em>{html.escape(reason)}</em></p>" if reason else ""

            blocks.append(
                f"<h3>{html.escape(item.name)}</h3>"
                f"<p>{summary}</p>"
                f"{reason_html}"
                '<table border="0" cellpadding="4" cellspacing="0">'
                '<tr><th align="left">Retailer</th><th align="left">Price</th><th></th></tr>'
                + "".join(rows)
                + "</table>"
            )
        return "".join(blocks)
