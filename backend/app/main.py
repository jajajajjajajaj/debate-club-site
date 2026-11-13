from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.routers import auth, debates, members, reservations

app = FastAPI(title="Debate Club API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allowed_origins(),
    allow_credentials=False,  # 쿠키를 쓰지 않고 Authorization 헤더만 씁니다.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(members.router, prefix="/members", tags=["members"])
app.include_router(debates.router, prefix="/debates", tags=["debates"])
app.include_router(reservations.router, prefix="/reservations", tags=["reservations"])
