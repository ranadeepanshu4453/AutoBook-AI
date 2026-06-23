from app.db.mysql_db import mysql_db
from app.core.logger import logger
from app.core.exceptions import InventoryFetchException
import os
import jwt
import httpx
from datetime import datetime, timedelta, timezone
from app.core.context import get_acc_num


# BACKEND_API = "https://a1.starr365.com/book/rental/getProfileDetail.php?ttt=1&counter=&insuranceId=undefined&roadinsuranceId=undefined&carNum=0043&bookId=0&staffNum=1860&booking_type_r=2&staffId=103175&from_date=2026-06-17T06:45&to_date=T&profile_id=&applyUnlimited=undefined&btype=&booking_type=undefined"
# CREATE_NEW_STAFF_API = "https://a1.starr365.com/book/rental/feature-ajax.php"

# ── Config ────────────────────────────────────────────────────────────────────
 
SECRET_KEY  = os.getenv("SECRET_KEY")
ALGORITHM   = "HS256"
PHP_API_URL = os.getenv("PHP_PAYMENT_API_URL", "https://copier-sequel-gestation.ngrok-free.dev/api/v1/payment/test-url")
 
 
# ── JWT helper ────────────────────────────────────────────────────────────────
 
def _generate_service_token() -> str:
    payload = {
        "iss": "autobook-chatbot",
        "aud": "booking-service",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

class CarSearch:

    async def get_available_inventory(self, date_iso: str, date_end_iso: str = None) -> list[dict]:
        """
        Fetch full car details available for the given date range.
        Overlap: fromDate < requested_end AND toDate > requested_start
        """
        acc_num = get_acc_num()
        start_date = date_iso
        end_date   = date_end_iso if date_end_iso else date_iso
        logger.info(
            f"Fetching inventory "
            f"accNum={acc_num} "
            f"{start_date} -> {end_date}"
        )

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
                WHERE acNum = %s 
                AND status = 2
                AND seating_capacity IN (5, 7)
                AND carMake  IS NOT NULL AND carMake  != ''
                AND carModel IS NOT NULL AND carModel != ''
                AND id NOT IN (
                    SELECT DISTINCT carId
                    FROM rental_car_booking
                    WHERE accnum = %s and status IN (0, 1, 7, 3)
                    AND fromDate < STR_TO_DATE(%s, '%%Y-%%m-%%d')
                    AND toDate   > STR_TO_DATE(%s, '%%Y-%%m-%%d')
                )
            """
     
        try:
            async with mysql_db.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, (acc_num,acc_num,end_date, start_date))
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
            raise InventoryFetchException(
                f"Inventory fetch failed: {e}", code="INV_003"
            )

    async def get_active_bookings(self, session_id: str = None) -> list[dict]:
        """
        Fetch cars with currently active/upcoming bookings.
        status 1,2 = confirmed/ongoing; toDate in future or unset = still active.
        """
        acc_num = get_acc_num()
        query = """
            SELECT
                c.id,
                c.seating_capacity,
                c.info8 AS transmission_type,
                c.info5 AS fuel_type,
                c.info7 AS body_type,
                c.info4 AS doors,
                c.carMake,
                c.carModel,
                b.fromDate,
                b.toDate,
                b.status AS booking_status
            FROM cars c
            INNER JOIN rental_car_booking b ON b.carId = c.id
            WHERE c.acNum=%s and b.accnum=%s and b.status IN (1, 2)
            AND (b.toDate > NOW() OR b.toDate IS NULL OR b.toDate = '')
        """

        try:
            async with mysql_db.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query,(acc_num,acc_num))
                    rows = await cursor.fetchall()

            bookings = []
            for row in rows:
                make  = (row.get("carMake")  or "").strip()
                model = (row.get("carModel") or "").strip()
                if not make or not model or make.lower() == "none" or model.lower() == "none":
                    continue

                raw_seating = row.get("seating_capacity")
                try:
                    seating = int(raw_seating)
                except (ValueError, TypeError):
                    seating = None

                bookings.append({
                    "id":               row["id"],
                    "seatingCapacity":  seating,
                    "transmissionType": row["transmission_type"],
                    "fuelType":         row["fuel_type"],
                    "bodyType":         row.get("body_type", ""),
                    "doors":            row.get("doors", ""),
                    "carMake":          make,
                    "carModel":         model,
                    "fromDate":         str(row.get("fromDate", "")),
                    "toDate":           str(row.get("toDate", "")) if row.get("toDate") else "Ongoing",
                    "bookingStatus":    row.get("booking_status"),
                })

            logger.info(f"Active bookings fetch returned {len(bookings)} rows")
            return bookings

        except Exception as e:
            logger.error(f"Active bookings fetch error: {e}")
            raise InventoryFetchException(
                f"Active bookings fetch failed: {e}", code="INV_003"
            )

 # ── Staff → PHP API ───────────────────────────────────────────────────────
 
    async def send_staff_to_php(self, entities: dict, session_id: str) -> dict:
        """
        POST all collected staff data to PHP backend.
        PHP handles staff lookup/creation and returns a payment link.
 
        Expected keys in entities:
            phone, full_name, email, licence_number, licence_expiry
 
        Returns parsed JSON response from PHP.
        Raises InventoryFetchException on any failure.
        """
        token = _generate_service_token()
 
        payload = {
            "accNum":         get_acc_num(),
            # Staff Details
            "name":           entities.get("full_name", ""),
            "email":          entities.get("email", ""),
            "phone":          entities.get("phone", ""),
            "licence_number": entities.get("licence_number", ""),
            "licence_expiry": entities.get("licence_expiry", ""),
            # Car Details
            "car_id":         entities.get("selected_car_id", ""),
            "car_name":       entities.get("selected_car_name", ""),
            "Start_date":     entities.get("booking_date_iso", ""),
            "end_date":       entities.get("booking_date_end", ""),
            #Extra
            'btype':          16                    #Periodic payment
        }
 
        logger.info(f"[{session_id}] Sending staff & Booking data to PHP API: {payload}")
        logger.info(f"All Entities: {entities}")
 
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    PHP_API_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )
 
            if not response.is_success:
                logger.error(f"[{session_id}] PHP API error {response.status_code}: {response.text}")
                raise InventoryFetchException(
                    f"PHP API returned {response.status_code}: {response.text}",
                    code="INV_005",
                )
 
            data = response.json()
            logger.info(f"[{session_id}] PHP API response: {data}")
            return data
 
        except InventoryFetchException:
            raise
        except Exception as e:
            logger.error(f"[{session_id}] PHP API request failed: {e}")
            raise InventoryFetchException(
                f"PHP API unreachable: {e}", code="INV_005"
            )
            
car_search = CarSearch()    