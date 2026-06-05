import logging
import sys

# Use a named logger instead of basicConfig to avoid infinite reload loops
# basicConfig configures the root logger globally, which causes uvicorn's
# file watcher to detect log file changes and trigger endless reloads.

logger = logging.getLogger("AI_Car_Booking_Chatbot")
logger.setLevel(logging.INFO)

# Avoid adding duplicate handlers if module is re-imported
if not logger.handlers:
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler("app.log")
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

# Prevent log records from bubbling up to the root logger
logger.propagate = False