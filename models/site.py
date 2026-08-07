"""Site value object."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Site:
    """Configuration for a retail website.

    Keeping site metadata in a dedicated value object lets Product remain
    focused on the product itself while still supporting per-site behaviour
    (headers, base URL) in the future.

    Attributes:
        name: Human-readable site name, e.g. ``JB Hi-Fi``.
        base_url: Optional root URL for the site.
        default_headers: Optional headers to use for requests to this site.
    """

    name: str
    base_url: str | None = None
    default_headers: dict[str, str] | None = None
