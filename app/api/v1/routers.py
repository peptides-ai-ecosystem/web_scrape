# XR-14 owner (HTTP API used by platform and peptide) — see orchestrator/docs/ecosystem/dependencies.md#xr-14
from fastapi import APIRouter, Depends

from app.api.gateway_auth import require_gateway_token
from app.api.v1.endpoints import (
    core,
    csv_inspector,
    evaluation,
    graph,
    operations,
    scheduler,
    sync,
    vendors,
)

api_router = APIRouter(dependencies=[Depends(require_gateway_token)])

api_router.include_router(sync.router, prefix="/sync", tags=["Syncing"])
api_router.include_router(evaluation.router, prefix="/evaluation", tags=["Evaluation"])
api_router.include_router(graph.router, tags=["Graph"])
api_router.include_router(operations.router, prefix="/operations", tags=["Operations"])
api_router.include_router(scheduler.router, prefix="/scheduler", tags=["Scheduler"])
api_router.include_router(core.router, prefix="/core", tags=["Core Data"])
api_router.include_router(csv_inspector.router, prefix="/csv", tags=["CSV Inspector"])
api_router.include_router(vendors.router, prefix="/vendors", tags=["Vendor Pricing"])
