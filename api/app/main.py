from fastapi import FastAPI

from app.config import Settings
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
    return application


app = create_app()
