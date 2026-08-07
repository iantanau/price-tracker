"""Notification payload value object."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationPayload:
    """Data-only payload delivered by a notifier.

    This object contains no sending logic; notifiers decide how to format
    and deliver the payload through their specific channel.

    Attributes:
        subject: Short summary line.
        body: Detailed message body.
        recipient: Optional override recipient; notifiers fall back to settings.
    """

    subject: str
    body: str
    recipient: str | None = None
