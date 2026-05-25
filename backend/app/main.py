from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.courses import router as courses_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Fasikül API")
    yield
    logger.info("Shutting down")


app = FastAPI(title="Fasikül Üretici API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(courses_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
