from app.db.mysql_db import mysql_db
from app.core.logger import logger


class CarSearch:

    async def get_available_inventory(self, date_iso: str, date_end_iso: str = None) -> list[dict]:
        """
        Fetch full car details available for the given date range.
        Overlap: fromDate < requested_end AND toDate > requested_start
        """
        start_date = date_iso
        end_date   = date_end_iso if date_end_iso else date_iso
        logger.info(f"Fetching inventory for {start_date} → {end_date}")

        query = """
                SELECT
                    id,
                    seating_capacity,
                    info8 AS transmission_type,
                    info5 AS fuel_type,
                    info7 AS body_type,
                    info4 AS Doors,
                    carMake,
                    carModel
                FROM cars
                WHERE status = 2
                AND seating_capacity IN (5, 7)
                AND carMake  IS NOT NULL AND carMake  != ''
                AND carModel IS NOT NULL AND carModel != ''
                AND id NOT IN (
                    SELECT DISTINCT carId
                    FROM rental_car_booking
                    WHERE status IN (0, 1, 7, 3)
                    AND fromDate < STR_TO_DATE(%s, '%%Y-%%m-%%d')
                    AND toDate   > STR_TO_DATE(%s, '%%Y-%%m-%%d')
                )
            """
     
        try:
            async with mysql_db.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, (end_date, start_date))
                    rows = await cursor.fetchall()

            inventory = []
            for row in rows:
                make  = (row.get("carMake")  or "").strip()
                model = (row.get("carModel") or "").strip()
                if not make or not model or make.lower() == "none" or model.lower() == "none":
                    continue
                inventory.append({
                    "id":               row["id"],
                    "seatingCapacity":  int(row["seating_capacity"]),
                    "transmissionType": row["transmission_type"],
                    "fuelType":         row["fuel_type"],
                    "bodyType":         row.get("body_type", ""),   
                    "doors":            row.get("doors", ""),        
                    "carMake":          make,
                    "carModel":         model,
                })
            logger.info(inventory)

            return inventory

        except Exception as e:
            logger.error(f"Inventory fetch error: {e}")
            return []


car_search = CarSearch()    