import streamlit as st
import requests
import uuid
import datetime

st.set_page_config(page_title="Car Rental", page_icon="🚗", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Fraunces:wght@700&display=swap');

html,body,[class*="css"]{font-family:'Inter',sans-serif!important}
#MainMenu,footer,header{visibility:hidden}
.block-container{padding:0!important;max-width:780px}

.top-bar{background:#fff;border-bottom:1px solid #ebebeb;padding:14px 20px;display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:100}
.top-bar .av{width:36px;height:36px;background:#1a1a1a;border-radius:10px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:16px;flex-shrink:0}
.top-bar .t{font-family:'Fraunces',serif;font-weight:700;font-size:17px;color:#1a1a1a}
.top-bar .s{font-size:11px;color:#aaa}
.online{width:7px;height:7px;background:#22c55e;border-radius:50%;margin-left:auto}

.stage-chip{display:inline-flex;align-items:center;gap:5px;background:#f0fdf4;color:#166534;border-radius:20px;padding:3px 10px;font-size:11px;font-weight:500;margin-bottom:6px}

.cars-label{font-size:10px;font-weight:600;color:#aaa;text-transform:uppercase;letter-spacing:.8px;margin:10px 0 7px}
.car-card{background:#fff;border:1px solid #ebebeb;border-radius:10px;padding:10px 11px;transition:border-color .15s;margin-bottom:4px}
.car-card:hover{border-color:#1a1a1a}
.car-num{font-size:9px;font-weight:700;color:#ccc;margin-bottom:2px}
.car-name{font-family:'Fraunces',serif;font-weight:700;font-size:12px;color:#1a1a1a;margin-bottom:5px;line-height:1.2}
.badges{display:flex;flex-wrap:wrap;gap:3px}
.badge{background:#f5f5f5;border-radius:4px;padding:2px 6px;font-size:9px;font-weight:500;color:#666}

.summary-card{background:#1a1a1a;border-radius:12px;padding:13px 15px;margin-top:10px;color:#fff}
.summary-card .sh{font-size:9px;font-weight:600;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.8px;margin-bottom:9px}
.srow{display:flex;justify-content:space-between;font-size:11.5px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.07)}
.srow:last-child{border:none}
.sk{color:rgba(255,255,255,.5)}.sv{font-weight:600}

.date-picker-box{background:#f9f9f9;border:1px solid #ebebeb;border-radius:12px;padding:14px 16px;margin:8px 0}
.date-picker-box .dp-title{font-size:11px;font-weight:600;color:#aaa;text-transform:uppercase;letter-spacing:.7px;margin-bottom:10px}

.err{background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:9px 13px;color:#dc2626;font-size:12px}
.welcome-msg{background:#fff;border:1px solid #ebebeb;border-radius:4px 16px 16px 16px;padding:11px 14px;font-size:13.5px;line-height:1.55;color:#1a1a1a}
.yes-hint{font-size:11px;color:#aaa;margin-top:8px}
</style>
""", unsafe_allow_html=True)

API_URL = "http://127.0.0.1:8000/api/v1/intent/analyze"
TODAY   = datetime.date.today()

FUEL_MAP = {"d":"Diesel","p":"Petrol","b":"Hybrid","e":"Electric","h":"Hydrogen"}
BODY_TYPE_MAP = {
    "S":"Sedan","1":"Hatchback","2":"SUV","3":"Coupe","4":"Sports Car",
    "5":"Station Wagon","6":"Convertible","7":"Minivan","8":"Pick Up Truck",
    "9":"Van","10":"Prime Mover","11":"Scooter",
}
TRANS_MAP = {"1":"Automatic","2":"Manual","automatic":"Automatic","manual":"Manual"}
STAGE_MAP = {
    "collecting_dates":          "📅 Collecting Dates",
    "showing_options":           "🚗 Showing Options",
    "collecting_seating":        "💺 Seating Preference",
    "collecting_transmission":   "⚙️ Transmission",
    "collecting_fuel_type":      "⛽ Fuel Type",
    "collecting_car_preference": "🔍 Pick a Car",
    "confirm_booking":           "✅ Confirming",
    "payment":                   "💳 Payment",
}
YES_WORDS = {"yes","yeah","yep","sure","ok","okay","proceed","start","yup","y"}

# ── Session init ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages      = []
    st.session_state.session_id    = f"sess_{uuid.uuid4().hex[:8]}"
    st.session_state.user_id       = 22
    st.session_state.pending_query = None
    st.session_state.started       = False
    st.session_state.current_stage = None


# ── Formatters ────────────────────────────────────────────────────────────────
def fmt_fuel(v):      return FUEL_MAP.get(str(v).lower(), str(v).capitalize())      if v else ""
def fmt_trans(v):     return TRANS_MAP.get(str(v).lower(), str(v).capitalize())     if v else ""
def fmt_body_type(v): return BODY_TYPE_MAP.get(str(v), str(v).capitalize())         if v else ""


# ── UI helpers ────────────────────────────────────────────────────────────────
def summary_html(entities: dict) -> str:
    name = (entities.get("selected_car_name") or "").strip()
    if not name:
        return ""
    rows = [("Car", name)]
    if entities.get("booking_dates"):     rows.append(("Dates",        entities["booking_dates"]))
    if entities.get("seating_capacity"):  rows.append(("Seating",      f"{entities['seating_capacity']} Seater"))
    if entities.get("transmission_type"): rows.append(("Transmission", fmt_trans(entities["transmission_type"])))
    if entities.get("fuel_type"):         rows.append(("Fuel",         fmt_fuel(entities["fuel_type"])))
    if entities.get("body_type"):         rows.append(("Body Type",    fmt_body_type(entities["body_type"])))
    r = "".join(
        f'<div class="srow"><span class="sk">{k}</span><span class="sv">{v}</span></div>'
        for k, v in rows
    )
    return f'<div class="summary-card"><div class="sh">Booking Summary</div>{r}</div>'


def payment_button_html(url: str) -> str:
    return (
        f'<a href="{url}" target="_blank" style="'
        f'display:inline-block;margin-top:10px;padding:10px 20px;'
        f'background:#1a1a1a;color:#fff;border-radius:8px;'
        f'font-size:13px;font-weight:600;text-decoration:none;">'
        f'💳 Complete Payment →</a>'
    )


def render_car_cards_native(cars: list, msg_idx: int = 0):
    if not cars:
        return
    st.markdown('<div class="cars-label">Available Cars</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for i, car in enumerate(cars):
        car_id = car.get("id")
        name   = (car.get("display_name") or f"{car.get('make','')} {car.get('model','')}").strip() or f"Car #{i+1}"
        seats  = car.get("seating", "")
        trans  = fmt_trans(car.get("transmission", ""))
        fuel   = fmt_fuel(car.get("fuel", ""))
        body   = fmt_body_type(car.get("body_type", ""))
        doors  = car.get("doors", "")
        b = ""
        if seats: b += f'<span class="badge">{seats} Seat</span>'
        if trans: b += f'<span class="badge">{trans}</span>'
        if fuel:  b += f'<span class="badge">{fuel}</span>'
        if body:  b += f'<span class="badge">{body}</span>'
        if doors and str(doors).isdigit() and int(doors) > 0:
            b += f'<span class="badge">{doors} Doors</span>'
        with cols[i % 3]:
            st.markdown(
                f'<div class="car-card"><div class="car-num">#{i+1}</div>'
                f'<div class="car-name">{name}</div>'
                f'<div class="badges">{b}</div></div>',
                unsafe_allow_html=True,
            )
            if st.button(f"Book #{i+1}", key=f"book_{msg_idx}_{i}"):
                st.session_state.pending_query = f"book_car_id:{car_id}"
                st.rerun()


def render_bot_extras(cars: list, entities: dict, msg_idx: int = 0):
    render_car_cards_native(cars, msg_idx)
    sh = summary_html(entities)
    if sh:
        st.markdown(sh, unsafe_allow_html=True)


# ── API call ──────────────────────────────────────────────────────────────────
def send_to_api(query: str) -> tuple:
    """
    Returns (msg_text, cars, entities, stage_lbl, redirect_url).
    """
    try:
        r = requests.post(API_URL, json={
            "query":      query,
            "user_id":    st.session_state.user_id,
            "session_id": st.session_state.session_id,
        }, timeout=90)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.ConnectionError:
        return "Cannot connect — make sure the API is running on port 8000.", [], {}, "", None
    except Exception as e:
        return f"Error: {e}", [], {}, "", None

    next_stage = data.get("next_stage")
    st.session_state.current_stage = next_stage
    return (
        data.get("response_message", "Sorry, something went wrong."),
        data.get("cars", []),
        data.get("entities", {}),
        STAGE_MAP.get(next_stage, "") if next_stage else "",
        data.get("redirect_url"),
    )


# ── Render bot message ────────────────────────────────────────────────────────
def append_and_render_bot(
    msg_text: str,
    cars: list,
    entities: dict,
    stage_lbl: str,
    redirect_url: str | None = None,
):
    if stage_lbl:
        st.markdown(f'<div class="stage-chip">{stage_lbl}</div>', unsafe_allow_html=True)
    st.write(msg_text)

    msg_idx = len(st.session_state.messages)
    render_bot_extras(cars, entities, msg_idx)

    if redirect_url:
        st.markdown(payment_button_html(redirect_url), unsafe_allow_html=True)
        # Auto-open in new tab
        st.components.v1.html(
            f'<script>window.open("{redirect_url}", "_blank");</script>',
            height=0,
        )

    st.session_state.messages.append({
        "role":         "assistant",
        "content":      msg_text,
        "cars":         cars,
        "entities":     entities,
        "stage":        stage_lbl,
        "redirect_url": redirect_url,
    })


# ── Top bar ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="top-bar">
  <div class="av">🚗</div>
  <div><div class="t">Car Rental Assistant</div><div class="s">Find your perfect ride</div></div>
  <div class="online"></div>
</div>
""", unsafe_allow_html=True)

# ── Static welcome ────────────────────────────────────────────────────────────
with st.chat_message("assistant"):
    st.markdown("""
    <div class="welcome-msg">
        👋 Hi there! I'm your Car Rental Assistant.<br><br>
        I can help you find and book the perfect car for your trip — just tell me
        your dates and preferences and I'll do the rest.<br><br>
        <strong>Type <em>yes</em> to get started!</strong>
    </div>
    """, unsafe_allow_html=True)

# ── Pending card-click ────────────────────────────────────────────────────────
if st.session_state.pending_query:
    query = st.session_state.pending_query
    st.session_state.pending_query = None
    with st.chat_message("user"):
        st.write(query)
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("assistant"):
        with st.spinner(""):
            msg_text, cars, entities, stage_lbl, redirect_url = send_to_api(query)
        append_and_render_bot(msg_text, cars, entities, stage_lbl, redirect_url)
    st.rerun()

# ── Chat history ──────────────────────────────────────────────────────────────
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and msg.get("stage"):
            st.markdown(f'<div class="stage-chip">{msg["stage"]}</div>', unsafe_allow_html=True)
        st.write(msg["content"])
        if msg["role"] == "assistant":
            render_car_cards_native(msg.get("cars", []), msg_idx=idx)
            sh = summary_html(msg.get("entities", {}))
            if sh:
                st.markdown(sh, unsafe_allow_html=True)
            if msg.get("redirect_url"):
                st.markdown(payment_button_html(msg["redirect_url"]), unsafe_allow_html=True)

# ── Date picker (collecting_dates stage) ──────────────────────────────────────
if st.session_state.started and st.session_state.current_stage == "collecting_dates":
    st.markdown(
        '<div class="date-picker-box"><div class="dp-title">Select Your Dates</div></div>',
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2)
    with col1:
        pickup = st.date_input("Pickup Date", min_value=TODAY, value=TODAY, key="pickup")
    with col2:
        dropoff = st.date_input(
            "Drop-off Date",
            min_value=pickup + datetime.timedelta(days=1),
            value=pickup + datetime.timedelta(days=1),
            key="dropoff",
        )
    if st.button("Search Available Cars →", use_container_width=True):
        date_query = f"{pickup.strftime('%d %B')} to {dropoff.strftime('%d %B')}"
        with st.chat_message("user"):
            st.write(date_query)
        st.session_state.messages.append({"role": "user", "content": date_query})
        with st.chat_message("assistant"):
            with st.spinner(""):
                msg_text, cars, entities, stage_lbl, redirect_url = send_to_api(date_query)
            append_and_render_bot(msg_text, cars, entities, stage_lbl, redirect_url)
        st.rerun()

# ── Chat input ────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Type a message..."):
    if not st.session_state.started and prompt.strip().lower() in YES_WORDS:
        st.session_state.started = True
        with st.chat_message("user"):
            st.write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("assistant"):
            with st.spinner(""):
                msg_text, cars, entities, stage_lbl, redirect_url = send_to_api("hi")
            append_and_render_bot(msg_text, cars, entities, stage_lbl, redirect_url)
        st.rerun()

    elif not st.session_state.started:
        with st.chat_message("assistant"):
            st.write("Please type **yes** to get started!")

    else:
        with st.chat_message("user"):
            st.write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("assistant"):
            with st.spinner(""):
                msg_text, cars, entities, stage_lbl, redirect_url = send_to_api(prompt)
            append_and_render_bot(msg_text, cars, entities, stage_lbl, redirect_url)
        st.rerun()