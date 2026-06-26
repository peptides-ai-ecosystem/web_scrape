from fastapi import APIRouter

from src.api.v1.endpoints import sync, evaluation, graph, operations, scheduler

api_router = APIRouter()

api_router.include_router(sync.router, prefix="/sync", tags=["Syncing"])
api_router.include_router(evaluation.router, prefix="/evaluation", tags=["Evaluation"])
api_router.include_router(graph.router, tags=["Graph"])
api_router.include_router(operations.router, prefix="/operations", tags=["Operations"])
api_router.include_router(scheduler.router, prefix="/scheduler", tags=["Scheduler"])
