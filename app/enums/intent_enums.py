from enum import Enum

class IntentType(str, Enum):
    CAR_BOOKING = "car_booking"
    CAR_SEARCH = "car_search"
    INVENTORY_FIND = "inventory_find"
    CUSTOMER_FIND = "customer_find"
    INVOICE_FIND = "invoice_find"
    PAYMENT_FIND = "payment_find"
    SERVICE_DUE = "service_due"
    TASK_STATUS = "task_status"
    GREETING = "greeting"
    HELP = "help"
    UNKNOWN = "unknown"