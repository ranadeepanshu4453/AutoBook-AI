from app.enums.intent_enums import IntentType


INTENT_EXAMPLES = {

    IntentType.CAR_BOOKING: [

        # ── Core booking phrases ──────────────────────────────────────────
        "I want to book a car",
        "I need to book a car",
        "book a car for me",
        "I want to rent a car",
        "I need to rent a car",
        "reserve a car",
        "make a car booking",
        "I want to make a booking",
        "car rental booking",

        # ── With dates ────────────────────────────────────────────────────
        "book a car from 10 to 15 june",
        "I need a car from monday to friday",
        "rent a car from 1st july to 5th july",
        "need a car from next thursday to sunday",
        "book from 20 june to 25 june",
        "car from 12 to 14 june",
        "available from 15th to 18th",
        "need a car this weekend",
        "rent for next week",
        "car for 3 days starting monday",
        "need wheels from tuesday to thursday",

        # ── With filters + dates (YOUR FAILING PATTERN) ───────────────────
        "show me 5 seater cars from 12 to 14 june",
        "5 seater manual car from 10 to 15 june",
        "automatic car from next monday to wednesday",
        "diesel suv from 20 to 25 june",
        "7 seater from this friday to sunday",
        "manual transmission car for next weekend",
        "petrol car from 1 july to 7 july",
        "show me automatic cars available next week",
        "need a 5 seat automatic diesel from 15 to 18 june",
        "looking for manual cars from thursday to saturday",

        # ── Show me patterns ──────────────────────────────────────────────
        "show me available cars",
        "show me cars for next week",
        "show me what cars you have",
        "show me cars from 15 june",
        "what cars do you have available",
        "what cars are available next weekend",
        "show available vehicles",

        # ── Casual / conversational ───────────────────────────────────────
        "need a ride next week",
        "looking for a car to rent",
        "want to hire a car",
        "need wheels for the weekend",
        "got anything available next thursday",
        "any cars free on saturday",
        "looking for something to drive next week",
        "need transport from monday",
        "any availability for june 20",

        # ── Seating-first patterns ────────────────────────────────────────
        "need a 7 seater",
        "looking for a 5 seat car",
        "want a 7 seater for next weekend",
        "need something with 7 seats",
        "family car with 7 seats",
        "large car for 6 people",

        # ── Transmission-first ────────────────────────────────────────────
        "need an automatic car",
        "looking for manual transmission",
        "want an auto from next week",
        "only manual cars please",
        "prefer automatic gearbox",

        # ── Fuel-first ────────────────────────────────────────────────────
        "need a diesel car",
        "looking for electric vehicle rental",
        "want a petrol car for the weekend",
        "any hybrid cars available",

        # ── Typos and informal spelling ───────────────────────────────────
        "nedd a car from monday",
        "boo a car for next week",
        "car form 15 to 18 june",
        "5seater manual car from 12 to 14 june",
        "automtic car next weekend",
    ],

    IntentType.CAR_SEARCH: [

        # ── Browse without committing ─────────────────────────────────────
        "what cars do you have",
        "show me your fleet",
        "list available cars",
        "what vehicles are available",
        "browse cars",
        "see all cars",
        "what options do you have",
        "show me the car list",
        "what cars can I rent",

        # ── Availability checks ───────────────────────────────────────────
        "is a toyota camry available",
        "do you have any SUVs",
        "any automatics available",
        "check availability for next week",
        "what is available for june 20",
        "any cars available this weekend",
        "is there anything available on saturday",

        # ── Comparison / browsing ─────────────────────────────────────────
        "show me different car options",
        "what types of cars do you offer",
        "compare available cars",
        "what sedans do you have",
        "show me SUVs",
        "any luxury cars available",
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

    IntentType.CHECK_BOOKING_STATUS: [
        "what is my booking status",
        "show my current bookings",
        "do I have any active bookings",
        "check my booking",
        "what bookings do I have",
        "show active rentals",
        "current booking status",
        "is my car still booked",
        "what's the status of my reservation",
        "show my reservations",
        "any ongoing bookings",
        "list my active bookings",
        "check my rental status",
        "what car did I book",
        "show me my booking details",
        "my current rentals",
        "status of my car booking",
        "do I have a car booked right now",
        "check active reservations",
        "show all current bookings",
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