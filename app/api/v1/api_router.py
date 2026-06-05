from fastapi import APIRouter
from app.api.v1.controllers import intent_controller

router = APIRouter()

# We will add more routes here (search, tasks, etc.) later
router.include_router(intent_controller.router, prefix="/intent", tags=["Intent Detection"])