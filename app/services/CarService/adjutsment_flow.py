from app.enums.intent_enums import IntentType
from app.enums.stage_enums import BookingStages
from app.core.logger import logger
from app.services.CarService.partials.response_builder import (
    filtered_options_message, fuel_question, make_response,
    seating_question, transmission_question,
)

TRANS_NORMALIZE = {"1": "automatic", "2": "manual"}
FUEL_NORMALIZE = {"p": "petrol","d": "diesel","b": "hybrid","e": "electric","h": "hydrogen",}

def _normalize_trans(val: str) -> str:
    return TRANS_NORMALIZE.get(str(val), str(val).lower())

def _apply_filters(inventory: list[dict], entities: dict) -> list[dict]:
    filtered = inventory
    if "seating_capacity" in entities:
        filtered = [c for c in filtered if int(c["seatingCapacity"]) == int(entities["seating_capacity"])]
    if "transmission_type" in entities:
        logger.info(f"Filtering transmission: looking for '{entities['transmission_type']}'")
        for c in filtered:
            logger.info(f"  Car {c['id']}: raw='{c['transmissionType']}' normalized='{_normalize_trans(c['transmissionType'])}'")
        filtered = [
            c for c in filtered
            if _normalize_trans(c["transmissionType"]) == entities["transmission_type"].lower()
        ]
        logger.info(f"After transmission filter: {len(filtered)} cars")
    if "fuel_type" in entities:
        filtered = [c for c in filtered if FUEL_NORMALIZE.get(str(c.get("fuelType", "")).lower()) == entities["fuel_type"].lower()]
    return filtered

async def run_adjustment(
    detected_intent, confidence, merged_entities, available_inventory, raw_query
):
    available_seating = sorted({int(c["seatingCapacity"]) for c in available_inventory})

    if "seating_capacity" not in merged_entities and "skip_seating_capacity" not in merged_entities and len(available_seating) > 1:
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["seating_capacity"],
            next_stage=BookingStages.COLLECTING_SEATING,
            response_message=seating_question(available_seating),
            raw_query=raw_query, available_inventory=available_inventory,
        )
    if "seating_capacity" not in merged_entities and len(available_seating) == 1:
        merged_entities["seating_capacity"] = available_seating[0]

    seat_filter = {"seating_capacity": merged_entities["seating_capacity"]} if "seating_capacity" in merged_entities else {}
    filtered_by_seating = _apply_filters(available_inventory, seat_filter)
    available_trans = list({_normalize_trans(c["transmissionType"]) for c in filtered_by_seating})

    if "transmission_type" not in merged_entities and "skip_transmission_type" not in merged_entities and len(available_trans) > 1:
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["transmission_type"],
            next_stage=BookingStages.COLLECTING_TRANSMISSION,
            response_message=transmission_question(available_trans),
            raw_query=raw_query, available_inventory=available_inventory,
        )
    if "transmission_type" not in merged_entities and len(available_trans) == 1:
        merged_entities["transmission_type"] = available_trans[0]

    trans_filter = {"transmission_type": merged_entities["transmission_type"]} if "transmission_type" in merged_entities else {}
    filtered_by_trans = _apply_filters(filtered_by_seating, trans_filter)
    available_fuels = list({
        FUEL_NORMALIZE.get(str(c.get("fuelType", "")).lower(), str(c.get("fuelType","")).lower())
        for c in filtered_by_trans if c.get("fuelType")
    })

    if "fuel_type" not in merged_entities and "skip_fuel_type" not in merged_entities and len(available_fuels) > 1:
        return make_response(
            intent=detected_intent, confidence=confidence,
            entities=merged_entities, missing_entities=["fuel_type"],
            next_stage=BookingStages.COLLECTING_FUEL_TYPE,
            response_message=fuel_question(available_fuels),
            raw_query=raw_query, available_inventory=available_inventory,
        )
    if "fuel_type" not in merged_entities and len(available_fuels) == 1:
        merged_entities["fuel_type"] = available_fuels[0]

    final_filtered = _apply_filters(available_inventory, merged_entities)
    return make_response(
        intent=detected_intent, confidence=confidence,
        entities=merged_entities, missing_entities=[],
        next_stage=BookingStages.SHOWING_OPTIONS,
        response_message=filtered_options_message(final_filtered, merged_entities),
        raw_query=raw_query, data=final_filtered, available_inventory=available_inventory,
    )