from typing import Any

from fastapi import FastAPI
from starlette.types import Receive, Scope, Send

from app.config import Settings
from app.routes.webhooks import mock_router
from app.routes.webhooks import router as webhooks_router
from app.services.runs import InMemoryRunStore, RunService


def create_app(run_service: RunService | None = None, webhook_secret: str | None = None) -> FastAPI:
    application = FastAPI(title="cicd-agent", version="0.0.0")

    application.state.run_service = (
        run_service if run_service is not None else RunService(InMemoryRunStore())
    )
    if webhook_secret is not None:
        application.state.webhook_secret = webhook_secret
    else:
        secret = Settings().github_webhook_secret
        application.state.webhook_secret = secret.get_secret_value() if secret is not None else None

    @application.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(webhooks_router)
    if Settings().env == "dev":
        application.include_router(mock_router)
    return application


_env_apps: dict[str, FastAPI] = {}


def _app_for_current_env() -> FastAPI:
    env = Settings().env
    if env not in _env_apps:
        _env_apps[env] = create_app()
    return _env_apps[env]


class _EnvironmentAwareApp:
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> Any:
        await _app_for_current_env()(scope, receive, send)

    def __getattr__(self, name: str) -> Any:
        return getattr(_app_for_current_env(), name)


app = _EnvironmentAwareApp()
