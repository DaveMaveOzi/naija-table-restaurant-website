
import os
import sqlite3
import hashlib
import math
import hmac
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "restaurant.db"
UPLOAD_DIR = APP_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Naija Table | Nigerian Kitchen", page_icon="🍲", layout="wide", initial_sidebar_state="collapsed")

# -------------------- DATABASE --------------------
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS menu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, category TEXT NOT NULL, description TEXT DEFAULT '',
        price INTEGER NOT NULL, available INTEGER DEFAULT 1, image_url TEXT DEFAULT ''
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT NOT NULL, phone TEXT NOT NULL,
        address TEXT DEFAULT '', items TEXT NOT NULL, total INTEGER NOT NULL,
        status TEXT DEFAULT 'New', created_at TEXT NOT NULL,
        customer_lat REAL, customer_lon REAL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS delivery_tracking (
        order_id INTEGER PRIMARY KEY,
        driver_lat REAL, driver_lon REAL,
        updated_at TEXT NOT NULL DEFAULT ''
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS restaurant_settings (
        setting_key TEXT PRIMARY KEY,
        setting_value TEXT NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS admin_auth (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        username TEXT NOT NULL,
        salt TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    cur.execute("INSERT OR IGNORE INTO restaurant_settings(setting_key, setting_value) VALUES('opening_time','10:00')")
    cur.execute("INSERT OR IGNORE INTO restaurant_settings(setting_key, setting_value) VALUES('closing_time','22:00')")
    # Safe migration for databases created by earlier project versions.
    order_columns = {row[1] for row in cur.execute("PRAGMA table_info(orders)").fetchall()}
    if "customer_lat" not in order_columns:
        cur.execute("ALTER TABLE orders ADD COLUMN customer_lat REAL")
    if "customer_lon" not in order_columns:
        cur.execute("ALTER TABLE orders ADD COLUMN customer_lon REAL")
    count = cur.execute("SELECT COUNT(*) FROM menu").fetchone()[0]
    if count == 0:
        items = [
            ("Egusi Soup","Soups","Rich melon-seed soup with traditional spices.",4500),
            ("Efo Riro","Soups","A vibrant Yoruba spinach stew.",4000),
            ("Okro Soup","Soups","Fresh okro simmered in a flavourful sauce.",3500),
            ("Afang Soup","Soups","A hearty vegetable soup with afang leaves.",5000),
            ("Bitterleaf Soup","Soups","Traditional bitterleaf soup, slow-cooked.",4500),
            ("Jollof Rice","Rice","Smoky party-style Nigerian jollof.",3500),
            ("Coconut Rice","Rice","Fragrant rice cooked in coconut milk.",4000),
            ("Fried Rice","Rice","Colourful fried rice with vegetables.",3500),
            ("Special Rice","Rice","House special rice with signature seasoning.",5000),
            ("Meat Pie","Snacks","Golden pastry with a savoury filling.",1200),
            ("Sausage Roll","Snacks","Flaky pastry wrapped around sausage.",1000),
            ("Fish Pie","Snacks","Crisp pastry with a seasoned fish filling.",1300),
            ("Puff Puff (6 pcs)","Snacks","Soft, golden Nigerian puff puff.",1500),
            ("Small Chops","Snacks","A tasty mix of party favourites.",4500),
            ("Bottled Water","Drinks","Chilled bottled water.",500),
            ("Coca-Cola","Drinks","Chilled Coca-Cola.",700),
            ("Fanta","Drinks","Chilled orange Fanta.",700),
            ("Sprite","Drinks","Chilled Sprite.",700),
            ("Energy Drink","Drinks","Chilled energy drink.",1500),
            ("Fried Plantain","Sides","Sweet ripe plantain, fried golden.",1500),
            ("Fresh Salad","Sides","Fresh, crunchy house salad.",1800),
            ("French Fries","Sides","Crispy golden fries.",2000),
            ("Boiled Egg","Sides","One boiled egg.",500),
            ("Grilled Chicken","Meat","Well-seasoned grilled chicken portion.",3500),
            ("Goat Meat","Meat","Tender, spicy goat meat.",3000),
            ("Beef","Meat","Seasoned beef portion.",2000),
            ("Turkey","Meat","Juicy turkey portion.",4000),
            ("Boiled White Yam","Yam","Soft boiled yam portions.",2500),
            ("Yam Porridge","Yam","Rich yam porridge with palm oil and spices.",3500),
        ]
        cur.executemany("INSERT INTO menu(name,category,description,price) VALUES(?,?,?,?)", items)
    conn.commit()
    conn.close()

init_db()

# -------------------- ADMIN AUTHENTICATION --------------------
# Secrets are read from Streamlit Community Cloud settings or local environment.
# Never commit real credentials or recovery codes to GitHub.
def config_value(*names, default=""):
    for name in names:
        try:
            value = st.secrets.get(name, "")
            if value:
                return str(value)
        except Exception:
            pass
        value = os.getenv(name, "")
        if value:
            return str(value)
    return default


def make_password_hash(password, salt_hex=None):
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return salt.hex(), digest.hex()


def verify_password(password, salt_hex, expected_hash):
    _, candidate = make_password_hash(password, salt_hex)
    return hmac.compare_digest(candidate, expected_hash)


def get_admin_account():
    conn = db()
    row = conn.execute("SELECT * FROM admin_auth WHERE id=1").fetchone()
    conn.close()
    return dict(row) if row else None


def save_admin_password(username, password):
    salt, digest = make_password_hash(password)
    conn = db()
    conn.execute("""INSERT INTO admin_auth(id,username,salt,password_hash,updated_at)
        VALUES(1,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
        username=excluded.username,salt=excluded.salt,
        password_hash=excluded.password_hash,updated_at=excluded.updated_at""",
        (username, salt, digest, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()


def bootstrap_admin_account():
    if get_admin_account() is None:
        username = config_value("ADMIN_USERNAME", "RESTAURANT_ADMIN_USER", default="admin")
        password = config_value("ADMIN_PASSWORD", "RESTAURANT_ADMIN_PASSWORD", default="ChangeMe123!")
        save_admin_password(username, password)


bootstrap_admin_account()

# -------------------- HELPERS --------------------
def money(value):
    return "₦" + f"{int(value):,}"

def get_restaurant_hours():
    conn = db()
    rows = conn.execute("SELECT setting_key, setting_value FROM restaurant_settings").fetchall()
    conn.close()
    values = {row["setting_key"]: row["setting_value"] for row in rows}
    return values.get("opening_time", "10:00"), values.get("closing_time", "22:00")

def format_clock(value):
    try:
        parsed = datetime.strptime(value, "%H:%M")
        hour = parsed.strftime("%I").lstrip("0") or "12"
        suffix = parsed.strftime("%p").lower()
        return f"{hour}{suffix}"
    except ValueError:
        return value

def get_menu(available_only=False):
    conn = db()
    q = "SELECT * FROM menu"
    if available_only:
        q += " WHERE available=1"
    rows = conn.execute(q + " ORDER BY category, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def set_theme_css(theme):
    dark = theme == "Dark"
    bg = "#171a16" if dark else "#f7f4ed"
    panel = "#222720" if dark else "#fffdf8"
    text = "#f3f0e8" if dark else "#252820"
    muted = "#c9c7bd" if dark else "#68685f"
    border = "#3b4037" if dark else "#e6e0d4"
    alert_bg = "#34402e" if dark else "#52633d"
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');\n    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400,1,0&display=swap');
    :root {{ color-scheme: {'dark' if dark else 'light'}; }}
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMarkdownContainer"],
    button, input, textarea, select, label, p, span, div {{ font-family:'Poppins',sans-serif !important; }}
    [data-testid="stAppViewContainer"], [data-testid="stMain"] {{ background:{bg} !important; color:{text} !important; }}
    [data-testid="stHeader"] {{ background:{bg} !important; }}
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{ display:none !important; width:0 !important; }}
    [data-testid="stAppViewContainer"] > .main {{ margin-left:0 !important; }}
    .block-container {{ max-width:1180px; padding-top:.7rem; padding-bottom:3rem; }}
    .st-key-admin_auth {{ width:100%; max-width:620px; margin:0 auto !important; }}
    .st-key-admin_auth [data-testid=\"stForm\"] {{ padding:16px !important; border-radius:9px !important; }}
    .st-key-admin_auth [data-testid=\"stTextInput\"] {{ margin-bottom:.35rem; }}
    .st-key-admin_auth [data-testid=\"stFormSubmitButton\"] button {{ width:auto !important; min-width:88px !important; padding:.42rem .9rem !important; }}
    .st-key-admin_auth [data-testid=\"stTextInput\"] button, .st-key-admin_auth [data-testid=\"stTextInput\"] button span, .st-key-admin_auth [data-testid=\"stTextInput\"] [data-testid=\"stIconMaterial\"] {{ font-family:'Material Symbols Rounded' !important; font-feature-settings:'liga' !important; }}
    h1,h2,h3,h4 {{ color:{text} !important; font-weight:600 !important; letter-spacing:-.5px; }}
    h1 {{ font-size:clamp(1.8rem,3vw,2.65rem) !important; }}
    p {{ color:{muted}; line-height:1.65; }}
    .brand {{ font-size:1.25rem; font-weight:800; letter-spacing:-1px; color:{text}; }}
    .brand span {{ color:#a96b3c; }}
    .brand-sub {{ color:{muted}; font-size:.59rem; letter-spacing:2px; margin-top:-2px; }}
    .section-kicker {{ text-transform:uppercase; letter-spacing:2px; color:#a96b3c; font-weight:600; font-size:.66rem; }}
    .hero {{ background:linear-gradient(90deg,rgba(17,22,16,.86),rgba(17,22,16,.22)),url('https://images.unsplash.com/photo-1604329760661-e71dc83f8f26?auto=format&fit=crop&w=1800&q=85'); background-size:cover; background-position:center 52%; min-height:390px; padding:clamp(28px,5vw,64px); display:flex; flex-direction:column; justify-content:center; margin:14px 0 34px; border-radius:5px; }}
    .hero h1 {{ color:#fff !important; font-size:clamp(2rem,4vw,3.35rem) !important; line-height:1.22; max-width:650px; margin:.55rem 0 1rem; font-weight:600 !important; white-space:normal; }}
    .hero p {{ color:#fff !important; max-width:540px; font-size:.9rem; }}
    .hero .eyebrow {{ color:#f0d2a9 !important; text-transform:uppercase; letter-spacing:2px; font-weight:600; font-size:.7rem; }}
    [class*="st-key-food_card_"] [data-testid="stVerticalBlockBorderWrapper"] {{ background:{panel} !important; border:1px solid {border} !important; border-radius:7px !important; padding:5px !important; }}
    [class*="st-key-food_card_"] [data-testid="stVerticalBlock"] {{ gap:.35rem !important; }}
    [class*="st-key-food_card_"] h3 {{ font-size:.92rem !important; margin:1px 0 3px; font-weight:600 !important; }}
    [class*="st-key-food_card_"] p {{ color:{muted}; font-size:.72rem; line-height:1.45; margin:0 0 4px; }}
    .food-category {{ display:inline-block; color:#a96b3c; font-size:.6rem; font-weight:600; letter-spacing:1px; text-transform:uppercase; }}
    .price {{ font-weight:600; font-size:.9rem; color:{'#e0ad78' if dark else '#92552f'}; }}
    .available {{ color:#79b777; font-size:.68rem; font-weight:600; }}
    .unavailable {{ color:#f09a8d; font-size:.68rem; font-weight:600; }}
    .info-panel {{ background:{panel}; border:1px solid {border}; border-radius:5px; padding:18px; }}
    div.stButton > button, div.stFormSubmitButton > button, div[data-testid="stFormSubmitButton"] button {{ border-radius:4px; border:1px solid #52633d !important; background:#52633d !important; color:#fff !important; font-weight:500; padding:.38rem .72rem; min-height:2.15rem; font-size:.78rem !important; }}
    div.stButton > button *, div.stFormSubmitButton > button *, div[data-testid="stFormSubmitButton"] button * {{ color:#fff !important; }}
    div.stButton > button:hover, div.stFormSubmitButton > button:hover, div[data-testid="stFormSubmitButton"] button:hover {{ background:#3e4d2e !important; color:#fff !important; border-color:#3e4d2e !important; }}
    div.stButton > button:disabled, div.stFormSubmitButton > button:disabled {{ color:#fff !important; opacity:.58; }}
    [data-testid="stAlert"] {{ background:{alert_bg} !important; border:1px solid {alert_bg} !important; }}
    [data-testid="stAlert"] *, [data-testid="stToast"] *, [data-testid="stNotification"] * {{ color:#fff !important; }}
    [data-testid="stCaptionContainer"] p {{ color:{muted} !important; }}
    div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input, div[data-testid="stTextArea"] textarea, div[data-testid="stSelectbox"] > div {{ border-radius:4px; }}
    div[data-testid="stNumberInput"] {{ max-width:112px; }}
    [data-testid="stMetric"] {{ background:{panel}; padding:12px; border:1px solid {border}; border-radius:5px; }}
    .footer {{ text-align:center; color:{muted}; padding:30px 0 12px; font-size:.7rem; letter-spacing:.5px; }}
    .footer-tagline {{ color:{text}; font-size:.72rem; font-weight:600; letter-spacing:1.1px; margin-bottom:7px; }}
    .footer-copyright {{ color:{muted}; font-size:.68rem; margin-bottom:14px; }}
    .footer-admin-link {{ display:inline-block; color:{'#e5c29b' if dark else '#52633d'} !important; font-size:.66rem; font-weight:600; letter-spacing:1.4px; text-decoration:none !important; border:1px solid {border}; border-radius:3px; padding:7px 13px; transition:background .2s ease,border-color .2s ease; }}
    .footer-admin-link:hover {{ background:{panel}; border-color:#a96b3c; color:{text} !important; }}
    /* HEADER LAYOUT: separate desktop and phone structures avoid overlap. */
    .st-key-desktop_header {{
      display:block !important; width:100% !important; margin:0 0 10px !important;
      padding:16px 0 10px !important; position:relative !important; z-index:5 !important;
    }}
    .st-key-desktop_header [data-testid="stHorizontalBlock"] {{
      display:flex !important; flex-wrap:nowrap !important; align-items:center !important;
      justify-content:space-between !important; gap:12px !important; width:100% !important;
    }}
    .st-key-desktop_header [data-testid="column"] {{
      flex:0 0 auto !important; min-width:0 !important; padding:0 !important;
    }}
    .st-key-desktop_header [data-testid="column"]:first-child {{ flex:1 1 auto !important; }}
    .st-key-desktop_header .brand {{ font-size:1.25rem !important; line-height:1.2 !important; }}
    .st-key-desktop_header .brand-sub {{ font-size:.59rem !important; letter-spacing:2px !important; }}
    .st-key-desktop_header .st-key-desktop_theme button {{
      width:42px !important; min-width:42px !important; max-width:42px !important;
      height:42px !important; min-height:42px !important; padding:0 !important;
      border-radius:50% !important; display:flex !important; align-items:center !important;
      justify-content:center !important; margin:0 !important;
    }}
    .st-key-mobile_header {{ display:none !important; }}

    @media(max-width:700px) {{
      .st-key-desktop_header {{ display:none !important; }}
      .st-key-mobile_header {{
        display:block !important; width:100% !important; margin:0 0 8px !important;
        padding:22px 0 0 !important; position:relative !important; z-index:10 !important;
      }}
      .st-key-mobile_brand {{
        display:block !important; width:100% !important; margin:0 0 18px !important;
        padding:0 !important; min-height:42px !important;
      }}
      .st-key-mobile_brand .brand {{
        display:block !important; font-size:1.12rem !important; line-height:1.25 !important;
        white-space:nowrap !important; visibility:visible !important; opacity:1 !important;
      }}
      .st-key-mobile_brand .brand-sub {{
        display:block !important; font-size:.52rem !important; letter-spacing:1.4px !important;
        line-height:1.4 !important; white-space:nowrap !important;
      }}
      .st-key-mobile_controls {{ display:block !important; width:100% !important; margin:0 0 12px !important; }}
      .st-key-mobile_controls [data-testid="stHorizontalBlock"] {{
        display:flex !important; flex-wrap:nowrap !important; align-items:center !important;
        justify-content:flex-start !important; gap:9px !important; width:100% !important;
      }}
      .st-key-mobile_controls [data-testid="column"] {{
        flex:0 0 42px !important; width:42px !important; min-width:42px !important;
        max-width:42px !important; padding:0 !important;
      }}
      .st-key-mobile_controls button {{
        display:flex !important; visibility:visible !important; opacity:1 !important;
        box-sizing:border-box !important; width:42px !important; min-width:42px !important;
        max-width:42px !important; height:42px !important; min-height:42px !important;
        max-height:42px !important; padding:0 !important; margin:0 !important;
        border-radius:50% !important; align-items:center !important; justify-content:center !important;
      }}
      .st-key-desktop_nav {{ display:none !important; }}
      .st-key-mobile_navigation_panel {{ margin-top:4px !important; }}
      .block-container {{ padding-left:.75rem !important; padding-right:.75rem !important; }}
      .hero {{ min-height:300px !important; padding:22px 18px !important; margin:8px 0 22px !important; background-position:58% center !important; }}
      .hero h1 {{ font-size:2rem !important; line-height:1.22 !important; }}
    }}
    .contact-row {{ display:flex; align-items:center; gap:13px; padding:12px 0; border-bottom:1px solid {border}; color:{text}; }}
    .contact-icon {{ width:38px; height:38px; display:flex; align-items:center; justify-content:center; border-radius:10px; background:{'#35402f' if dark else '#edf0e7'}; color:{'#e5c29b' if dark else '#52633d'}; flex-shrink:0; }}
    .material-symbols-rounded {{ font-family:'Material Symbols Rounded' !important; font-size:21px; line-height:1; font-weight:normal; font-style:normal; letter-spacing:normal; text-transform:none; display:inline-block; white-space:nowrap; direction:ltr; -webkit-font-feature-settings:'liga'; -webkit-font-smoothing:antialiased; }}
    .contact-row strong {{ display:block; color:{text}; font-size:.83rem; }}
    .contact-row small {{ color:{muted}; font-size:.75rem; }}
    @media(max-width:900px) {{
      .block-container {{ padding-left:1rem; padding-right:1rem; }}
      .hero {{ min-height:350px; }}
      .hero h1 {{ font-size:clamp(1.9rem,5vw,2.8rem) !important; }}
    }}
    @media(max-width:700px) {{
      .st-key-desktop_nav {{ display:none !important; }}
    }}
    @media(max-width:600px) {{
      .st-key-mobile_navigation_panel [data-testid="stHorizontalBlock"] {{ flex-wrap:wrap !important; }}
      .st-key-mobile_navigation_panel [data-testid="column"] {{ min-width:calc(50% - .25rem) !important; flex:1 1 calc(50% - .25rem) !important; }}
      .block-container {{ padding-left:.5rem !important; padding-right:.75rem !important; }}
      .hero {{ min-height:330px; padding:22px 18px; background-position:58% center; margin:10px 0 25px; }}
      .hero h1 {{ font-size:2rem !important; line-height:1.25; }}
      [class*="st-key-food_card_"] [data-testid="stVerticalBlockBorderWrapper"] {{ padding:3px !important; }}
      .st-key-desktop_nav [data-testid="stHorizontalBlock"] {{ gap:.2rem; }}
      .st-key-desktop_nav button {{ font-size:.66rem !important; padding:.28rem .12rem !important; min-height:2rem !important; }}
    }}

    </style>
    """, unsafe_allow_html=True)

# -------------------- IMAGE HELPERS --------------------
DEFAULT_IMAGES = {
    "Soups": "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=700&q=80",
    "Rice": "https://images.unsplash.com/photo-1516684732162-798a0062be99?auto=format&fit=crop&w=700&q=80",
    "Snacks": "https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=700&q=80",
    "Drinks": "https://images.unsplash.com/photo-1544145945-f90425340c7e?auto=format&fit=crop&w=700&q=80",
    "Sides": "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=700&q=80",
    "Meat": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=700&q=80",
    "Yam": "https://images.unsplash.com/photo-1518977676601-b53f82aba655?auto=format&fit=crop&w=700&q=80",
}

def item_image(item):
    url = (item.get("image_url") or "").strip()
    if url:
        if url.startswith("/"):
            local = APP_DIR / url.lstrip("/")
            if local.exists(): return str(local)
        return url
    return DEFAULT_IMAGES.get(item.get("category"), DEFAULT_IMAGES["Rice"])

def save_uploaded_image(uploaded):
    if uploaded is None:
        return ""
    suffix = Path(uploaded.name).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("Please upload a PNG, JPG or WEBP image.")
    filename = f"{uuid.uuid4().hex}{suffix}"
    target = UPLOAD_DIR / filename
    target.write_bytes(uploaded.getbuffer())
    return f"uploads/{filename}"

def render_food_item(item, key_prefix, show_quantity=False):
    with st.container(key=f"food_card_{key_prefix}_{item['id']}", border=True):
        image_col, detail_col = st.columns([0.78, 2.7], vertical_alignment="center", gap="small")
        with image_col:
            st.image(item_image(item), width=92)
        with detail_col:
            status_html = '<div class="available">● Available</div>' if item["available"] else '<div class="unavailable">● Currently unavailable</div>'
            st.markdown(
                f'<div class="food-category">{item["category"]}</div><h3>{item["name"]}</h3>'
                f'<p>{item["description"]}</p><div class="price">{money(item["price"])}</div>{status_html}',
                unsafe_allow_html=True,
            )
        if show_quantity and item["available"]:
            qty_col, action_col, spacer_col = st.columns([0.72, 1.15, 2.0], vertical_alignment="center", gap="small")
            with qty_col:
                qty = st.number_input("Quantity", min_value=1, max_value=20, value=1, step=1,
                                      key=f"qty_{key_prefix}_{item['id']}", label_visibility="collapsed")
            with action_col:
                if st.button("Add to basket", key=f"{key_prefix}_add_{item['id']}", use_container_width=True):
                    st.session_state.cart[item["id"]] = st.session_state.cart.get(item["id"], 0) + int(qty)
                    st.toast(f'{item["name"]} added to basket')
        elif not show_quantity:
            if st.button("Add to basket", key=f"{key_prefix}_add_{item['id']}"):
                if item["available"]:
                    st.session_state.cart[item["id"]] = st.session_state.cart.get(item["id"], 0) + 1
                    st.toast(f'{item["name"]} added to basket')
                else:
                    st.warning("This item is currently unavailable.")


def haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlon/2)**2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


@st.fragment(run_every="15s")
def render_live_tracking(order_id, phone):
    conn = db()
    order = conn.execute("SELECT * FROM orders WHERE id=? AND phone=?", (int(order_id), phone)).fetchone()
    tracking = conn.execute("SELECT * FROM delivery_tracking WHERE order_id=?", (int(order_id),)).fetchone()
    conn.close()
    if not order:
        st.error("We could not find an order matching those details.")
        return
    st.success(f"Order #{order['id']} · {order['status']}")
    st.write(f"**Items:** {order['items']}")
    st.write(f"**Delivery address:** {order['address'] or 'Not provided'}")
    if order["status"] in ["Picked up", "Out for delivery"] and tracking and tracking["driver_lat"] is not None and order["customer_lat"] is not None:
        distance = haversine_km(float(tracking["driver_lat"]), float(tracking["driver_lon"]), float(order["customer_lat"]), float(order["customer_lon"]))
        eta = max(1, round((distance / 25.0) * 60))
        st.metric("Estimated arrival", f"About {eta} min", help="Approximation based on straight-line distance at 25 km/h. Actual road ETA may differ.")
        st.caption(f"Driver location last updated: {tracking['updated_at']} · This panel refreshes every 15 seconds.")
        map_data = [{"lat": float(tracking["driver_lat"]), "lon": float(tracking["driver_lon"]), "Location": "Driver"},
                    {"lat": float(order["customer_lat"]), "lon": float(order["customer_lon"]), "Location": "Delivery address"}]
        st.map(map_data, latitude="lat", longitude="lon", size=150, color="#52633d")
        st.caption("Map pins show the driver's last shared location and your delivery pin. Road-route ETA requires a routing service.")
    elif order["status"] == "Delivered":
        st.success("Your order has been marked as delivered.")
    elif order["status"] in ["Picked up", "Out for delivery"]:
        st.info("Your order is with the driver. The restaurant has not added both map locations yet.")
    else:
        st.info("Your order is being processed. Driver tracking will appear after pickup and location sharing.")

# -------------------- SESSION --------------------
if "theme" not in st.session_state: st.session_state.theme = "Light"
if "cart" not in st.session_state: st.session_state.cart = {}
if "admin" not in st.session_state: st.session_state.admin = False
if "page" not in st.session_state: st.session_state.page = "Home"
if "mobile_menu_open" not in st.session_state: st.session_state.mobile_menu_open = False

# Admin access is intentionally not linked from the public interface.
# Open the private route directly with ?admin=1, then authenticate.
if "admin_route_enabled" not in st.session_state:
    st.session_state.admin_route_enabled = False
try:
    if st.query_params.get("admin") == "1" and not st.session_state.admin_route_enabled:
        st.session_state.admin_route_enabled = True
        st.session_state.page = "Admin"
except Exception:
    pass

# Apply theme before rendering all page elements so desktop, tablet and mobile
# receive the same CSS on every rerun.
set_theme_css(st.session_state.theme)

# Separate desktop and mobile headers. This avoids overlap and keeps the
# mobile controls on their own row below the logo.
with st.container(key="desktop_header"):
    desktop_brand_col, desktop_theme_col = st.columns([1, 0.08], gap="small", vertical_alignment="center")
    with desktop_brand_col:
        st.markdown('<div class="brand">NAIJA <span>TABLE</span></div><div class="brand-sub">NIGERIAN KITCHEN & GRILL</div>', unsafe_allow_html=True)
    with desktop_theme_col:
        with st.container(key="desktop_theme"):
            desktop_icon = "☾" if st.session_state.theme == "Light" else "☀"
            if st.button(desktop_icon, key="desktop_theme_toggle", help="Switch light/dark mode"):
                st.session_state.theme = "Dark" if st.session_state.theme == "Light" else "Light"
                st.rerun()

with st.container(key="mobile_header"):
    with st.container(key="mobile_brand"):
        st.markdown('<div class="brand">NAIJA <span>TABLE</span></div><div class="brand-sub">NIGERIAN KITCHEN & GRILL</div>', unsafe_allow_html=True)
    with st.container(key="mobile_controls"):
        mobile_menu_col, mobile_theme_col = st.columns([1, 1], gap="small", vertical_alignment="center")
        with mobile_menu_col:
            with st.container(key="mobile_menu"):
                menu_icon = "×" if st.session_state.mobile_menu_open else "☰"
                if st.button(menu_icon, key="mobile_menu_toggle", help="Open navigation" if not st.session_state.mobile_menu_open else "Close navigation"):
                    st.session_state.mobile_menu_open = not st.session_state.mobile_menu_open
                    st.rerun()
        with mobile_theme_col:
            mobile_icon = "☾" if st.session_state.theme == "Light" else "☀"
            if st.button(mobile_icon, key="mobile_theme_toggle", help="Switch light/dark mode"):
                st.session_state.theme = "Dark" if st.session_state.theme == "Light" else "Light"
                st.rerun()

# A simple conditional navigation panel replaces Streamlit's popover. This avoids
# the default "Expand more / Expand less" accessibility text in the mobile UI.
if st.session_state.mobile_menu_open:
    with st.container(key="mobile_navigation_panel", border=True):
        mobile_items = [("Home", "Home"), ("Our Menu", "Menu"), ("Contact", "Contact"), ("Track Order", "Track"), ("Basket", "Cart")]
        mobile_cols = st.columns(len(mobile_items))
        for col, (label, key) in zip(mobile_cols, mobile_items):
            with col:
                nav_label = label + (f" ({sum(st.session_state.cart.values())})" if key == "Cart" and st.session_state.cart else "")
                if st.button(nav_label, key=f"mobile_{key}", use_container_width=True):
                    st.session_state.page = key
                    st.session_state.mobile_menu_open = False
                    st.rerun()

with st.container(key="desktop_nav"):
    nav_cols = st.columns(5)
    nav_items = [("Home", "Home"), ("Our Menu", "Menu"), ("Contact", "Contact"), ("Track Order", "Track"), ("Basket", "Cart")]
    for col, (label, key) in zip(nav_cols, nav_items):
        with col:
            nav_label = label + (f" ({sum(st.session_state.cart.values())})" if key == "Cart" and st.session_state.cart else "")
            if st.button(nav_label, key=f"nav_{key}", use_container_width=True):
                st.session_state.page = key
                st.session_state.mobile_menu_open = False
                st.rerun()

page = st.session_state.page
if page == "About":
    page = "Home"
    st.session_state.page = "Home"

# -------------------- HOME --------------------
if page == "Home":
    st.markdown("""
    <div class="hero">
      <div class="eyebrow">A TASTE TO REMEMBER</div>
      <h1>Good food<br>Beautiful moments.<br>Memories that last.</h1>
      <p>From the first spoonful to the very last bite, enjoy the comforting flavours of Nigerian cooking, prepared with care and served with love.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="section-kicker">COOKED WITH CARE. SERVED WITH GENEROSITY.</div>', unsafe_allow_html=True)
    st.markdown("## From our kitchen")
    st.write("A few of the dishes our table is known for. Explore the full menu for soups, rice, small chops, sides and more.")
    featured_names = ["Jollof Rice","Egusi Soup","Small Chops","Yam Porridge"]
    menu = get_menu(True)
    featured = [x for x in menu if x["name"] in featured_names]
    for idx in range(0, len(featured), 2):
        left, right = st.columns(2, gap="medium")
        with left:
            render_food_item(featured[idx], "home")
        if idx + 1 < len(featured):
            with right:
                render_food_item(featured[idx + 1], "home")
    if st.button("Explore the full menu →"):
        st.session_state.page = "Menu"; st.rerun()

# -------------------- MENU --------------------
elif page == "Menu":
    st.markdown('<div class="section-kicker">FROM OUR KITCHEN TO YOU</div>', unsafe_allow_html=True)
    st.title("Explore the menu")
    st.write("Find something you love. All prices are displayed in Nigerian naira.")
    menu = get_menu(True)
    cats = ["All"] + sorted(set(x["category"] for x in get_menu()))
    f1,f2 = st.columns([2,1])
    with f1: search = st.text_input("Search the menu", placeholder="Search jollof, egusi, plantain...")
    with f2: category = st.selectbox("Category", cats)
    shown = [x for x in menu if (category=="All" or x["category"]==category) and (search.lower() in x["name"].lower() or search.lower() in x["description"].lower())]
    if not shown:
        st.info("No available items match your search.")
    for idx in range(0, len(shown), 2):
        left, right = st.columns(2, gap="medium")
        with left:
            render_food_item(shown[idx], "menu", show_quantity=True)
        if idx + 1 < len(shown):
            with right:
                render_food_item(shown[idx + 1], "menu", show_quantity=True)

# -------------------- CART --------------------
elif page == "Cart":
    st.title("Your basket")
    all_items = {x["id"]:x for x in get_menu()}
    if not st.session_state.cart:
        st.info("Your basket is empty. Explore the menu to add something.")
        if st.button("Browse menu"): st.session_state.page="Menu"; st.rerun()
    else:
        total = 0
        for item_id, qty in list(st.session_state.cart.items()):
            item = all_items.get(item_id)
            if not item or not item["available"]:
                st.warning(f'{item["name"] if item else "An item"} is currently unavailable and cannot be ordered.')
                continue
            row = st.columns([3,1,1,1])
            row[0].write(f"**{item['name']}**")
            row[1].write(f"× {qty}")
            row[2].write(money(item["price"]*qty))
            if row[3].button("Remove", key=f"remove_{item_id}"):
                del st.session_state.cart[item_id]; st.rerun()
            total += item["price"]*qty
        st.divider()
        st.subheader(f"Subtotal: {money(total)}")
        st.caption("Delivery fees, if applicable, are confirmed by the restaurant.")
        st.markdown("### Checkout details")
        with st.form("checkout_form"):
            customer = st.text_input("Your name")
            phone = st.text_input("Phone number")
            address = st.text_area("Delivery address / pickup note")
            st.caption("For map-based delivery tracking, enter the delivery pin coordinates from your map app. These can also be added later by the restaurant.")
            coord1, coord2 = st.columns(2)
            with coord1:
                customer_lat = st.number_input("Delivery latitude (optional)", min_value=-90.0, max_value=90.0, value=0.0, format="%.6f")
            with coord2:
                customer_lon = st.number_input("Delivery longitude (optional)", min_value=-180.0, max_value=180.0, value=0.0, format="%.6f")
            submitted = st.form_submit_button("Place order")
        if submitted:
            if not customer.strip() or not phone.strip():
                st.error("Please enter your name and phone number.")
            elif total <= 0:
                st.error("Your basket has no available items.")
            else:
                summary = []
                for item_id,qty in st.session_state.cart.items():
                    item = all_items.get(item_id)
                    if item and item["available"]:
                        summary.append(f"{item['name']} x{qty} ({money(item['price']*qty)})")
                conn=db()
                lat_value = customer_lat if (customer_lat != 0.0 or customer_lon != 0.0) else None
                lon_value = customer_lon if lat_value is not None else None
                cur = conn.execute("INSERT INTO orders(customer,phone,address,items,total,status,created_at,customer_lat,customer_lon) VALUES(?,?,?,?,?,?,?,?,?)",
                             (customer.strip(),phone.strip(),address.strip()," | ".join(summary),total,"New",datetime.now().strftime("%Y-%m-%d %H:%M"),lat_value,lon_value))
                conn.commit()
                new_order_id = cur.lastrowid
                conn.close()
                st.session_state.cart={}
                st.success(f"Your order has been submitted. Your order number is #{new_order_id}. Save it to track delivery.")
                st.info("Once a driver is assigned and their location is shared, you can view delivery progress under Track Order.")
                st.balloons()

# -------------------- TRACK ORDER --------------------
elif page == "Track":
    st.markdown('<div class="section-kicker">YOUR ORDER, ON ITS WAY</div>', unsafe_allow_html=True)
    st.title("Track your delivery")
    st.write("Enter your order number and phone number to view its latest status and driver location.")
    with st.form("track_order_form"):
        order_number = st.number_input("Order number", min_value=1, step=1, value=1)
        track_phone = st.text_input("Phone number used at checkout")
        track_submit = st.form_submit_button("Find my order")
    if track_submit:
        st.session_state["tracked_order_id"] = int(order_number)
        st.session_state["tracked_order_phone"] = track_phone.strip()
    if st.session_state.get("tracked_order_id") and st.session_state.get("tracked_order_phone"):
        render_live_tracking(st.session_state["tracked_order_id"], st.session_state["tracked_order_phone"])

# -------------------- CONTACT --------------------
elif page == "Contact":
    st.markdown('<div class="section-kicker">WE WOULD LOVE TO HEAR FROM YOU</div>', unsafe_allow_html=True)
    st.title("Contact the kitchen")
    st.write("Questions, orders or a special request? We would be glad to hear from you.")
    opening_time, closing_time = get_restaurant_hours()
    opening_label = format_clock(opening_time)
    closing_label = format_clock(closing_time)
    st.markdown(f'''<div class="info-panel">
      <h3>Naija Table</h3>
      <div class="contact-row"><span class="contact-icon"><span class="material-symbols-rounded">location_on</span></span><div><strong>Visit us</strong><small>Restaurant address to be added</small></div></div>
      <div class="contact-row"><span class="contact-icon"><span class="material-symbols-rounded">call</span></span><div><strong>Call us</strong><small>Phone number to be added</small></div></div>
      <div class="contact-row"><span class="contact-icon"><span class="material-symbols-rounded">mail</span></span><div><strong>Email us</strong><small>Email address to be added</small></div></div>
      <div class="contact-row" style="border-bottom:0"><span class="contact-icon"><span class="material-symbols-rounded">schedule</span></span><div><strong>Opening hours</strong><small>{opening_label} – {closing_label}, daily</small></div></div>
    </div>''', unsafe_allow_html=True)

# -------------------- ADMIN --------------------
elif page == "Admin":
    st.markdown('<div class="section-kicker">RESTAURANT MANAGEMENT</div>', unsafe_allow_html=True)
    st.title("Admin dashboard")
    if not st.session_state.admin:
        with st.container(key="admin_auth"):
            st.write("Sign in to manage your menu and orders.")
            login_tab, reset_tab = st.tabs(["Admin sign in", "Forgot password?"])
            with login_tab:
                with st.form("admin_login"):
                    username = st.text_input("Admin username")
                    password = st.text_input("Admin password", type="password")
                    login = st.form_submit_button("Sign in")
                if login:
                    account = get_admin_account()
                    if account and hmac.compare_digest(username, account["username"]) and verify_password(password, account["salt"], account["password_hash"]):
                        st.session_state.admin = True
                        st.rerun()
                    else:
                        st.error("Incorrect username or password.")
            with reset_tab:
                st.write("Enter the administrator recovery code configured by the website owner, then choose a new password.")
                recovery_code = config_value("ADMIN_RESET_CODE", "RESTAURANT_ADMIN_RESET_CODE")
                if not recovery_code:
                    st.warning("Password recovery has not been configured. The website owner must add ADMIN_RESET_CODE in Streamlit Secrets before this option can be used.")
                with st.form("admin_password_reset"):
                    reset_username = st.text_input("Admin username", key="reset_admin_username")
                    entered_code = st.text_input("Recovery code", type="password")
                    new_password = st.text_input("New password (at least 12 characters)", type="password")
                    confirm_password = st.text_input("Confirm new password", type="password")
                    reset_submit = st.form_submit_button("Reset admin password")
                if reset_submit:
                    account = get_admin_account()
                    if not recovery_code:
                        st.error("Password recovery is not configured. Contact the website owner.")
                    elif not account or not hmac.compare_digest(reset_username, account["username"]):
                        st.error("The admin username is incorrect.")
                    elif not hmac.compare_digest(entered_code, recovery_code):
                        st.error("The recovery code is incorrect.")
                    elif len(new_password) < 12:
                        st.error("Choose a password with at least 12 characters.")
                    elif new_password != confirm_password:
                        st.error("The new passwords do not match.")
                    else:
                        save_admin_password(account["username"], new_password)
                        st.success("Admin password reset. You can now sign in with your new password.")
            st.caption("For deployment, configure ADMIN_USERNAME, ADMIN_PASSWORD and ADMIN_RESET_CODE in Streamlit Community Cloud → App settings → Secrets.")
    else:
        top1,top2,top3=st.columns([2,2,1])
        menu_all=get_menu()
        orders_conn=db()
        orders=orders_conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
        orders_conn.close()
        top1.metric("Menu items",len(menu_all))
        top2.metric("Available items",sum(x["available"] for x in menu_all))
        top3.metric("Orders",len(orders))
        if st.button("Sign out"):
            st.session_state.admin=False; st.rerun()
        tab_menu,tab_add,tab_orders,tab_settings=st.tabs(["Manage menu","Add menu item","Orders","Restaurant settings"])
        with tab_menu:
            st.markdown("#### Menu inventory")
            for item in menu_all:
                with st.container(border=True):
                    image_col,left,mid,price_col,avail_col,del_col=st.columns([0.8,2,1,1,1,1])
                    image_col.image(item_image(item), use_container_width=True)
                    left.write(f"**{item['name']}**")
                    mid.caption(item["category"])
                    price_col.write(money(item["price"]))
                    new_avail=avail_col.toggle("Available",value=bool(item["available"]),key=f"availability_{item['id']}")
                    if int(new_avail)!=item["available"]:
                        conn=db(); conn.execute("UPDATE menu SET available=? WHERE id=?",(int(new_avail),item["id"])); conn.commit(); conn.close()
                        st.rerun()
                    if del_col.button("Delete",key=f"delete_{item['id']}"):
                        conn=db(); conn.execute("DELETE FROM menu WHERE id=?",(item["id"],)); conn.commit(); conn.close()
                        st.rerun()
                    with st.expander("Edit item"):
                        with st.form(f"edit_{item['id']}"):
                            en=st.text_input("Name",item["name"])
                            ec=st.selectbox("Category",["Soups","Rice","Snacks","Drinks","Sides","Meat","Yam"],index=["Soups","Rice","Snacks","Drinks","Sides","Meat","Yam"].index(item["category"]) if item["category"] in ["Soups","Rice","Snacks","Drinks","Sides","Meat","Yam"] else 0)
                            ed=st.text_area("Description",item["description"])
                            ep=st.number_input("Price (₦)",min_value=0,value=int(item["price"]),step=100)
                            ei=st.text_input("Food image URL (optional)",item["image_url"])
                            upload_edit=st.file_uploader("Or upload a food image",type=["png","jpg","jpeg","webp"],key=f"edit_image_{item['id']}")
                            save=st.form_submit_button("Save changes")
                        if save:
                            if upload_edit:
                                ei=save_uploaded_image(upload_edit)
                            conn=db(); conn.execute("UPDATE menu SET name=?,category=?,description=?,price=?,image_url=? WHERE id=?",(en,ec,ed,int(ep),ei,item["id"])); conn.commit(); conn.close()
                            st.success("Menu item updated."); st.rerun()
        with tab_add:
            with st.form("add_item",clear_on_submit=True):
                name=st.text_input("Food / drink name")
                category=st.selectbox("Category",["Soups","Rice","Snacks","Drinks","Sides","Meat","Yam"])
                description=st.text_area("Description")
                price=st.number_input("Price (₦)",min_value=0,value=1000,step=100)
                image_url=st.text_input("Food image URL (optional)")
                upload_new=st.file_uploader("Upload food image",type=["png","jpg","jpeg","webp"])
                available=st.checkbox("Available for ordering",value=True)
                add=st.form_submit_button("Add to menu")
            if add:
                if not name.strip(): st.error("Enter an item name.")
                else:
                    if upload_new:
                        image_url=save_uploaded_image(upload_new)
                    conn=db(); conn.execute("INSERT INTO menu(name,category,description,price,available,image_url) VALUES(?,?,?,?,?,?)",(name.strip(),category,description.strip(),int(price),int(available),image_url.strip())); conn.commit(); conn.close()
                    st.success("Menu item added."); st.rerun()
        with tab_orders:
            st.markdown("#### Customer orders")
            if not orders: st.info("No orders have been placed yet.")
            for order in orders:
                with st.expander(f"Order #{order['id']} · {order['customer']} · {money(order['total'])} · {order['status']}"):
                    st.write(f"**Phone:** {order['phone']}")
                    st.write(f"**Address / note:** {order['address'] or 'Not provided'}")
                    st.write(f"**Items:** {order['items']}")
                    st.write(f"**Placed:** {order['created_at']}")
                    statuses=["New","Confirmed","Preparing","Ready","Picked up","Out for delivery","Delivered","Cancelled"]
                    idx=statuses.index(order["status"]) if order["status"] in statuses else 0
                    new_status=st.selectbox("Order status",statuses,index=idx,key=f"status_{order['id']}")
                    if st.button("Update status",key=f"update_order_{order['id']}"):
                        conn=db(); conn.execute("UPDATE orders SET status=? WHERE id=?",(new_status,order["id"])); conn.commit(); conn.close()
                        st.success("Order status updated."); st.rerun()
                    if new_status in ["Picked up", "Out for delivery"]:
                        st.markdown("**Driver location update**")
                        st.caption("Enter the driver's current coordinates. Customers will see the latest saved position on the Track Order page.")
                        dl1, dl2 = st.columns(2)
                        with dl1:
                            driver_lat = st.number_input("Driver latitude", min_value=-90.0, max_value=90.0, value=0.0, format="%.6f", key=f"driver_lat_{order['id']}")
                        with dl2:
                            driver_lon = st.number_input("Driver longitude", min_value=-180.0, max_value=180.0, value=0.0, format="%.6f", key=f"driver_lon_{order['id']}")
                        if st.button("Save driver location", key=f"save_driver_{order['id']}"):
                            conn=db()
                            conn.execute("INSERT INTO delivery_tracking(order_id,driver_lat,driver_lon,updated_at) VALUES(?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET driver_lat=excluded.driver_lat, driver_lon=excluded.driver_lon, updated_at=excluded.updated_at",
                                         (order["id"], float(driver_lat), float(driver_lon), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            conn.commit(); conn.close()
                            st.success("Driver location saved."); st.rerun()
        with tab_settings:
            st.markdown("#### Restaurant opening hours")
            current_open, current_close = get_restaurant_hours()
            with st.form("restaurant_hours_form"):
                open_value = st.time_input("Opening time", value=datetime.strptime(current_open, "%H:%M").time())
                close_value = st.time_input("Closing time", value=datetime.strptime(current_close, "%H:%M").time())
                save_hours = st.form_submit_button("Save opening hours")
            if save_hours:
                if open_value == close_value:
                    st.error("Opening and closing times cannot be the same.")
                else:
                    conn = db()
                    conn.execute("INSERT INTO restaurant_settings(setting_key,setting_value) VALUES('opening_time',?) ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value", (open_value.strftime("%H:%M"),))
                    conn.execute("INSERT INTO restaurant_settings(setting_key,setting_value) VALUES('closing_time',?) ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value", (close_value.strftime("%H:%M"),))
                    conn.commit(); conn.close()
                    st.success("Restaurant opening hours updated.")
                    st.rerun()
            st.divider()
            st.markdown("#### Admin password")
            st.caption("Change your password while signed in. Use at least 12 characters.")
            with st.form("admin_change_password_form"):
                current_password = st.text_input("Current password", type="password")
                changed_password = st.text_input("New password", type="password")
                changed_password_confirm = st.text_input("Confirm new password", type="password")
                change_password_submit = st.form_submit_button("Update admin password")
            if change_password_submit:
                account = get_admin_account()
                if not account or not verify_password(current_password, account["salt"], account["password_hash"]):
                    st.error("Your current password is incorrect.")
                elif len(changed_password) < 12:
                    st.error("Choose a password with at least 12 characters.")
                elif changed_password != changed_password_confirm:
                    st.error("The new passwords do not match.")
                else:
                    save_admin_password(account["username"], changed_password)
                    st.success("Your admin password has been updated.")

st.markdown("""
<div class="footer">
  <div class="footer-tagline">NAIJA TABLE · GOOD FOOD, GOOD COMPANY</div>
  <div class="footer-copyright">© 2026 Naija Table.</div>
  <a class="footer-admin-link" href="?admin=1" target="_self">ADMIN LOGIN</a>
</div>
""", unsafe_allow_html=True)
