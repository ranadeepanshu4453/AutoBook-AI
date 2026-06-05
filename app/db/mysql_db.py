import aiomysql
import os
from app.core.logger import logger

db_config = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "db": os.getenv("MYSQL_DATABASE"), # aiomysql uses 'db' instead of 'database'
    "autocommit": True,
    "cursorclass": aiomysql.DictCursor
}

class MySQLDB:
    def __init__(self):
        self.pool = None

    async def connect(self):
        try:
            self.pool = await aiomysql.create_pool(**db_config)
            logger.info("Connected to MySQL Pool")
        except Exception as e:
            logger.error(f"MySQL Connection Failed: {e}")

    async def close(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()

mysql_db = MySQLDB()