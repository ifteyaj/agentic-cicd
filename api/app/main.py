from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="cicd-agent", version="0.0.0")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
