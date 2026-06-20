from fastapi import APIRouter

from src.api.v1.endpoints import scraping, sync, evaluation, graph

api_router = APIRouter()

api_router.include_router(scraping.router, prefix="/scraping", tags=["Scraping"])
api_router.include_router(sync.router, prefix="/sync", tags=["Syncing"])
api_router.include_router(evaluation.router, prefix="/evaluation", tags=["Evaluation"])
api_router.include_router(graph.router, tags=["Graph"])
