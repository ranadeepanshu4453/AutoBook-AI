from app.db.mysql_db import mysql_db
from app.core.logger import logger


class CarService:

    async def search_available_cars(self, entities: dict):
        if not mysql_db.pool:
            await mysql_db.connect()

        async with mysql_db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """
                    SELECT id, carMake, carModel, seating_capacity,
                           info8 AS transmission, info5 AS fuel
                    FROM cars
                """
                params = []

                if "seating_capacity" in entities:
                    sql += " AND seating_capacity = %s"
                    params.append(entities["seating_capacity"])

                if "transmission_type" in entities:
                    trans_val = "1" if entities["transmission_type"] == "automatic" else "2"
                    sql += " AND info8 = %s"
                    params.append(trans_val)

                if "fuel_type" in entities:
                    sql += " AND info5 LIKE %s"
                    params.append(f"%{entities['fuel_type']}%")

                # Exclude cars already booked for the requested dates
                if "booking_date_iso" in entities:
                    end_date = entities.get("booking_date_end", entities["booking_date_iso"])
                    sql += """
                        AND id NOT IN (
                            SELECT DISTINCT carId
                            FROM rental_car_booking
                            WHERE status IN (1, 2)
                            AND fromDate < STR_TO_DATE(%s, '%%Y-%%m-%%d')
                            AND toDate   > STR_TO_DATE(%s, '%%Y-%%m-%%d')
                        )
                    """
                    params.append(end_date)
                    params.append(entities["booking_date_iso"])

                logger.info(f"Executing search: {sql} | Params: {params}")
                await cur.execute(sql, tuple(params))
                return await cur.fetchall()

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
                    "carMake":          make,
                    "carModel":         model,
                })
            logger.info(inventory)

            return inventory

        except Exception as e:
            logger.error(f"Inventory fetch error: {e}")
            return []


car_service = CarService()