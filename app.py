import os
import sqlite3
import hashlib
import math
import hmac
import html
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
import secrets

import streamlit as st
import streamlit.components.v1 as components

RIDER_COMPONENT = components.declare_component(
    "amala_rider_gps",
    path=str(Path(__file__).parent / "rider_location_component")
)

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "restaurant.db"
UPLOAD_DIR = APP_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Amala T’Ó Dùn | The Authentic Taste of Home", page_icon="🍲", layout="wide",
                   initial_sidebar_state="collapsed")


# -------------------- DATABASE --------------------
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS menu
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       name
                       TEXT
                       NOT
                       NULL,
                       category
                       TEXT
                       NOT
                       NULL,
                       description
                       TEXT
                       DEFAULT
                       '',
                       price
                       INTEGER
                       NOT
                       NULL,
                       available
                       INTEGER
                       DEFAULT
                       1,
                       image_url
                       TEXT
                       DEFAULT
                       ''
                   )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS menu_categories
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       name
                       TEXT
                       NOT
                       NULL
                       COLLATE
                       NOCASE
                       UNIQUE
                   )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS orders
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       customer
                       TEXT
                       NOT
                       NULL,
                       phone
                       TEXT
                       NOT
                       NULL,
                       address
                       TEXT
                       DEFAULT
                       '',
                       items
                       TEXT
                       NOT
                       NULL,
                       total
                       INTEGER
                       NOT
                       NULL,
                       status
                       TEXT
                       DEFAULT
                       'New',
                       created_at
                       TEXT
                       NOT
                       NULL,
                       customer_lat
                       REAL,
                       customer_lon
                       REAL
                   )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS delivery_tracking
                   (
                       order_id
                       INTEGER
                       PRIMARY
                       KEY,
                       driver_lat
                       REAL,
                       driver_lon
                       REAL,
                       updated_at
                       TEXT
                       NOT
                       NULL
                       DEFAULT
                       ''
                   )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS restaurant_settings
                   (
                       setting_key
                       TEXT
                       PRIMARY
                       KEY,
                       setting_value
                       TEXT
                       NOT
                       NULL
                   )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS admin_auth
    (
        id
        INTEGER
        PRIMARY
        KEY
        CHECK
                   (
        id =
        1
                   ),
        username TEXT NOT NULL,
        salt TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        updated_at TEXT NOT NULL
        )""")
    cur.execute("INSERT OR IGNORE INTO restaurant_settings(setting_key, setting_value) VALUES('opening_time','00:00')")
    cur.execute("INSERT OR IGNORE INTO restaurant_settings(setting_key, setting_value) VALUES('closing_time','23:59')")
    cur.executemany("INSERT OR IGNORE INTO restaurant_settings(setting_key, setting_value) VALUES(?,?)",
                    [("whatsapp_number", ""), ("contact_phone", ""), ("instagram_url", ""), ("tiktok_url", "")])
    # Safe migration for databases created by earlier project versions.
    order_columns = {row[1] for row in cur.execute("PRAGMA table_info(orders)").fetchall()}
    if "customer_lat" not in order_columns:
        cur.execute("ALTER TABLE orders ADD COLUMN customer_lat REAL")
    if "customer_lon" not in order_columns:
        cur.execute("ALTER TABLE orders ADD COLUMN customer_lon REAL")
    if "fulfilment_type" not in order_columns:
        cur.execute("ALTER TABLE orders ADD COLUMN fulfilment_type TEXT NOT NULL DEFAULT 'Not specified'")
    if "rider_token" not in order_columns:
        cur.execute("ALTER TABLE orders ADD COLUMN rider_token TEXT")
    count = cur.execute("SELECT COUNT(*) FROM menu").fetchone()[0]
    if count == 0:
        items = [
            ("Egusi Soup", "Soups", "Rich melon-seed soup with traditional spices.", 4500),
            ("Efo Riro", "Soups", "A vibrant Yoruba spinach stew.", 4000),
            ("Okro Soup", "Soups", "Fresh okro simmered in a flavourful sauce.", 3500),
            ("Afang Soup", "Soups", "A hearty vegetable soup with afang leaves.", 5000),
            ("Bitterleaf Soup", "Soups", "Traditional bitterleaf soup, slow-cooked.", 4500),
            ("Jollof Rice", "Rice", "Smoky party-style Nigerian jollof.", 3500),
            ("Coconut Rice", "Rice", "Fragrant rice cooked in coconut milk.", 4000),
            ("Fried Rice", "Rice", "Colourful fried rice with vegetables.", 3500),
            ("Special Rice", "Rice", "House special rice with signature seasoning.", 5000),
            ("Meat Pie", "Snacks", "Golden pastry with a savoury filling.", 1200),
            ("Sausage Roll", "Snacks", "Flaky pastry wrapped around sausage.", 1000),
            ("Fish Pie", "Snacks", "Crisp pastry with a seasoned fish filling.", 1300),
            ("Puff Puff (6 pcs)", "Snacks", "Soft, golden Nigerian puff puff.", 1500),
            ("Small Chops", "Snacks", "A tasty mix of party favourites.", 4500),
            ("Bottled Water", "Drinks", "Chilled bottled water.", 500),
            ("Coca-Cola", "Drinks", "Chilled Coca-Cola.", 700),
            ("Fanta", "Drinks", "Chilled orange Fanta.", 700),
            ("Sprite", "Drinks", "Chilled Sprite.", 700),
            ("Energy Drink", "Drinks", "Chilled energy drink.", 1500),
            ("Fried Plantain", "Sides", "Sweet ripe plantain, fried golden.", 1500),
            ("Fresh Salad", "Sides", "Fresh, crunchy house salad.", 1800),
            ("French Fries", "Sides", "Crispy golden fries.", 2000),
            ("Boiled Egg", "Sides", "One boiled egg.", 500),
            ("Grilled Chicken", "Meat", "Well-seasoned grilled chicken portion.", 3500),
            ("Goat Meat", "Meat", "Tender, spicy goat meat.", 3000),
            ("Beef", "Meat", "Seasoned beef portion.", 2000),
            ("Turkey", "Meat", "Juicy turkey portion.", 4000),
            ("Boiled White Yam", "Yam", "Soft boiled yam portions.", 2500),
            ("Yam Porridge", "Yam", "Rich yam porridge with palm oil and spices.", 3500),
        ]
        cur.executemany("INSERT INTO menu(name,category,description,price) VALUES(?,?,?,?)", items)
    # Keep category records persistent and migrate categories already used by menu items.
    cur.execute(
        "INSERT OR IGNORE INTO menu_categories(name) SELECT DISTINCT TRIM(category) FROM menu WHERE TRIM(category) <> ''")
    # Add the new restaurant's menu groupings without deleting existing categories or menu data.
    cur.executemany("INSERT OR IGNORE INTO menu_categories(name) VALUES(?)", [
        ("Amala & Swallow",), ("Native Soups",), ("Rice",), ("Ofada",),
        ("Proteins",), ("Breakfast",), ("Local Drinks",)
    ])
    # Brief-based catalogue placeholders: prices are intentionally zero and items
    # unavailable until the restaurant confirms prices and enables each item.
    brief_items = [
        ("Amala", "Amala & Swallow"), ("Eba", "Amala & Swallow"),
        ("Pounded Yam", "Amala & Swallow"), ("Semo", "Amala & Swallow"),
        ("Fufu", "Amala & Swallow"), ("Ewedu", "Native Soups"),
        ("Gbegiri", "Native Soups"), ("Egusi Soup", "Native Soups"),
        ("Efo Riro", "Native Soups"), ("Ogbono Soup", "Native Soups"),
        ("Jollof Rice", "Rice"), ("Fried Rice", "Rice"),
        ("White Rice", "Rice"), ("Ofada Rice", "Ofada"),
        ("Ayamase Sauce", "Ofada"), ("Assorted Meat", "Proteins"),
        ("Goat Meat", "Proteins"), ("Fish", "Proteins"), ("Ponmo", "Proteins"),
        ("Traditional Breakfast", "Breakfast"), ("Local Drinks", "Local Drinks")
    ]
    for item_name, item_category in brief_items:
        exists = cur.execute("SELECT 1 FROM menu WHERE name=? COLLATE NOCASE", (item_name,)).fetchone()
        if not exists:
            cur.execute("INSERT INTO menu(name,category,description,price,available) VALUES(?,?,?,?,0)",
                        (item_name, item_category, "Price to be confirmed before launch.", 0))
    category_migrations = {
        "Egusi Soup": "Native Soups", "Efo Riro": "Native Soups",
        "Okro Soup": "Native Soups", "Ogbono Soup": "Native Soups",
        "Goat Meat": "Proteins", "Beef": "Proteins", "Turkey": "Proteins",
        "Grilled Chicken": "Proteins", "Fish": "Proteins", "Ponmo": "Proteins",
        "Jollof Rice": "Rice", "Fried Rice": "Rice", "White Rice": "Rice",
    }
    for existing_name, new_category in category_migrations.items():
        cur.execute("UPDATE menu SET category=? WHERE name=? COLLATE NOCASE", (new_category, existing_name))
    conn.commit()
    conn.close()


def get_categories():
    conn = db()
    rows = conn.execute("SELECT name FROM menu_categories ORDER BY name COLLATE NOCASE").fetchall()
    conn.close()
    return [row["name"] for row in rows]


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
    conn.execute("""INSERT INTO admin_auth(id, username, salt, password_hash, updated_at)
                    VALUES (1, ?, ?, ?, ?) ON CONFLICT(id) DO
                    UPDATE
                    SET
                        username=excluded.username, salt=excluded.salt, password_hash=excluded.password_hash, updated_at=excluded.updated_at""",
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


def get_setting(key, default=""):
    conn = db()
    row = conn.execute("SELECT setting_value FROM restaurant_settings WHERE setting_key=?", (key,)).fetchone()
    conn.close()
    return row["setting_value"] if row else default


def public_app_url():
    return get_setting("public_website_url").strip().rstrip("/")


def rider_tracking_url(token):
    base_url = public_app_url()
    return f"{base_url}/?rider={quote(token)}" if base_url else ""


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
    bg = "#18251b" if dark else "#f5efdf"
    panel = "#243328" if dark else "#fff9eb"
    text = "#f6f0df" if dark else "#2d281e"
    muted = "#d0c6aa" if dark else "#71634d"
    border = "#465442" if dark else "#d9c9a7"
    alert_bg = "#314b35" if dark else "#3f613f"
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');\n    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400,1,0&display=swap');
    :root {{ color-scheme: {'dark' if dark else 'light'}; }}
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMarkdownContainer"],
    button, input, textarea, select, label, p, span, div {{ font-family:'Poppins',sans-serif !important; }}
    /* Keep Streamlit's Material Symbols font for every built-in icon.
       This must be global: expanders, password visibility controls, tabs,
       navigation and admin widgets all render icons outside admin_auth. */
    [data-testid="stIconMaterial"],
    [data-testid="stIconMaterial"] *,
    span[data-testid="stIconMaterial"],
    .material-symbols-rounded,
    .material-symbols-outlined,
    .material-icons,
    [class*="material-symbols"] {{
        font-family:'Material Symbols Rounded' !important;
        font-weight:normal !important;
        font-style:normal !important;
        letter-spacing:normal !important;
        text-transform:none !important;
        white-space:nowrap !important;
        direction:ltr !important;
        font-feature-settings:'liga' 1 !important;
        font-variation-settings:'FILL' 1,'wght' 400,'GRAD' 0,'opsz' 24 !important;
        -webkit-font-feature-settings:'liga' !important;
        -webkit-font-smoothing:antialiased !important;
    }}
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
    .brand-link {{ display:inline-block !important; color:inherit !important; text-decoration:none !important; cursor:pointer; }}
    .brand-link:hover {{ opacity:.86; text-decoration:none !important; }}
    .brand {{ font-size:1.25rem; font-weight:800; letter-spacing:-1px; color:{text}; }}
    .brand span {{ color:#b88a32; }}
    .brand-sub {{ color:{muted}; font-size:.59rem; letter-spacing:2px; margin-top:-2px; }}
    .section-kicker {{ text-transform:uppercase; letter-spacing:2px; color:#b88a32; font-weight:600; font-size:.66rem; }}
    .hero {{ background:linear-gradient(90deg,rgba(17,22,16,.86),rgba(17,22,16,.22)),url('https://images.unsplash.com/photo-1604329760661-e71dc83f8f26?auto=format&fit=crop&w=1800&q=85'); background-size:cover; background-position:center 52%; min-height:390px; padding:clamp(28px,5vw,64px); display:flex; flex-direction:column; justify-content:center; margin:14px 0 34px; border-radius:5px; }}
    .hero h1 {{ color:#fff !important; font-size:clamp(2rem,4vw,3.35rem) !important; line-height:1.22; max-width:650px; margin:.55rem 0 1rem; font-weight:600 !important; white-space:normal; }}
    .hero p {{ color:#fff !important; max-width:540px; font-size:.9rem; }}
    .hero .eyebrow {{ color:#f0d2a9 !important; text-transform:uppercase; letter-spacing:2px; font-weight:600; font-size:.7rem; }}
    [class*="st-key-food_card_"] [data-testid="stVerticalBlockBorderWrapper"] {{ background:{panel} !important; border:1px solid {border} !important; border-radius:7px !important; padding:5px !important; }}
    [class*="st-key-food_card_"] [data-testid="stVerticalBlock"] {{ gap:.35rem !important; }}
    [class*="st-key-food_card_"] h3 {{ font-size:.92rem !important; margin:1px 0 3px; font-weight:600 !important; }}
    [class*="st-key-food_card_"] p {{ color:{muted}; font-size:.72rem; line-height:1.45; margin:0 0 4px; }}
    .food-category {{ display:inline-block; color:#b88a32; font-size:.6rem; font-weight:600; letter-spacing:1px; text-transform:uppercase; }}
    .price {{ font-weight:600; font-size:.9rem; color:{'#e2bd63' if dark else '#8a5b27'}; }}
    .available {{ color:#79b777; font-size:.68rem; font-weight:600; }}
    .unavailable {{ color:#f09a8d; font-size:.68rem; font-weight:600; }}
    .info-panel {{ background:{panel}; border:1px solid {border}; border-radius:5px; padding:18px; }}
    div.stButton > button, div.stFormSubmitButton > button, div[data-testid="stFormSubmitButton"] button {{ border-radius:4px; border:1px solid #3f613f !important; background:#3f613f !important; color:#fff !important; font-weight:500; padding:.38rem .72rem; min-height:2.15rem; font-size:.78rem !important; }}
    div.stButton > button *, div.stFormSubmitButton > button *, div[data-testid="stFormSubmitButton"] button * {{ color:#fff !important; }}
    div.stButton > button:hover, div.stFormSubmitButton > button:hover, div[data-testid="stFormSubmitButton"] button:hover {{ background:#2e4a32 !important; color:#fff !important; border-color:#2e4a32 !important; }}
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
    .footer-admin-link {{ display:inline-block; color:{'#e5c29b' if dark else '#3f613f'} !important; font-size:.66rem; font-weight:600; letter-spacing:1.4px; text-decoration:none !important; border:1px solid {border}; border-radius:3px; padding:7px 13px; transition:background .2s ease,border-color .2s ease; }}
    .footer-admin-link:hover {{ background:{panel}; border-color:#b88a32; color:{text} !important; }}
    /* HEADER LAYOUT: separate desktop and phone structures avoid overlap. */
    .st-key-desktop_header {{
      display:block !important; width:100% !important; margin:0 0 10px !important;
      padding:34px 0 10px !important; position:relative !important; z-index:5 !important;
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
      /* Keep the hamburger first and the theme toggle immediately to its right. */
      .st-key-mobile_controls [data-testid="stVerticalBlock"] {{
        display:flex !important; flex-direction:row !important; flex-wrap:nowrap !important;
        align-items:center !important; justify-content:flex-start !important;
        gap:4pt !important; width:100% !important;
      }}
      .st-key-mobile_controls [data-testid="stElementContainer"] {{
        flex:0 0 42px !important; width:42px !important; min-width:42px !important;
        max-width:42px !important; margin:0 !important; padding:0 !important;
      }}
      .st-key-mobile_controls [data-testid="stElementContainer"] > div {{
        width:42px !important; min-width:42px !important; max-width:42px !important;
        margin:0 !important; padding:0 !important;
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
    .contact-icon {{ width:38px; height:38px; display:flex; align-items:center; justify-content:center; border-radius:10px; background:{'#35402f' if dark else '#edf0e7'}; color:{'#e5c29b' if dark else '#3f613f'}; flex-shrink:0; }}
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


.social-icon-link,.social-icon-muted{{display:inline-flex;align-items:center;gap:10px;text-decoration:none;font-weight:600;color:inherit;padding:10px 0}}
.social-icon-link:hover{{text-decoration:underline}}
.social-icon-muted{{opacity:.55}}

    /* Pickup / Delivery selector: button-style cards with clear theme contrast */
    .st-key-checkout_fulfilment_type [data-testid="stRadio"] [role="radiogroup"] {{
        display:flex !important;
        flex-wrap:wrap !important;
        gap:12px !important;
    }}
    .st-key-checkout_fulfilment_type [data-testid="stRadio"] [role="radiogroup"] label {{
        display:flex !important;
        align-items:center !important;
        justify-content:center !important;
        min-width:148px !important;
        min-height:48px !important;
        padding:10px 22px !important;
        border:1.5px solid {border} !important;
        border-radius:10px !important;
        background:{panel} !important;
        color:{text} !important;
        cursor:pointer !important;
        transition:background .18s ease,border-color .18s ease,color .18s ease,transform .18s ease,box-shadow .18s ease !important;
    }}
    .st-key-checkout_fulfilment_type [data-testid="stRadio"] [role="radiogroup"] label p,
    .st-key-checkout_fulfilment_type [data-testid="stRadio"] [role="radiogroup"] label span {{
        color:inherit !important;
        font-weight:600 !important;
    }}
    .st-key-checkout_fulfilment_type [data-testid="stRadio"] [role="radiogroup"] label:has(input[type="radio"]:checked) {{
        background:#3f613f !important;
        border-color:#3f613f !important;
        color:#ffffff !important;
        box-shadow:0 3px 10px rgba(20,35,20,.16) !important;
    }}
    .st-key-checkout_fulfilment_type [data-testid="stRadio"] input[type="radio"] {{
        accent-color:#3f613f !important;
    }}
    @media (hover:hover) and (pointer:fine) {{
        .st-key-checkout_fulfilment_type [data-testid="stRadio"] [role="radiogroup"] label:hover {{
            background:#e8d7a9 !important;
            border-color:#b58a36 !important;
            color:#292318 !important;
            transform:translateY(-2px) !important;
            box-shadow:0 5px 14px rgba(35,28,16,.12) !important;
        }}
        .st-key-checkout_fulfilment_type [data-testid="stRadio"] [role="radiogroup"] label:has(input[type="radio"]:checked):hover {{
            background:#b58a36 !important;
            border-color:#b58a36 !important;
            color:#211b10 !important;
        }}
    }}
    @media(max-width:520px) {{
        .st-key-checkout_fulfilment_type [data-testid="stRadio"] [role="radiogroup"] label {{
            min-width:calc(50% - 6px) !important;
            flex:1 1 calc(50% - 6px) !important;
            padding:10px 12px !important;
        }}
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
    "Amala & Swallow": "https://images.unsplash.com/photo-1518977676601-b53f82aba655?auto=format&fit=crop&w=700&q=80",
    "Native Soups": "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=700&q=80",
    "Ofada": "https://images.unsplash.com/photo-1516684732162-798a0062be99?auto=format&fit=crop&w=700&q=80",
    "Proteins": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=700&q=80",
    "Breakfast": "https://images.unsplash.com/photo-1533089860892-a7c6f0a88666?auto=format&fit=crop&w=700&q=80",
    "Local Drinks": "https://images.unsplash.com/photo-1544145945-f90425340c7e?auto=format&fit=crop&w=700&q=80",
}


def item_image(item):
    """Return a usable image source, falling back when a saved upload is missing.

    Older database rows may contain relative upload paths whose files were not
    included in a deployment or were deleted locally. Never pass those missing
    paths to st.image; use the category fallback instead.
    """
    url = (item.get("image_url") or "").strip()
    if url:
        if url.startswith(("https://", "http://", "data:")):
            return url
        # Treat every non-URL value (including uploads/name.jpg and /uploads/name.jpg)
        # as a path relative to the application directory.
        local = Path(url.lstrip("/\\"))
        if not local.is_absolute():
            local = APP_DIR / local
        if local.is_file():
            return str(local)
    category = item.get("category") or "Rice"
    return DEFAULT_IMAGES.get(category, DEFAULT_IMAGES["Rice"])


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
            status_html = '<div class="available">● Available</div>' if item[
                "available"] else '<div class="unavailable">● Currently unavailable</div>'
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
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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
    if order["status"] in ["Picked up", "Out for delivery"] and tracking and tracking["driver_lat"] is not None:
        st.caption(f"Rider's last GPS update: {tracking['updated_at']} · This panel refreshes every 15 seconds.")
        map_data = [{"lat": float(tracking["driver_lat"]), "lon": float(tracking["driver_lon"]), "Location": "Rider"}]
        if order["customer_lat"] is not None and order["customer_lon"] is not None:
            map_data.append({"lat": float(order["customer_lat"]), "lon": float(order["customer_lon"]),
                             "Location": "Delivery point"})
            distance = haversine_km(float(tracking["driver_lat"]), float(tracking["driver_lon"]),
                                    float(order["customer_lat"]), float(order["customer_lon"]))
            st.metric("Straight-line distance to delivery point", f"{distance:.1f} km")
        else:
            st.info(
                "Rider location is visible. The customer did not share a GPS delivery pin, so the exact delivery point cannot be plotted.")
        st.map(map_data, latitude="lat", longitude="lon", size=150, color="#3f613f")
    elif order["status"] in ["Picked up", "Out for delivery"]:
        st.info("Waiting for the rider to open the tracking link and allow GPS access.")
    elif order["status"] == "Delivered":
        st.success("Your order has been marked as delivered.")
    elif order["status"] in ["Picked up", "Out for delivery"]:
        st.info("Your order is with the driver. The restaurant has not added both map locations yet.")
    else:
        st.info("Your order is being processed. Driver tracking will appear after pickup and location sharing.")


# -------------------- RIDER GPS PORTAL --------------------
rider_token_from_url = st.query_params.get("rider", "")
if rider_token_from_url:
    st.title("Amala T’Ó Dùn · Rider location sharing")
    conn = db()
    rider_order = conn.execute(
        "SELECT id, status, fulfilment_type FROM orders WHERE rider_token=?",
        (rider_token_from_url,)
    ).fetchone()
    conn.close()
    if not rider_order:
        st.error("This rider link is invalid or has expired. Please contact the restaurant.")
        st.stop()
    if rider_order["status"] in ["Delivered", "Cancelled"]:
        st.info("Location sharing has ended for this order.")
        st.stop()
    st.write(f"Order #{rider_order['id']} · {rider_order['status']}")
    st.write("Open this page on your phone, tap the button and allow GPS access. Keep the page open during delivery.")
    gps_result = RIDER_COMPONENT(mode="watch", key=f"rider_gps_{rider_order['id']}", default=None)
    if isinstance(gps_result, dict) and gps_result.get("lat") is not None and gps_result.get("lon") is not None:
        conn = db()
        conn.execute(
            """INSERT INTO delivery_tracking(order_id, driver_lat, driver_lon, updated_at)
               VALUES (?, ?, ?, ?) ON CONFLICT(order_id) DO
               UPDATE
               SET
                   driver_lat=excluded.driver_lat, driver_lon=excluded.driver_lon, updated_at=excluded.updated_at""",
            (int(rider_order["id"]), float(gps_result["lat"]), float(gps_result["lon"]),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
        st.success(f"Location received. Last browser update: {gps_result.get('updatedAt', 'just now')}")
    st.caption("Location is shared only while this page is open and GPS permission remains enabled.")
    st.stop()

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
    elif st.query_params.get("home") == "1":
        st.session_state.page = "Home"
        st.query_params.pop("home", None)
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
        st.markdown(
            '<a class="brand-link" href="?home=1" aria-label="Amala T’O Dun home"><div class="brand">AMALA <span>T’Ó DÙN</span></div><div class="brand-sub">YORUBA BUKA · LEKKI</div></a>',
            unsafe_allow_html=True)
    with desktop_theme_col:
        with st.container(key="desktop_theme"):
            desktop_icon = "☾" if st.session_state.theme == "Light" else "☀"
            if st.button(desktop_icon, key="desktop_theme_toggle", help="Switch light/dark mode"):
                st.session_state.theme = "Dark" if st.session_state.theme == "Light" else "Light"
                st.rerun()

with st.container(key="mobile_header"):
    with st.container(key="mobile_brand"):
        st.markdown(
            '<a class="brand-link" href="?home=1" aria-label="Amala T’O Dun home"><div class="brand">AMALA <span>T’Ó DÙN</span></div><div class="brand-sub">YORUBA BUKA · LEKKI</div></a>',
            unsafe_allow_html=True)
    with st.container(key="mobile_controls"):
        menu_icon = "×" if st.session_state.mobile_menu_open else "☰"
        if st.button(menu_icon, key="mobile_menu_toggle",
                     help="Open navigation" if not st.session_state.mobile_menu_open else "Close navigation"):
            st.session_state.mobile_menu_open = not st.session_state.mobile_menu_open
            st.rerun()
        mobile_icon = "☾" if st.session_state.theme == "Light" else "☀"
        if st.button(mobile_icon, key="mobile_theme_toggle", help="Switch light/dark mode"):
            st.session_state.theme = "Dark" if st.session_state.theme == "Light" else "Light"
            st.rerun()

# A simple conditional navigation panel replaces Streamlit's popover. This avoids
# the default "Expand more / Expand less" accessibility text in the mobile UI.
if st.session_state.mobile_menu_open:
    with st.container(key="mobile_navigation_panel", border=True):
        mobile_items = [("Home", "Home"), ("Our Menu", "Menu"), ("Contact", "Contact"), ("Track Order", "Track"),
                        ("Basket", "Cart")]
        mobile_cols = st.columns(len(mobile_items))
        for col, (label, key) in zip(mobile_cols, mobile_items):
            with col:
                nav_label = label + (
                    f" ({sum(st.session_state.cart.values())})" if key == "Cart" and st.session_state.cart else "")
                if st.button(nav_label, key=f"mobile_{key}", use_container_width=True):
                    st.session_state.page = key
                    st.session_state.mobile_menu_open = False
                    st.rerun()

with st.container(key="desktop_nav"):
    nav_cols = st.columns(5)
    nav_items = [("Home", "Home"), ("Our Menu", "Menu"), ("Contact", "Contact"), ("Track Order", "Track"),
                 ("Basket", "Cart")]
    for col, (label, key) in zip(nav_cols, nav_items):
        with col:
            nav_label = label + (
                f" ({sum(st.session_state.cart.values())})" if key == "Cart" and st.session_state.cart else "")
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
      <h1>The Authentic Taste of Home.</h1>
      <p>Amala T’Ó Dùn brings the warmth of a traditional Yoruba buka to Orchid Road, Lekki. Enjoy generous portions, soulful native soups and the familiar flavours of home.</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("## Welcome to Amala T’Ó Dùn")
    st.write(
        "From amala with ewedu and gbegiri to rice, native soups, assorted meats and local drinks, find the food you love, served the way home should taste.")
    featured_names = ["Amala", "Amala with Ewedu & Gbegiri", "Jollof Rice", "Egusi Soup", "Ofada Rice & Ayamase"]
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
        st.session_state.page = "Menu";
        st.rerun()


# -------------------- MENU --------------------
elif page == "Menu":
    st.markdown('<div class="section-kicker">FROM OUR KITCHEN TO YOU</div>', unsafe_allow_html=True)
    st.title("Explore the menu")
    st.write("Find something you love. All prices are displayed in Nigerian naira.")
    menu = get_menu(True)
    cats = ["All"] + sorted(set(x["category"] for x in get_menu()))
    f1, f2 = st.columns([2, 1])
    with f1:
        search = st.text_input("Search the menu", placeholder="Search jollof, egusi, plantain...")
    with f2:
        category = st.selectbox("Category", cats)
    shown = [x for x in menu if (category == "All" or x["category"] == category) and (
                search.lower() in x["name"].lower() or search.lower() in x["description"].lower())]
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
    all_items = {x["id"]: x for x in get_menu()}
    if not st.session_state.cart:
        st.info("Your basket is empty. Explore the menu to add something.")
        if st.button("Browse menu"): st.session_state.page = "Menu"; st.rerun()
    else:
        total = 0
        for item_id, qty in list(st.session_state.cart.items()):
            item = all_items.get(item_id)
            if not item or not item["available"]:
                st.warning(f'{item["name"] if item else "An item"} is currently unavailable and cannot be ordered.')
                continue
            row = st.columns([3, 1, 1, 1])
            row[0].write(f"**{item['name']}**")
            row[1].write(f"× {qty}")
            row[2].write(money(item["price"] * qty))
            if row[3].button("Remove", key=f"remove_{item_id}"):
                del st.session_state.cart[item_id];
                st.rerun()
            total += item["price"] * qty
        st.divider()
        st.subheader(f"Subtotal: {money(total)}")
        st.caption("Delivery fees, if applicable, are confirmed by the restaurant.")
        st.markdown("### Checkout details")
        fulfilment_choice = st.radio(
            "How would you like to receive your order?",
            ["🚚  Delivery", "🛍️  Pickup"],
            horizontal=True,
            key="checkout_fulfilment_type",
        )
        fulfilment_type = "Delivery" if fulfilment_choice.startswith("🚚") else "Pickup"
        customer = st.text_input("Your name", key="checkout_customer_name")
        phone = st.text_input("Phone number", key="checkout_customer_phone")

        if fulfilment_type == "Delivery":
            address = st.text_area("Delivery address", key="checkout_delivery_address")
            st.caption(
                "For the map to show your delivery point, you can share your phone's current location. This is optional and requires your permission.")
            destination_result = RIDER_COMPONENT(mode="once", key="customer_delivery_gps", default=None)
            if isinstance(destination_result, dict) and destination_result.get(
                    "lat") is not None and destination_result.get("lon") is not None:
                st.session_state["delivery_destination_lat"] = float(destination_result["lat"])
                st.session_state["delivery_destination_lon"] = float(destination_result["lon"])
                st.success("Your delivery location has been captured.")
            customer_lat = st.session_state.get("delivery_destination_lat")
            customer_lon = st.session_state.get("delivery_destination_lon")
        else:
            address = st.text_input("Pickup note (optional)", key="checkout_pickup_note")
            customer_lat = None
            customer_lon = None
            st.info("Your order will be prepared for collection at the restaurant.")

        if st.button("Place order", type="primary", key="place_customer_order"):
            if not customer.strip() or not phone.strip():
                st.error("Please enter your name and phone number.")
            elif fulfilment_type == "Delivery" and not address.strip():
                st.error("Please enter your delivery address.")
            elif total <= 0:
                st.error("Your basket has no available items.")
            else:
                summary = []
                for item_id, qty in st.session_state.cart.items():
                    item = all_items.get(item_id)
                    if item and item["available"]:
                        summary.append(f'{item["name"]} x{qty} ({money(item["price"] * qty)})')
                conn = db()
                lat_value = customer_lat
                lon_value = customer_lon
                cur = conn.execute(
                    """INSERT INTO orders
                       (customer, phone, address, items, total, status, created_at, customer_lat, customer_lon,
                        fulfilment_type)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        customer.strip(), phone.strip(), address.strip(), " | ".join(summary),
                        total, "New", datetime.now().strftime("%Y-%m-%d %H:%M"),
                        lat_value, lon_value, fulfilment_type
                    )
                )
                conn.commit()
                new_order_id = cur.lastrowid
                conn.close()
                st.session_state.cart = {}
                st.success(
                    f"Your {fulfilment_type.lower()} order has been submitted. Your order number is #{new_order_id}. Save it to track your order.")
                st.info(
                    "The restaurant will contact you to confirm your order and any applicable delivery arrangements.")

        st.divider()
        st.markdown("### Order through WhatsApp")
        whatsapp_number = get_setting("whatsapp_number").strip().replace("+", "").replace(" ", "").replace("-", "")
        if whatsapp_number:
            whatsapp_lines = [
                "Hello Amala T’Ó Dùn, I would like to place an order:",
                "",
            ]
            for item_id, qty in st.session_state.cart.items():
                item = all_items.get(item_id)
                if item and item["available"]:
                    whatsapp_lines.append(f'{item["name"]} x{qty} — {money(item["price"] * qty)}')
            whatsapp_lines.extend([
                "",
                f"Subtotal: {money(total)}",
                f"Fulfilment: {('Delivery' if st.session_state.get('checkout_fulfilment_type', '🚚  Delivery').startswith('🚚') else 'Pickup')}",
                f"Name: {st.session_state.get('checkout_customer_name', '').strip() or 'To be confirmed'}",
                f"Phone: {st.session_state.get('checkout_customer_phone', '').strip() or 'To be confirmed'}",
            ])
            selected_method = "Delivery" if st.session_state.get("checkout_fulfilment_type", "🚚  Delivery").startswith(
                "🚚") else "Pickup"
            if selected_method == "Delivery":
                current_address = st.session_state.get("checkout_delivery_address", "").strip()
                whatsapp_lines.append(f"Delivery address: {current_address or 'To be confirmed'}")
            else:
                pickup_note = st.session_state.get("checkout_pickup_note", "").strip()
                whatsapp_lines.append(f"Pickup note: {pickup_note or 'None'}")
            whatsapp_message = quote("\\n".join(whatsapp_lines))
            st.link_button(
                "Send basket to WhatsApp",
                f"https://wa.me/{whatsapp_number}?text={whatsapp_message}",
                use_container_width=True,
            )
            st.caption(
                "WhatsApp will open with your basket details ready to send. Your order is not submitted to the website until you use Place order.")
        else:
            st.info(
                "WhatsApp ordering will be available once the admin adds the restaurant's WhatsApp number under Admin → Restaurant settings.")

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
    st.title("Visit Amala T’Ó Dùn")
    st.write("Questions, pickup or delivery enquiries? Reach the restaurant or find us on Orchid Road.")
    phone = get_setting("contact_phone").strip()
    whatsapp = get_setting("whatsapp_number").strip()
    instagram = get_setting("instagram_url").strip()
    tiktok = get_setting("tiktok_url").strip()
    opening_time = get_setting("opening_time").strip() or "00:00"
    closing_time = get_setting("closing_time").strip() or "23:59"
    if opening_time == "00:00" and closing_time in ("23:59", "00:00"):
        hours_label = "Open 24 hours"
    else:
        hours_label = f"{opening_time} – {closing_time}"

    st.markdown(f'''<div class="info-panel">
      <h3>Amala T’Ó Dùn</h3>
      <div class="contact-row"><span class="contact-icon"><span class="material-symbols-rounded">location_on</span></span><div><strong>Visit us</strong><small>Orchid Road, Lekki, Lagos, Nigeria</small></div></div>
      <div class="contact-row"><span class="contact-icon"><span class="material-symbols-rounded">schedule</span></span><div><strong>Opening hours</strong><small>{html.escape(hours_label)}</small></div></div>
      <div class="contact-row"><span class="contact-icon"><span class="material-symbols-rounded">call</span></span><div><strong>Phone</strong><small>{html.escape(phone if phone else 'Phone number to be announced')}</small></div></div>
    </div>''', unsafe_allow_html=True)

    st.markdown("### Find us")
    st.components.v1.iframe(
        "https://www.google.com/maps?q=Orchid+Road%2C+Lekki%2C+Lagos%2C+Nigeria&output=embed",
        height=360,
        scrolling=False,
    )
    if whatsapp:
        st.link_button("Chat / order on WhatsApp", f"https://wa.me/{whatsapp}")

    st.markdown("### Follow us")
    social_cols = st.columns(2)
    instagram_svg = """<svg viewBox="0 0 24 24" width="25" height="25" aria-label="Instagram" role="img"><rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="17.5" cy="6.5" r="1.2" fill="currentColor"/></svg>"""
    tiktok_svg = """<svg viewBox="0 0 24 24" width="25" height="25" aria-label="TikTok" role="img"><path d="M14 3v11.2a4.2 4.2 0 1 1-3.5-4.1v3.2a1.2 1.2 0 1 0 .5 1V3h3c.3 2.2 1.6 3.8 4 4.3v3.1A8 8 0 0 1 14 8.8" fill="currentColor"/></svg>"""
    with social_cols[0]:
        if instagram:
            st.markdown(
                f'<a class="social-icon-link" href="{html.escape(instagram, quote=True)}" target="_blank" rel="noopener noreferrer">{instagram_svg}<span>Instagram</span></a>',
                unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="social-icon-muted">{instagram_svg}<span>Instagram</span></div>',
                        unsafe_allow_html=True)
            st.caption("Instagram link not added yet.")
    with social_cols[1]:
        if tiktok:
            st.markdown(
                f'<a class="social-icon-link" href="{html.escape(tiktok, quote=True)}" target="_blank" rel="noopener noreferrer">{tiktok_svg}<span>TikTok</span></a>',
                unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="social-icon-muted">{tiktok_svg}<span>TikTok</span></div>', unsafe_allow_html=True)
            st.caption("TikTok link not added yet.")

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
                    if account and hmac.compare_digest(username, account["username"]) and verify_password(password,
                                                                                                          account[
                                                                                                              "salt"],
                                                                                                          account[
                                                                                                              "password_hash"]):
                        st.session_state.admin = True
                        st.rerun()
                    else:
                        st.error("Incorrect username or password.")
            with reset_tab:
                st.write(
                    "Enter the administrator recovery code configured by the website owner, then choose a new password.")
                recovery_code = config_value("ADMIN_RESET_CODE", "RESTAURANT_ADMIN_RESET_CODE")
                if not recovery_code:
                    st.warning(
                        "Password recovery has not been configured. The website owner must add ADMIN_RESET_CODE in Streamlit Secrets before this option can be used.")
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
            st.caption(
                "For deployment, configure ADMIN_USERNAME, ADMIN_PASSWORD and ADMIN_RESET_CODE in Streamlit Community Cloud → App settings → Secrets.")
    else:
        top1, top2, top3 = st.columns([2, 2, 1])
        menu_all = get_menu()
        orders_conn = db()
        orders = orders_conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
        orders_conn.close()
        top1.metric("Menu items", len(menu_all))
        top2.metric("Available items", sum(x["available"] for x in menu_all))
        top3.metric("Orders", len(orders))
        if st.button("Sign out"):
            st.session_state.admin = False;
            st.rerun()
        tab_menu, tab_add, tab_orders, tab_settings = st.tabs(
            ["Manage menu", "Add menu item", "Orders", "Restaurant settings"])
        with tab_menu:
            st.markdown("#### Manage categories")
            category_col, add_category_col = st.columns([2, 1])
            with category_col:
                with st.form("add_menu_category_form", clear_on_submit=True):
                    new_category_name = st.text_input("New category name", placeholder="e.g. Seafood")
                    add_category_submit = st.form_submit_button("Add category")
                if add_category_submit:
                    clean_category = new_category_name.strip()
                    if not clean_category:
                        st.error("Enter a category name.")
                    elif any(existing.casefold() == clean_category.casefold() for existing in get_categories()):
                        st.error("That category already exists.")
                    else:
                        conn = db()
                        conn.execute("INSERT INTO menu_categories(name) VALUES(?)", (clean_category,))
                        conn.commit()
                        conn.close()
                        st.success(f"Category '{clean_category}' added.")
                        st.rerun()
            with add_category_col:
                current_categories = get_categories()
                if current_categories:
                    category_to_remove = st.selectbox("Category to remove", current_categories,
                                                      key="remove_category_select")
                    if st.button("Remove category", key="remove_menu_category_button"):
                        conn = db()
                        assigned_count = \
                        conn.execute("SELECT COUNT(*) FROM menu WHERE category=?", (category_to_remove,)).fetchone()[0]
                        if assigned_count:
                            conn.close()
                            st.error(
                                f"Cannot remove '{category_to_remove}' yet. {assigned_count} menu item(s) still use it. Move those items to another category first.")
                        else:
                            conn.execute("DELETE FROM menu_categories WHERE name=?", (category_to_remove,))
                            conn.commit()
                            conn.close()
                            st.success(f"Category '{category_to_remove}' removed.")
                            st.rerun()
                else:
                    st.caption("No categories have been created yet.")

            current_categories = get_categories()
            st.markdown("#### Edit category")
            if current_categories:
                with st.form("rename_menu_category_form"):
                    category_to_edit = st.selectbox("Choose category", current_categories, key="edit_category_select")
                    renamed_category = st.text_input("New category name", value=category_to_edit,
                                                     key="renamed_category_name")
                    rename_category_submit = st.form_submit_button("Save category changes")
                if rename_category_submit:
                    clean_new_name = renamed_category.strip()
                    if not clean_new_name:
                        st.error("Enter a category name.")
                    elif clean_new_name.casefold() != category_to_edit.casefold() and any(
                            existing.casefold() == clean_new_name.casefold() for existing in current_categories
                    ):
                        st.error("A category with that name already exists.")
                    elif clean_new_name == category_to_edit:
                        st.info("No category changes were made.")
                    else:
                        conn = db()
                        rename_succeeded = False
                        try:
                            conn.execute("BEGIN IMMEDIATE")
                            conn.execute("UPDATE menu_categories SET name=? WHERE name=?",
                                         (clean_new_name, category_to_edit))
                            conn.execute("UPDATE menu SET category=? WHERE category=?",
                                         (clean_new_name, category_to_edit))
                            conn.commit()
                            rename_succeeded = True
                        except sqlite3.IntegrityError:
                            conn.rollback()
                            st.error("A category with that name already exists.")
                        finally:
                            conn.close()
                        if rename_succeeded:
                            st.success(
                                f"Category renamed to '{clean_new_name}'. Menu items in that category were updated too.")
                            st.rerun()
            else:
                st.caption("Add a category before editing one.")
            st.divider()
            st.markdown("#### Menu inventory")
            for item in menu_all:
                with st.container(border=True):
                    image_col, left, mid, price_col, avail_col, del_col = st.columns([0.8, 2, 1, 1, 1, 1])
                    image_col.image(item_image(item), use_container_width=True)
                    left.write(f"**{item['name']}**")
                    mid.caption(item["category"])
                    price_col.write(money(item["price"]))
                    new_avail = avail_col.toggle("Available", value=bool(item["available"]),
                                                 key=f"availability_{item['id']}")
                    if int(new_avail) != item["available"]:
                        conn = db();
                        conn.execute("UPDATE menu SET available=? WHERE id=?", (int(new_avail), item["id"]));
                        conn.commit();
                        conn.close()
                        st.rerun()
                    if del_col.button("Delete", key=f"delete_{item['id']}"):
                        conn = db();
                        conn.execute("DELETE FROM menu WHERE id=?", (item["id"],));
                        conn.commit();
                        conn.close()
                        st.rerun()
                    with st.expander("Edit item"):
                        with st.form(f"edit_{item['id']}"):
                            en = st.text_input("Name", item["name"])
                            edit_categories = get_categories()
                            if item["category"] not in edit_categories:
                                edit_categories = [item["category"]] + edit_categories
                            ec = st.selectbox("Category", edit_categories,
                                              index=edit_categories.index(item["category"]))
                            ed = st.text_area("Description", item["description"])
                            ep = st.number_input("Price (₦)", min_value=0, value=int(item["price"]), step=100)
                            ei = st.text_input("Food image URL (optional)", item["image_url"])
                            upload_edit = st.file_uploader("Or upload a food image",
                                                           type=["png", "jpg", "jpeg", "webp"],
                                                           key=f"edit_image_{item['id']}")
                            save = st.form_submit_button("Save changes")
                        if save:
                            if upload_edit:
                                ei = save_uploaded_image(upload_edit)
                            conn = db();
                            conn.execute(
                                "UPDATE menu SET name=?,category=?,description=?,price=?,image_url=? WHERE id=?",
                                (en, ec, ed, int(ep), ei, item["id"]));
                            conn.commit();
                            conn.close()
                            st.success("Menu item updated.");
                            st.rerun()
        with tab_add:
            with st.form("add_item", clear_on_submit=True):
                name = st.text_input("Food / drink name")
                available_categories = get_categories()
                if not available_categories:
                    st.warning("Create a menu category in the Manage categories section before adding menu items.")
                    available_categories = ["Uncategorised"]
                category = st.selectbox("Category", available_categories)
                description = st.text_area("Description")
                price = st.number_input("Price (₦)", min_value=0, value=1000, step=100)
                image_url = st.text_input("Food image URL (optional)")
                upload_new = st.file_uploader("Upload food image", type=["png", "jpg", "jpeg", "webp"])
                available = st.checkbox("Available for ordering", value=True)
                add = st.form_submit_button("Add to menu")
            if add:
                if not name.strip():
                    st.error("Enter an item name.")
                else:
                    if upload_new:
                        image_url = save_uploaded_image(upload_new)
                    conn = db();
                    conn.execute(
                        "INSERT INTO menu(name,category,description,price,available,image_url) VALUES(?,?,?,?,?,?)",
                        (name.strip(), category, description.strip(), int(price), int(available), image_url.strip()));
                    conn.commit();
                    conn.close()
                    st.success("Menu item added.");
                    st.rerun()
        with tab_orders:
            st.markdown("#### Customer orders")
            if not orders: st.info("No orders have been placed yet.")
            for order in orders:
                with st.expander(
                        f"Order #{order['id']} · {order['customer']} · {money(order['total'])} · {order['status']}"):
                    st.write(f"**Phone:** {order['phone']}")
                    fulfilment = order["fulfilment_type"] if "fulfilment_type" in order.keys() else "Not specified"
                    st.write(f"**Fulfilment:** {fulfilment}")
                    st.write(f"**Address / note:** {order['address'] or 'Not provided'}")
                    st.write(f"**Items:** {order['items']}")
                    st.write(f"**Placed:** {order['created_at']}")
                    statuses = ["New", "Confirmed", "Preparing", "Ready", "Picked up", "Out for delivery", "Delivered",
                                "Cancelled"]
                    idx = statuses.index(order["status"]) if order["status"] in statuses else 0
                    new_status = st.selectbox("Order status", statuses, index=idx, key=f"status_{order['id']}")
                    if st.button("Update status", key=f"update_order_{order['id']}"):
                        conn = db();
                        conn.execute("UPDATE orders SET status=? WHERE id=?", (new_status, order["id"]));
                        conn.commit();
                        conn.close()
                        st.success("Order status updated.");
                        st.rerun()
                    if new_status in ["Picked up", "Out for delivery"] and fulfilment == "Delivery":
                        current_token = order["rider_token"] if "rider_token" in order.keys() else None
                        if not current_token:
                            if st.button("Create rider tracking link", key=f"create_rider_link_{order['id']}"):
                                token = secrets.token_urlsafe(32)
                                conn = db()
                                conn.execute("UPDATE orders SET rider_token=? WHERE id=?", (token, order["id"]))
                                conn.commit()
                                conn.close()
                                st.success("Rider tracking link created.")
                                st.rerun()
                        else:
                            link = rider_tracking_url(current_token)
                            if link:
                                st.markdown("**Rider GPS sharing link**")
                                st.code(link)
                                st.caption(
                                    "Send this link to the rider. They open it on their phone, tap Share my location, allow GPS access and keep the page open.")
                            else:
                                st.warning("Add the public website URL in Restaurant settings to create a rider link.")
                    elif new_status in ["Delivered", "Cancelled"]:
                        st.caption("Rider tracking is no longer active for this order.")
        with tab_settings:
            st.markdown("#### Restaurant details and online links")
            with st.form("restaurant_profile_form"):
                profile_phone = st.text_input("Restaurant phone number", value=get_setting("contact_phone"),
                                              placeholder="Add the confirmed phone number")
                profile_whatsapp = st.text_input("WhatsApp number (international format, digits only)",
                                                 value=get_setting("whatsapp_number"), placeholder="e.g. 2348012345678")
                profile_instagram = st.text_input("Instagram profile URL", value=get_setting("instagram_url"),
                                                  placeholder="https://instagram.com/...")
                profile_tiktok = st.text_input("TikTok profile URL", value=get_setting("tiktok_url"),
                                               placeholder="https://tiktok.com/@...")
                profile_public_url = st.text_input("Public website URL (for rider links)",
                                                   value=get_setting("public_website_url"),
                                                   placeholder="https://your-site.streamlit.app")
                st.caption("Enter the public website address customers use, including https://.")
                st.caption("To remove a social link, clear its field and save. To edit it, replace the URL and save.")
                st.markdown("**Operating hours**")
                hour_col1, hour_col2 = st.columns(2)
                with hour_col1:
                    profile_opening_time = st.time_input("Opening time",
                                                         value=datetime.strptime(get_setting("opening_time") or "00:00",
                                                                                 "%H:%M").time())
                with hour_col2:
                    profile_closing_time = st.time_input("Closing time",
                                                         value=datetime.strptime(get_setting("closing_time") or "23:59",
                                                                                 "%H:%M").time())
                save_profile = st.form_submit_button("Save restaurant details")
            if save_profile:
                conn = db()
                profile_values = [
                    ("contact_phone", profile_phone.strip()),
                    ("whatsapp_number", profile_whatsapp.strip().replace("+", "").replace(" ", "")),
                    ("instagram_url", profile_instagram.strip()),
                    ("tiktok_url", profile_tiktok.strip()),
                    ("public_website_url", profile_public_url.strip().rstrip("/")),
                    ("opening_time", profile_opening_time.strftime("%H:%M")),
                    ("closing_time", profile_closing_time.strftime("%H:%M")),
                ]
                for setting_key, setting_value in profile_values:
                    conn.execute(
                        "INSERT INTO restaurant_settings(setting_key,setting_value) VALUES(?,?) ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value",
                        (setting_key, setting_value))
                conn.commit();
                conn.close()
                st.success("Restaurant contact details, social links and opening hours saved.")
                st.rerun()
            st.markdown("**Restaurant address**")
            st.write("Orchid Road, Lekki, Lagos, Nigeria")
            st.divider()
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
  <div class="footer-tagline">AMALA T’Ó DÙN · THE AUTHENTIC TASTE OF HOME</div>
  <div class="footer-copyright">© 2026 Amala T’Ó Dùn.</div>
  <a class="footer-admin-link" href="?admin=1" target="_self">ADMIN LOGIN</a>
</div>
""", unsafe_allow_html=True)
