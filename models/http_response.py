"""HTTP response value object."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HttpResponse:
    """Normalised HTTP response returned by the client abstraction.

    Returning a dedicated value object instead of a plain string keeps the
    door open for monitors and parsers to react to status codes or headers
    in the future without changing the HttpClient interface.

    Attributes:
        content: Response body as a string.
        status_code: HTTP status code.
        headers: Response headers.
    """

    content: str
    status_code: int
    headers: dict[str, str]
