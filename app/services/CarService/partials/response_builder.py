from app.enums.intent_enums import IntentType
from app.enums.stage_enums import BookingStages
from app.models.intent_models import IntentResponse

TRANS_DISPLAY = {"1": "Automatic", "2": "Manual", "automatic": "Automatic", "manual": "Manual"}
FUEL_DISPLAY = {
    "p": "Petrol",    "petrol": "Petrol",
    "d": "Diesel",    "diesel": "Diesel",
    "b": "Hybrid",    "hybrid": "Hybrid",
    "e": "Electric",  "electric": "Electric",
    "h": "Hydrogen",  "hydrogen": "Hydrogen",
}

def _display_trans(val: str) -> str:
    return TRANS_DISPLAY.get(str(val).lower(), val.capitalize())


def _display_fuel(val: str) -> str:
    if not val:
        return ""
    return FUEL_DISPLAY.get(str(val).lower(), str(val).capitalize())


def car_options_message(inventory: list[dict], booking_dates: str) -> str:
    available_seating = sorted({int(c["seatingCapacity"]) for c in inventory})
    
    if len(available_seating) > 1:
        opts = " and ".join(f"{s}-Seater" for s in available_seating)
        seating_note = f"We have both {opts} options available. "
    else:
        seating_note = ""

    return (
        f"Here are the cars available for {booking_dates}. "
        f"{seating_note}"
        f"Would you like any of these, or shall I filter by seating, transmission, or fuel type?"
    )
    
def booking_status_message(bookings: list[dict]) -> str:
    if not bookings:
        return "You don't have any active bookings right now."

    lines = [f"You have {len(bookings)} active booking(s):\n"]
    for b in bookings:
        car_name = f"{b['carMake']} {b['carModel']}"
        dates = f"{b['fromDate']} → {b['toDate']}"
        lines.append(f"• {car_name} ({dates})")

    return "\n".join(lines)


def filtered_options_message(inventory: list[dict], filters: dict) -> str:
    if not inventory:
        return "No cars match those filters. Would you like to adjust your preferences?"

    filter_summary = []
    if "seating_capacity" in filters:
        filter_summary.append(f"{filters['seating_capacity']}-Seater")
    if "transmission_type" in filters:
        filter_summary.append(_display_trans(filters["transmission_type"]))
    if "fuel_type" in filters:
        filter_summary.append(_display_fuel(filters["fuel_type"]))

    summary = ", ".join(filter_summary) if filter_summary else "your preferences"

    return (
        f"Here are the {summary} options. "
        f"Which one would you like to book?"
    )

def seating_question(available_seating: list[int]) -> str:
    opts = " or ".join(f"{s}-Seater" for s in sorted(available_seating))
    return f"Would you prefer a {opts}?"


def transmission_question(available: list[str]) -> str:
    # normalize before display
    opts = " or ".join(_display_trans(t) for t in available if t)
    return f"Would you prefer {opts} transmission?"


def fuel_question(available: list[str]) -> str:
    opts = " or ".join(_display_fuel(f) for f in available)
    return f"Would you prefer {opts} fuel?"


def format_cars_for_display(inventory: list[dict]) -> list[dict]:
    """
    Clean, frontend-friendly car list.
    """
    TRANS_MAP = {"1": "Automatic", "2": "Manual"}

    seen    = set()
    results = []

    for c in inventory:
        make  = (c.get("carMake") or "").strip()
        model = (c.get("carModel") or "").strip()
        
        # ── skip invalid entries ──────────────────────────────────────
        if not make or not model or make.lower() == "none" or model.lower() == "none":
            continue
        
        key = (c["carMake"], c["carModel"])
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "id":           c["id"],
            "make":         c["carMake"],
            "model":        c["carModel"],
            "display_name": f"{c['carMake']} {c['carModel']}",
            "seating":      c["seatingCapacity"],
            "transmission": TRANS_MAP.get(str(c.get("transmissionType", "")), c.get("transmissionType", "")),
            "fuel":         str(c.get("fuelType", "")).capitalize(),
            "body_type":    str(c.get("bodyType", "")).capitalize(),   
            "doors":        c.get("doors", ""),                       
        })

    return results

def format_bookings_for_display(bookings: list[dict]) -> list[dict]:
    results = []
    for b in bookings:
        results.append({
            "id":           b["id"],
            "display_name": f"{b['carMake']} {b['carModel']}",
            "from_date":    b["fromDate"],
            "to_date":      b["toDate"],
            "status":       b["bookingStatus"],
        })
    return results

def make_response(
    intent, confidence, entities, missing_entities,
    next_stage, response_message, raw_query,
    data=None, available_inventory=None, redirect_url=None,
) -> IntentResponse:
    return IntentResponse(
        intent=intent,
        confidence=confidence,
        entities=entities,
        missing_entities=missing_entities,
        next_stage=next_stage,
        response_message=response_message,
        redirect_url=redirect_url,
        raw_query=raw_query,
        data=data, #raw data
        available_inventory=available_inventory, #initially raw but update with filters
        cars=format_cars_for_display(data) if data else [], #main data to be displayed
    )