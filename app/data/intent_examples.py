from app.enums.intent_enums import IntentType


INTENT_EXAMPLES = {

    IntentType.CAR_BOOKING: [

        "book a car",
        "confirm booking",
        "reserve this car",
        "i want to book this vehicle",
        "book this suv",
        "confirm my rental",
        "reserve a 7 seater",
        "i want to proceed with booking",
        "book this automatic car",
        "rent this vehicle",
        "schedule this booking",
        "finalize the car booking",
        "book vehicle for next week",
        "confirm my car reservation",
        "complete the booking process"
    ],

    IntentType.CAR_SEARCH: [

        "i need a car",
        "looking for a vehicle",
        "show available cars",
        "need a 5 seater",
        "need a 7 seater",
        "looking for suv",
        "family trip vehicle",
        "need automatic car",
        "need manual transmission",
        "show hybrid cars",
        "show diesel vehicles",
        "available cars for next monday",
        "need rental car",
        "find available sedan",
        "looking for transportation",
        "show me cars",
        "which cars are available",
        "find me a car",
        "need a vehicle for travel",
        "looking for rental options",
        "need a car for weekend",
        "available luxury cars",
        "show hatchback cars",
        "need vehicle urgently",
        "find available inventory"
    ],

    IntentType.INVENTORY_FIND: [

        "check inventory",
        "show available inventory",
        "find available vehicles",
        "inventory status",
        "which vehicles are free",
        "show all available cars",
        "available fleet",
        "cars available in inventory",
        "which suv is available",
        "show available stock",
        "inventory availability",
        "vehicle inventory report",
        "find available automatic cars",
        "available vehicles for booking",
        "fleet availability"
    ],

    IntentType.CUSTOMER_FIND: [

        "find customer",
        "search customer",
        "customer details",
        "show customer info",
        "find customer by number",
        "search customer by name",
        "customer booking history",
        "show client details",
        "find user account",
        "customer payment history",
        "show customer profile",
        "locate customer",
        "find merchant customer",
        "customer invoice details",
        "show all customer records"
    ],

    IntentType.INVOICE_FIND: [

        "find invoice",
        "show invoice",
        "invoice details",
        "get invoice",
        "download invoice",
        "invoice status",
        "pending invoice",
        "paid invoice",
        "show customer invoice",
        "invoice history",
        "search invoice",
        "find invoice by id",
        "invoice report",
        "billing invoice",
        "show invoice summary"
    ],

    IntentType.PAYMENT_FIND: [

        "payment details",
        "show payments",
        "payment status",
        "pending payment",
        "failed payment",
        "customer payment",
        "payment report",
        "cash payment report",
        "online payment details",
        "show today's payment",
        "payment recovery",
        "check payment",
        "show transactions",
        "find payment record",
        "payment summary",
        "unpaid invoices",
        "show payment history",
        "which payments are pending",
        "payment reminder status",
        "get today's cash collection"
    ],

    IntentType.SERVICE_DUE: [

        "service due",
        "maintenance due",
        "vehicle service reminder",
        "oil change due",
        "car maintenance",
        "repair status",
        "show due services",
        "upcoming maintenance",
        "which cars need service",
        "vehicle inspection due",
        "service notification",
        "maintenance report",
        "garage service task",
        "find overdue service",
        "repair schedule",
        "show maintenance tasks",
        "vehicle health check",
        "service follow up",
        "inspection pending",
        "maintenance alerts"
    ],

    IntentType.TASK_STATUS: [

        "task status",
        "show task progress",
        "diary status",
        "work diary status",
        "pending tasks",
        "completed tasks",
        "assigned tasks",
        "task details",
        "show active tasks",
        "check work progress",
        "follow up task",
        "open tasks",
        "show ongoing work",
        "task completion report",
        "member assigned tasks",
        "show diary updates",
        "which tasks are pending",
        "task tracking",
        "work update",
        "show workflow status"
    ],

    IntentType.GREETING: [

        "hi",
        "hello",
        "hey",
        "good morning",
        "good evening",
        "how are you",
        "hello there",
        "hi ai",
        "hey assistant",
        "good afternoon",
        "yo",
        "hii",
        "hola",
        "what's up",
        "hey bot"
    ],

    IntentType.HELP: [

        "help",
        "what can you do",
        "show features",
        "guide me",
        "how does this work",
        "need assistance",
        "help me",
        "system help",
        "available commands",
        "what services are available",
        "support",
        "how to book a car",
        "how to check payments",
        "how to find inventory",
        "explain the workflow"
    ]
}