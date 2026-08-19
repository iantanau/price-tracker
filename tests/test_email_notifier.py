"""Tests for EmailNotifier message construction and delivery."""

from decimal import Decimal
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from config.settings import Settings
from models.notification_payload import NotificationItem, NotificationPayload
from models.price import Price
from notifiers.base import NotifierError
from notifiers.email_notifier import EmailNotifier


class TestEmailNotifier:
    """Tests for the SMTP email notifier."""

    def _settings(self, **overrides) -> Settings:
        """Create settings with sensible defaults for tests."""
        defaults = {
            "smtp_host": "smtp.test.local",
            "smtp_port": 587,
            "smtp_security": "STARTTLS",
            "smtp_username": "alerts@test.local",
            "smtp_password": "secret",
            "smtp_from": "alerts@test.local",
            "smtp_to": "user@test.local",
        }
        defaults.update(overrides)
        return Settings(**defaults)

    def _item(self, **overrides) -> NotificationItem:
        """Create a single notification item."""
        defaults = {
            "product_id": "p001",
            "name": "Example Product",
            "url": "https://example.com/p/1",
            "price": Price(value=Decimal("49.95"), currency="AUD"),
            "target_price": Decimal("39.99"),
        }
        defaults.update(overrides)
        return NotificationItem(**defaults)

    def _payload(self, **overrides) -> NotificationPayload:
        """Create a notification payload."""
        defaults = {
            "subject": "Price alert: Example Product",
            "items": (self._item(),),
        }
        defaults.update(overrides)
        return NotificationPayload(**defaults)

    @patch("notifiers.email_notifier.smtplib.SMTP")
    def test_sends_email_with_starttls(self, mock_smtp_class) -> None:
        """Builds and sends an email using STARTTLS transport."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        notifier = EmailNotifier(self._settings())
        notifier.send(self._payload())

        mock_smtp_class.assert_called_once_with("smtp.test.local", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("alerts@test.local", "secret")
        mock_server.send_message.assert_called_once()

        message = mock_server.send_message.call_args[0][0]
        assert isinstance(message, EmailMessage)
        assert message["Subject"] == "Price alert: Example Product"
        assert message["From"] == "alerts@test.local"
        assert message["To"] == "user@test.local"

        text = message.get_body(preferencelist=("plain",)).get_content().strip()
        assert "Example Product: 49.95 AUD" in text
        assert "https://example.com/p/1" in text

        html = message.get_body(preferencelist=("html",)).get_content()
        assert "Example Product" in html
        assert "https://example.com/p/1" in html

    @patch("notifiers.email_notifier.smtplib.SMTP")
    def test_renders_multiple_items(self, mock_smtp_class) -> None:
        """Renders every item in a multi-product notification."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        payload = self._payload(
            subject="Price alert: 2 products",
            items=(
                self._item(name="First", product_id="p001"),
                self._item(
                    name="Second",
                    product_id="p002",
                    url="https://example.com/p/2",
                ),
            ),
        )
        notifier = EmailNotifier(self._settings())
        notifier.send(payload)

        message = mock_server.send_message.call_args[0][0]
        text = message.get_body(preferencelist=("plain",)).get_content().strip()
        assert "First: 49.95 AUD" in text
        assert "Second: 49.95 AUD" in text
        assert "https://example.com/p/2" in text

    @patch("notifiers.email_notifier.smtplib.SMTP_SSL")
    def test_sends_email_with_ssl(self, mock_smtp_ssl_class) -> None:
        """Builds and sends an email using SSL transport."""
        mock_server = MagicMock()
        mock_smtp_ssl_class.return_value.__enter__.return_value = mock_server

        notifier = EmailNotifier(
            self._settings(smtp_port=465, smtp_security="SSL")
        )
        notifier.send(self._payload())

        mock_smtp_ssl_class.assert_called_once_with("smtp.test.local", 465)
        mock_server.starttls.assert_not_called()
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()

    @patch("notifiers.email_notifier.smtplib.SMTP")
    def test_sends_email_without_security(self, mock_smtp_class) -> None:
        """Builds and sends an email without TLS."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        notifier = EmailNotifier(self._settings(smtp_security="NONE"))
        notifier.send(self._payload())

        mock_server.starttls.assert_not_called()
        mock_server.send_message.assert_called_once()

    @patch("notifiers.email_notifier.smtplib.SMTP")
    def test_parses_multiple_recipients(self, mock_smtp_class) -> None:
        """Sends to all recipients in a comma-separated list."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        notifier = EmailNotifier(
            self._settings(smtp_to="one@test.local, two@test.local, three@test.local")
        )
        notifier.send(self._payload())

        message = mock_server.send_message.call_args[0][0]
        assert message["To"] == "one@test.local, two@test.local, three@test.local"

    def test_raises_when_no_recipients_configured(self) -> None:
        """Raises NotifierError when there are no recipients."""
        notifier = EmailNotifier(self._settings(smtp_to=""))

        with pytest.raises(NotifierError, match="No recipients configured"):
            notifier.send(self._payload())

    def test_raises_when_no_sender_configured(self) -> None:
        """Raises NotifierError when there is no sender address."""
        notifier = EmailNotifier(self._settings(smtp_from=""))

        with pytest.raises(NotifierError, match="No sender configured"):
            notifier.send(self._payload())

    @patch("notifiers.email_notifier.smtplib.SMTP")
    def test_wraps_smtp_errors_in_notifier_error(self, mock_smtp_class) -> None:
        """Wraps SMTP failures in NotifierError."""
        import smtplib

        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server
        mock_server.send_message.side_effect = smtplib.SMTPException("SMTP failure")

        notifier = EmailNotifier(self._settings())

        with pytest.raises(NotifierError, match="Failed to send email"):
            notifier.send(self._payload())

    def test_payload_recipient_overrides_settings(self) -> None:
        """Uses the payload recipient when one is provided."""
        notifier = EmailNotifier(self._settings())
        payload = self._payload(recipient="override@test.local")

        recipients = notifier._parse_recipients(payload)

        assert recipients == ["override@test.local"]
