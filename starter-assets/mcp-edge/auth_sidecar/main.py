"""Internal nginx auth_request target: Bearer == MCP_BEARER_TOKEN -> 204, else 401."""

import os

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route


def _expected() -> str:
    token = os.environ.get("MCP_BEARER_TOKEN", "").strip()
    if not token:
        raise RuntimeError("MCP_BEARER_TOKEN is required")
    return token


async def health(_: Request) -> Response:
    return JSONResponse({"status": "healthy", "service": "auth_sidecar"})


async def verify(request: Request) -> Response:
    expected = _expected()
    auth = (request.headers.get("authorization") or "").strip()
    if auth == f"Bearer {expected}":
        return Response(status_code=204)
    return JSONResponse(
        {"error": "unauthorized", "detail": "Missing or invalid Bearer token"},
        status_code=401,
    )


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/verify", verify, methods=["GET", "HEAD"]),
    ],
)
