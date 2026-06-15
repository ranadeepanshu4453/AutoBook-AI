from fastapi import APIRouter
from app.api.v1.endpoints import intent, whatsapp, feedback

router = APIRouter()

router.include_router(intent.router,    prefix="/intent",    tags=["Intent"])
router.include_router(whatsapp.router,  prefix="/whatsapp",  tags=["WhatsApp"])
router.include_router(feedback.router)  # prefix="/feedback" already set in the router itself