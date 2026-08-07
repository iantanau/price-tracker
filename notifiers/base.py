"""Notifier abstraction."""

from abc import ABC, abstractmethod

from models.notification_payload import NotificationPayload


class Notifier(ABC):
    """Abstract channel for delivering messages.

    Phase 1 sends price alerts via email. Future implementations can send
    daily reports, weekly summaries, or deal recommendations through channels
    such as Telegram, Discord, Slack, or ServerChan.
    """

    @abstractmethod
    def send(self, payload: NotificationPayload) -> None:
        """Deliver the given notification payload.

        Args:
            payload: Data-only message to deliver.

        Raises:
            NotifierError: If delivery fails.
        """
        raise NotImplementedError


class NotifierError(Exception):
    """Raised when a notifier fails to deliver a message."""

    pass
