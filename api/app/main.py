from typing import Any, Literal

from fastapi import FastAPI
from starlette.types import Receive, Scope, Send

from app.config import Settings
from app.routes.runs import router as runs_router
from app.routes.webhooks import mock_router
from app.routes.webhooks import router as webhooks_router
from app.services.runs import InMemoryRunStore, RunService, SQLiteRunStore


def create_app(
    run_service: RunService | None = None,
    webhook_secret: str | None = None,
    db_path: str | None = None,
    stub_mode: Literal["pass", "fail"] = "pass",
) -> FastAPI:
    application = FastAPI(title="cicd-agent", version="0.0.0")

    if run_service is not None:
        application.state.run_service = run_service
    elif db_path is not None:
        application.state.run_service = RunService(SQLiteRunStore(db_path), stub_mode=stub_mode)
    else:
        application.state.run_service = RunService(InMemoryRunStore(), stub_mode=stub_mode)
    if webhook_secret is not None:
        application.state.webhook_secret = webhook_secret
    else:
        secret = Settings().github_webhook_secret
        application.state.webhook_secret = secret.get_secret_value() if secret is not None else None

    @application.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(webhooks_router)
    application.include_router(runs_router)
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
