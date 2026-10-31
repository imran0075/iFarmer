import os, sqlite3, secrets, hmac, hashlib, re
import psycopg
from psycopg.rows import dict_row
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()
ROOT = Path(__file__).parent
DB_PATH = os.getenv("DATABASE_PATH", str(ROOT / "ifarmer.db"))
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY", "")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

from agriculture import router as agriculture_router

app = FastAPI(title="iFarmer", docs_url=None, redoc_url=None)
if not SECRET_KEY:
    # For local development only. Configure a stable secret in .env for deployment.
    SECRET_KEY = secrets.token_urlsafe(48)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax", https_only=COOKIE_SECURE)
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

FORBIDDEN = [
    "gme agro", "gmeagro", "জিএমই এগ্রো", "জিএমই এগ্রো লিঃ",
    "জিএমই এগ্রো লিমিটেড", "gme agro limited", "gme group"
]

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def db():
    # Keep SQLite as a local/fallback database until DATABASE_URL is configured.
    if DATABASE_URL:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=10)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def sql_placeholders(sql):
    return sql.replace("?", "%s") if DATABASE_URL else sql

def init_db():
    primary_key = "SERIAL PRIMARY KEY" if DATABASE_URL else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with db() as c:
        c.execute(f"""CREATE TABLE IF NOT EXISTS orders(
            id {primary_key}, name TEXT NOT NULL, phone TEXT NOT NULL,
            address TEXT NOT NULL, product TEXT NOT NULL, quantity TEXT NOT NULL,
            payment TEXT NOT NULL, notes TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'নতুন',
            created_at TEXT NOT NULL)""")
        c.execute(f"""CREATE TABLE IF NOT EXISTS partner_requests(
            id {primary_key}, shop_name TEXT NOT NULL, owner_name TEXT NOT NULL,
            phone TEXT NOT NULL, email TEXT DEFAULT '', subdomain TEXT NOT NULL UNIQUE,
            area TEXT NOT NULL, description TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'অপেক্ষমাণ',
            created_at TEXT NOT NULL)""")
        c.execute(f"""CREATE TABLE IF NOT EXISTS audit(
            id {primary_key}, actor TEXT NOT NULL, action TEXT NOT NULL,
            item_type TEXT NOT NULL, item_id INTEGER, created_at TEXT NOT NULL)""")
        c.execute(f"""CREATE TABLE IF NOT EXISTS partner_sites(
            id {primary_key}, partner_request_id INTEGER NOT NULL UNIQUE,
            shop_name TEXT NOT NULL, owner_name TEXT NOT NULL, phone TEXT NOT NULL,
            subdomain TEXT NOT NULL UNIQUE, area TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'সক্রিয়', created_at TEXT NOT NULL)""")
        c.execute(f"""CREATE TABLE IF NOT EXISTS partner_accounts(
            id {primary_key}, partner_request_id INTEGER NOT NULL UNIQUE,
            password_hash TEXT NOT NULL, created_at TEXT NOT NULL)""")
        c.execute(f"""CREATE TABLE IF NOT EXISTS partner_products(
            id {primary_key}, partner_request_id INTEGER NOT NULL,
            name TEXT NOT NULL, price TEXT NOT NULL, unit TEXT NOT NULL,
            description TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'সক্রিয়',
            created_at TEXT NOT NULL, image_data BYTEA)""")
        if DATABASE_URL:
            c.execute("ALTER TABLE partner_products ADD COLUMN IF NOT EXISTS image_data BYTEA")
        else:
            product_columns = [row["name"] for row in c.execute("PRAGMA table_info(partner_products)").fetchall()]
            if "image_data" not in product_columns:
                c.execute("ALTER TABLE partner_products ADD COLUMN image_data BLOB")
        c.execute(f"""CREATE TABLE IF NOT EXISTS order_product_links(
            id {primary_key}, order_id INTEGER NOT NULL UNIQUE,
            product_id INTEGER NOT NULL, partner_request_id INTEGER NOT NULL)""")
init_db()
app.include_router(agriculture_router)

def log_action(actor, action, item_type, item_id=None):
    with db() as c:
        c.execute(sql_placeholders("INSERT INTO audit(actor,action,item_type,item_id,created_at) VALUES(?,?,?,?,?)"),
                  (actor, action, item_type, item_id, now()))

def clean(s, maxlen=300):
    return re.sub(r"\s+", " ", (s or "").strip())[:maxlen]

def contains_forbidden(*values):
    text = " ".join(values).lower()
    return any(x.lower() in text for x in FORBIDDEN)

def password_digest(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 240000).hex()
    return salt + "$" + digest

def password_matches(password, stored):
    try:
        salt, digest = stored.split("$", 1)
        check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 240000).hex()
        return hmac.compare_digest(check, digest)
    except (ValueError, AttributeError):
        return False

def esc(s):
    import html
    return html.escape(str(s or ""))

def page(title, body, active=""):
    return f"""<!doctype html><html lang="bn"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#176b45"><title>{esc(title)} · iFarmer</title>
<link rel="stylesheet" href="/static/style.css"></head><body>
<header class="top"><a class="brand" href="/"><span class="logo">🌱</span><span>iFarmer</span></a>
<nav><a href="/agri">কৃষি সহায়ক</a><a href="/#products">পণ্য</a><a href="/#order">অর্ডার</a><a href="/track-order">অর্ডার ট্র্যাক</a><a href="/partner">পার্টনার হোন</a></nav></header>
{body}
<nav class="mobile-dock" aria-label="প্রধান মেনু"><a href="/">⌂<span>হোম</span></a><a href="/agri">🌱<span>কৃষি</span></a><a href="/#products">▦<span>পণ্য</span></a><a href="/partner/login">♙<span>প্রোফাইল</span></a></nav>
<footer><b>iFarmer</b><p>কৃষির ডিজিটাল সহযাত্রী</p><div><a href="/privacy">গোপনীয়তা</a> · <a href="/terms">শর্তাবলি</a> · <a href="/admin">মালিক লগইন</a></div>
<small>© {datetime.now().year} iFarmer</small></footer></body></html>"""

@app.get("/", response_class=HTMLResponse)
def home():
    with db() as c:
        products = c.execute(sql_placeholders("""SELECT pp.id,pp.name,pp.price,pp.unit,pp.description,
            pr.shop_name,pr.area,(pp.image_data IS NOT NULL) AS has_image FROM partner_products pp
            JOIN partner_requests pr ON pr.id=pp.partner_request_id
            WHERE pp.status='সক্রিয়' AND pr.status='অনুমোদিত'
            ORDER BY pp.id DESC LIMIT 60""")).fetchall()
    product_cards = ''.join(
        f'<article class="card">{f"<img class=\'product-photo\' src=\'/partner/product-image/{p[chr(105)+chr(100)]}\' alt=\'{esc(p[chr(110)+chr(97)+chr(109)+chr(101)])}\' loading=\'lazy\'>" if p["has_image"] else "<div class=\'card-icon\'>🛒</div>"}<h3>{esc(p["name"])}</h3>'
        f'<p><b>{esc(p["price"])} টাকা / {esc(p["unit"])}</b></p>'
        f'<p>{esc(p["description"])}</p><p class="fine">বিক্রেতা: {esc(p["shop_name"])} · {esc(p["area"])}</p>'
        f'<a class="btn primary" href="#order" onclick="document.getElementById(\'order-product\').value=\'{p["id"]}\'">এই পণ্য অর্ডার করুন</a></article>' for p in products
    )
    if not product_cards:
        product_cards = '<article class="card"><div class="card-icon">🌱</div><h3>পণ্য শিগগিরই আসছে</h3><p>অনুমোদিত পার্টনাররা পণ্য প্রকাশ করলে এখানে দেখা যাবে।</p></article>'
    body = f"""
<main>
<section class="hero">
<div class="pill">কৃষির ডিজিটাল সহযাত্রী</div><h1>কৃষি পণ্য ও সেবা,<br><span>এখন আরও সহজে</span></h1>
<p>কৃষকের প্রয়োজনীয় পণ্য খুঁজুন, অর্ডারের অনুরোধ পাঠান এবং স্থানীয় কৃষি সেবার সঙ্গে যুক্ত থাকুন।</p>
<div class="actions"><a class="btn primary" href="#products">পণ্য দেখুন</a><a class="btn light" href="/partner">পার্টনার হোন</a></div>
<div class="hero-note">সহজ অর্ডার · ফোনে নিশ্চিতকরণ · ডেলিভারির নিয়ম বিক্রেতার সঙ্গে নিশ্চিত করুন</div>
</section>
<section class="stats"><div><b>🌾</b><span>কৃষি পণ্য</span></div><div><b>🛒</b><span>সহজ অর্ডার</span></div><div><b>📞</b><span>ফোনে নিশ্চিতকরণ</span></div><div><b>🏪</b><span>স্থানীয় পার্টনার</span></div></section>
<section class="section" id="agriculture">
<div class="section-head"><div><div class="eyebrow">কৃষকের ডিজিটাল সহকারী</div><h2>কৃষি সহায়ক সেবা</h2></div><p>আবহাওয়া দেখুন, জমির হিসাব করুন এবং ফসলের সমস্যা সম্পর্কে তথ্য জমা দিন।</p></div>
<div class="cards">
<article class="card"><div class="card-icon">🌦️</div><h3>কৃষি আবহাওয়া</h3><p>জেলাভিত্তিক তাপমাত্রা, বৃষ্টি ও বাতাসের তথ্য।</p><a class="btn primary" href="/agri/weather">আবহাওয়া দেখুন</a></article>
<article class="card"><div class="card-icon">🧮</div><h3>সার ক্যালকুলেটর</h3><p>জমির পরিমাণ ও সুপারিশকৃত মাত্রা দিয়ে মোট সার হিসাব।</p><a class="btn primary" href="/agri/fertilizer">সার হিসাব করুন</a></article>
<article class="card"><div class="card-icon">🧴</div><h3>কীটনাশক ক্যালকুলেটর</h3><p>অনুমোদিত পণ্যের লেবেলে দেওয়া মাত্রা অনুযায়ী হিসাব।</p><a class="btn primary" href="/agri/pesticide">মাত্রা হিসাব করুন</a></article>
<article class="card"><div class="card-icon">📷</div><h3>ফসলের সমস্যা</h3><p>ফসলের ছবি ও লক্ষণ জমা দিন; AI রোগ শনাক্তকরণ এখনো চালু নয়।</p><a class="btn primary" href="/agri/diagnose">ছবি জমা দিন</a></article>
</div></section>
<section class="section" id="agri-categories">
<div class="section-head"><div><div class="eyebrow">এক প্ল্যাটফর্মে সব সেবা</div><h2>কৃষি, মৎস্য ও প্রাণিসম্পদ</h2></div><p>আপনার প্রয়োজনীয় বিভাগ বেছে নিয়ে সংশ্লিষ্ট পরামর্শ ও সেবা নিন।</p></div>
<div class="cards">
<article class="card"><div class="card-icon">🌾</div><h3>ফসল</h3><p>ধান, গম, ভুট্টা, শাকসবজি ও ফলের রোগ-পোকা এবং পরিচর্যার পরামর্শ।</p><a class="btn primary" href="/agri/category/crop">ফসল বিভাগে যান</a></article>
<article class="card"><div class="card-icon">🐟</div><h3>মৎস্য</h3><p>মাছের চাষ, পানির গুণাগুণ, রোগ শনাক্তকরণ ও পরিচর্যার সহায়তা।</p><a class="btn primary" href="/agri/category/fish">মৎস্য বিভাগে যান</a></article>
<article class="card"><div class="card-icon">🐄</div><h3>প্রাণিজ</h3><p>গরু, ছাগল ও ভেড়ার পালন, খাদ্য, স্বাস্থ্য ও রোগ বিষয়ে সহায়তা।</p><a class="btn primary" href="/agri/category/livestock">প্রাণিজ বিভাগে যান</a></article>
<article class="card"><div class="card-icon">🐔</div><h3>পোল্ট্রি</h3><p>মুরগি, হাঁস, টার্কি ও কোয়েল পালন, খাদ্য ও স্বাস্থ্য ব্যবস্থাপনা।</p><a class="btn primary" href="/agri/category/poultry">পোল্ট্রি বিভাগে যান</a></article>
</div></section>
<section id="products" class="section"><div class="section-head"><div><div class="eyebrow">iFarmer মার্কেটপ্লেস</div><h2>পার্টনারদের পণ্য</h2></div><p>পণ্যের প্রাপ্যতা, দাম ও ব্যবহার বিক্রেতার সঙ্গে নিশ্চিত করুন।</p></div>
<div class="cards">{product_cards}</div></section>
<section id="order" class="section order-section"><div class="section-head"><div><div class="eyebrow">অর্ডার রিকোয়েস্ট</div><h2>আপনার অর্ডারের তথ্য দিন</h2></div><p>ফর্ম পাঠানোর পর বিক্রেতা আপনার সঙ্গে যোগাযোগ করবেন।</p></div>
<form class="form card" method="post" action="/order">
<div class="form-grid">
<label>আপনার নাম<input name="name" required maxlength="100" placeholder="পূর্ণ নাম"></label>
<label>মোবাইল নম্বর<input name="phone" required inputmode="tel" maxlength="30" placeholder="01XXXXXXXXX"></label>
<label class="wide">পণ্য নির্বাচন<select id="order-product" name="product_id" required><option value="">পণ্য নির্বাচন করুন</option>{''.join(f'<option value="{p["id"]}">{esc(p["name"])} — {esc(p["price"])} টাকা / {esc(p["unit"])} · {esc(p["shop_name"])}</option>' for p in products)}</select></label>
<label>পরিমাণ<input name="quantity" required maxlength="80" placeholder="যেমন: ৫ প্যাকেট"></label>
<label class="wide">ডেলিভারি ঠিকানা<input name="address" required maxlength="300" placeholder="গ্রাম, বাজার, উপজেলা, জেলা"></label>
<label>পেমেন্ট পদ্ধতি<select name="payment"><option value="ক্যাশ অন ডেলিভারি">ক্যাশ অন ডেলিভারি (অনুরোধ)</option><option value="ফোনে আলোচনা">ফোনে আলোচনা করে ঠিক করব</option></select></label>
<label>অতিরিক্ত তথ্য<input name="notes" maxlength="300" placeholder="ঐচ্ছিক"></label>
</div><button class="btn primary" type="submit">অর্ডারের অনুরোধ পাঠান →</button>
<p class="fine">এটি অর্ডারের অনুরোধ; ফোনে মূল্য, পণ্য, প্রাপ্যতা ও ডেলিভারি নিশ্চিত হওয়ার পর অর্ডার চূড়ান্ত হবে।</p>
</form></section>
<section class="partner-banner"><div><div class="eyebrow">স্থানীয় ব্যবসার জন্য</div><h2>iFarmer পার্টনার নেটওয়ার্কে যোগ দিন</h2><p>দোকানের তথ্য জমা দিন। প্রতিটি পার্টনার অনুরোধ মালিকের অনুমোদনের জন্য অপেক্ষা করবে।</p></div><a class="btn light" href="/partner">আবেদন করুন</a></section>
</main>"""
    return page("কৃষি পণ্য ও সেবা", body)

@app.post("/order", response_class=HTMLResponse)
def create_order(name: str=Form(...), phone: str=Form(...), address: str=Form(...),
                 product_id: int=Form(...), quantity: str=Form(...),
                 payment: str=Form("ক্যাশ অন ডেলিভারি"), notes: str=Form("")):
    with db() as c:
        selected = c.execute(sql_placeholders("""SELECT pp.id,pp.name,pp.price,pp.unit,
            pr.id AS partner_id,pr.shop_name FROM partner_products pp
            JOIN partner_requests pr ON pr.id=pp.partner_request_id
            WHERE pp.id=? AND pp.status='সক্রিয়' AND pr.status='অনুমোদিত'"""), (product_id,)).fetchone()
    if not selected:
        raise HTTPException(400, "নির্বাচিত পণ্যটি এখন অর্ডারের জন্য পাওয়া যাচ্ছে না।")
    product = f'{selected["name"]} ({selected["shop_name"]})'
    vals = [clean(name,100), clean(phone,30), clean(address,300), clean(product,160),
            clean(quantity,80), clean(payment,50), clean(notes,300)]
    if contains_forbidden(*vals):
        raise HTTPException(400, "এই ব্র্যান্ডের নাম iFarmer-এ অনুমোদিত নয়।")
    if not vals[0] or not vals[1] or not vals[2] or not vals[3] or not vals[4]:
        raise HTTPException(400, "প্রয়োজনীয় তথ্য পূরণ করুন।")
    with db() as c:
        cur = c.execute(sql_placeholders("""INSERT INTO orders(name,phone,address,product,quantity,payment,notes,created_at)
        VALUES(?,?,?,?,?,?,?,?)""") + (" RETURNING id" if DATABASE_URL else ""), (*vals, now()))
        oid = cur.fetchone()["id"] if DATABASE_URL else cur.lastrowid
        c.execute(sql_placeholders("INSERT INTO order_product_links(order_id,product_id,partner_request_id) VALUES(?,?,?)"),
                  (oid, selected["id"], selected["partner_id"]))
    log_action("public", "order_created", "order", oid)
    body = f"""<main class="narrow"><section class="success"><div class="success-icon">✓</div><h1>অর্ডারের অনুরোধ গ্রহণ করা হয়েছে</h1>
<p>আপনার অনুরোধ নম্বর <b>IF-{oid:05d}</b>। বিক্রেতা ফোনে যোগাযোগ করে তথ্য নিশ্চিত করতে পারেন।</p>
<p>পণ্য, মূল্য ও ডেলিভারি নিশ্চিত না হওয়া পর্যন্ত অর্ডার চূড়ান্ত নয়।</p><a class="btn primary" href="/track-order?order_code=IF-{oid:05d}">অর্ডার ট্র্যাক করুন</a> <a class="btn light" href="/">হোমে ফিরে যান</a></section></main>"""
    return page("অর্ডার গ্রহণ", body)

@app.get("/track-order", response_class=HTMLResponse)
def track_order(order_code: str = ""):
    code = clean(order_code, 20).upper()
    body = f"""<main class="narrow"><section class="section-head"><div><div class="eyebrow">অর্ডার ট্র্যাকিং</div><h1>আপনার অর্ডারের অবস্থা দেখুন</h1></div><p>অর্ডার নম্বর ও অর্ডারের সময় দেওয়া মোবাইল নম্বর লিখুন।</p></section>
<form class="form card" method="post" action="/track-order">
<label>অর্ডার নম্বর<input name="order_code" required maxlength="20" value="{esc(code)}" placeholder="যেমন: IF-00001"></label>
<label>মোবাইল নম্বর<input name="phone" required inputmode="tel" maxlength="30" placeholder="অর্ডারে দেওয়া নম্বর"></label>
<button class="btn primary" type="submit">অর্ডার খুঁজুন</button></form></main>"""
    return page("অর্ডার ট্র্যাক", body)

@app.post("/track-order", response_class=HTMLResponse)
def track_order_post(order_code: str=Form(...), phone: str=Form(...)):
    code = clean(order_code, 20).upper()
    match = re.fullmatch(r"IF-(\d{1,10})", code)
    if not match:
        raise HTTPException(400, "সঠিক অর্ডার নম্বর লিখুন, যেমন IF-00001।")
    oid = int(match.group(1))
    phone_value = clean(phone, 30)
    with db() as c:
        row = c.execute(sql_placeholders("SELECT id,product,quantity,status,created_at FROM orders WHERE id=? AND phone=?"), (oid, phone_value)).fetchone()
    if not row:
        body = """<main class="narrow"><section class="card"><h1>অর্ডার পাওয়া যায়নি</h1><p>অর্ডার নম্বর ও মোবাইল নম্বর মিলিয়ে আবার চেষ্টা করুন।</p><a class="btn light" href="/track-order">আবার খুঁজুন</a></section></main>"""
        return page("অর্ডার পাওয়া যায়নি", body)
    cancel_button = ""
    if row["status"] in ["নতুন", "ফোনে যোগাযোগ করতে হবে"]:
        cancel_button = f"""<form class="form card" method="post" action="/track-order/cancel"><input type="hidden" name="order_code" value="IF-{row['id']:05d}"><input type="hidden" name="phone" value="{esc(phone_value)}"><p>অর্ডারটি আর প্রয়োজন না হলে বাতিলের অনুরোধ পাঠাতে পারেন।</p><button class="btn light" type="submit">অর্ডার বাতিলের অনুরোধ</button></form>"""
    body = f"""<main class="narrow"><section class="success"><div class="success-icon">✓</div><h1>অর্ডার: IF-{row['id']:05d}</h1><p>অর্ডারের তথ্য</p><div class="card"><p><b>পণ্য:</b> {esc(row['product'])}</p><p><b>পরিমাণ:</b> {esc(row['quantity'])}</p><p><b>তারিখ:</b> {esc(row['created_at'])}</p><p><b>বর্তমান অবস্থা:</b> <strong>{esc(row['status'])}</strong></p></div>{cancel_button}<a class="btn light" href="/track-order">অন্য অর্ডার ট্র্যাক করুন</a></section></main>"""
    return page("অর্ডারের অবস্থা", body)

@app.post("/track-order/cancel", response_class=HTMLResponse)
def track_order_cancel(order_code: str=Form(...), phone: str=Form(...)):
    code = clean(order_code, 20).upper()
    match = re.fullmatch(r"IF-(\d{1,10})", code)
    if not match:
        raise HTTPException(400, "সঠিক অর্ডার নম্বর লিখুন।")
    oid = int(match.group(1))
    phone_value = clean(phone, 30)
    with db() as c:
        row = c.execute(sql_placeholders("SELECT id,status FROM orders WHERE id=? AND phone=?"), (oid, phone_value)).fetchone()
        if not row:
            raise HTTPException(404, "অর্ডার পাওয়া যায়নি।")
        if row["status"] not in ["নতুন", "ফোনে যোগাযোগ করতে হবে"]:
            body = f"""<main class="narrow"><section class="card"><h1>বাতিলের অনুরোধ করা যাচ্ছে না</h1><p>এই অর্ডারের অবস্থা: <b>{esc(row['status'])}</b>। বিক্রেতার সঙ্গে ফোনে যোগাযোগ করুন।</p><a class="btn light" href="/track-order?order_code=IF-{oid:05d}">অর্ডার ট্র্যাক করুন</a></section></main>"""
            return page("বাতিলের অনুরোধ", body)
        c.execute(sql_placeholders("UPDATE orders SET status=? WHERE id=?"), ("বাতিলের অনুরোধ", oid))
    log_action("public", "order_cancel_requested", "order", oid)
    body = f"""<main class="narrow"><section class="success"><div class="success-icon">✓</div><h1>বাতিলের অনুরোধ পাঠানো হয়েছে</h1><p>অর্ডার IF-{oid:05d} বাতিলের অনুরোধ বিক্রেতার কাছে পাঠানো হয়েছে।</p><p>চূড়ান্ত অবস্থা অর্ডার ট্র্যাকিংয়ে দেখুন।</p><a class="btn primary" href="/track-order?order_code=IF-{oid:05d}">অর্ডার ট্র্যাক করুন</a></section></main>"""
    return page("বাতিলের অনুরোধ", body)

@app.get("/partner", response_class=HTMLResponse)
def partner():
    body = """<main class="narrow"><section class="section-head"><div><div class="eyebrow">iFarmer পার্টনার</div><h1>দোকান/পার্টনার সাইটের আবেদন</h1></div><p>আবেদন জমা দিলে মালিক যাচাই করে অনুমোদন বা বাতিল করবেন। অনুমোদন নিজে থেকে সাবডোমেইন চালু করে না।</p></section>
<form class="form card" method="post" action="/partner">
<div class="form-grid">
<label>দোকানের নাম<input name="shop_name" required maxlength="140"></label>
<label>মালিক/যোগাযোগ ব্যক্তির নাম<input name="owner_name" required maxlength="100"></label>
<label>মোবাইল নম্বর<input name="phone" required maxlength="30" inputmode="tel"></label>
<label>ইমেইল (ঐচ্ছিক)<input name="email" type="email" maxlength="160"></label>
<label>ড্যাশবোর্ড পাসওয়ার্ড<input name="password" type="password" required minlength="8" maxlength="128" autocomplete="new-password"></label>
<label>প্রস্তাবিত সাবডোমেইন নাম<input name="subdomain" required maxlength="50" pattern="[a-zA-Z0-9-]{3,50}" placeholder="যেমন: rahim-agro"></label>
<label>এলাকা<input name="area" required maxlength="200" placeholder="বাজার, উপজেলা, জেলা"></label>
<label class="wide">ব্যবসার সংক্ষিপ্ত বিবরণ<textarea name="description" maxlength="400"></textarea></label>
</div><button class="btn primary" type="submit">অনুমোদনের জন্য পাঠান</button>
<p class="fine">শুধু ইংরেজি অক্ষর, সংখ্যা ও হাইফেন দিয়ে সাবডোমেইন লিখুন। অনুমোদনের পর ডোমেইন/DNS সেটআপ আলাদাভাবে প্রয়োজন হবে।</p>
<p class="fine">আগে আবেদন করেছেন? <a href="/partner/login">পার্টনার লগইন</a></p>
</form></main>"""
    return page("পার্টনার আবেদন", body)

@app.post("/partner", response_class=HTMLResponse)
def create_partner(shop_name: str=Form(...), owner_name: str=Form(...), phone: str=Form(...),
                   email: str=Form(""), password: str=Form(...), subdomain: str=Form(...),
                   area: str=Form(...), description: str=Form("")):
    vals = [clean(shop_name,140), clean(owner_name,100), clean(phone,30), clean(email,160),
            clean(subdomain,50).lower(), clean(area,200), clean(description,400)]
    if len(password) < 8 or len(password) > 128:
        raise HTTPException(400, "পাসওয়ার্ড ৮ থেকে ১২৮ অক্ষরের হতে হবে।")
    if contains_forbidden(*vals):
        raise HTTPException(400, "এই ব্র্যান্ডের নাম iFarmer-এ অনুমোদিত নয়।")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])", vals[4]):
        raise HTTPException(400, "সাবডোমেইন ৩-৫০ অক্ষরের হতে হবে; ইংরেজি ছোট হাতের অক্ষর, সংখ্যা ও হাইফেন ব্যবহার করুন।")
    try:
        with db() as c:
            cur = c.execute(sql_placeholders("""INSERT INTO partner_requests(shop_name,owner_name,phone,email,subdomain,area,description,created_at)
            VALUES(?,?,?,?,?,?,?,?)""") + (" RETURNING id" if DATABASE_URL else ""), (*vals, now()))
            pid = cur.fetchone()["id"] if DATABASE_URL else cur.lastrowid
            c.execute(sql_placeholders("INSERT INTO partner_accounts(partner_request_id,password_hash,created_at) VALUES(?,?,?)"),
                      (pid, password_digest(password), now()))
    except (sqlite3.IntegrityError, psycopg.errors.UniqueViolation):
        raise HTTPException(409, "এই সাবডোমেইন নাম আগে থেকেই আবেদন করা হয়েছে।")
    log_action("public", "partner_request_created", "partner", pid)
    body = f"""<main class="narrow"><section class="success"><div class="success-icon">✓</div><h1>আবেদন জমা হয়েছে</h1><p>আবেদন নম্বর <b>IP-{pid:05d}</b>। স্ট্যাটাস: অপেক্ষমাণ। মালিক অনুমোদন না দেওয়া পর্যন্ত সাইট চালু হবে না।</p><a class="btn primary" href="/">হোমে ফিরে যান</a></section></main>"""
    return page("আবেদন জমা", body)


@app.get("/partner/login", response_class=HTMLResponse)
def partner_login_page(request: Request):
    if request.session.get("partner_id"):
        return RedirectResponse("/partner/dashboard", status_code=303)
    body = """<main class="narrow"><section class="section-head"><div><div class="eyebrow">iFarmer পার্টনার</div><h1>পার্টনার লগইন</h1></div><p>আবেদনের সময় দেওয়া সাবডোমেইন নাম ও পাসওয়ার্ড ব্যবহার করুন।</p></section>
<form class="form card" method="post" action="/partner/login">
<label>সাবডোমেইন নাম<input name="subdomain" required maxlength="50" placeholder="যেমন: rahim-agro"></label>
<label>পাসওয়ার্ড<input name="password" type="password" required autocomplete="current-password"></label>
<button class="btn primary" type="submit">লগইন</button><p class="fine"><a href="/partner">নতুন পার্টনার আবেদন</a></p></form></main>"""
    return page("পার্টনার লগইন", body)

@app.post("/partner/login", response_class=HTMLResponse)
def partner_login(request: Request, subdomain: str=Form(...), password: str=Form(...)):
    slug = clean(subdomain, 50).lower()
    with db() as c:
        row = c.execute(sql_placeholders("""SELECT pr.id,pr.status,pa.password_hash
            FROM partner_requests pr JOIN partner_accounts pa ON pa.partner_request_id=pr.id
            WHERE pr.subdomain=?"""), (slug,)).fetchone()
    if not row or not password_matches(password, row["password_hash"]):
        raise HTTPException(401, "সাবডোমেইন নাম বা পাসওয়ার্ড সঠিক নয়।")
    if row["status"] != "অনুমোদিত":
        raise HTTPException(403, "মালিক আবেদন অনুমোদন করার পর ড্যাশবোর্ড ব্যবহার করতে পারবেন।")
    request.session["partner_id"] = row["id"]
    return RedirectResponse("/partner/dashboard", status_code=303)

@app.post("/partner/logout")
def partner_logout(request: Request):
    request.session.pop("partner_id", None)
    return RedirectResponse("/partner/login", status_code=303)

@app.get("/partner/dashboard", response_class=HTMLResponse)
def partner_dashboard(request: Request):
    partner_id = request.session.get("partner_id")
    if not partner_id:
        return RedirectResponse("/partner/login", status_code=303)
    with db() as c:
        partner = c.execute(sql_placeholders("SELECT * FROM partner_requests WHERE id=?"), (partner_id,)).fetchone()
        products = c.execute(sql_placeholders("SELECT * FROM partner_products WHERE partner_request_id=? ORDER BY id DESC LIMIT 100"), (partner_id,)).fetchall()
        orders = c.execute(sql_placeholders("""SELECT o.* FROM orders o
            JOIN order_product_links l ON l.order_id=o.id
            WHERE l.partner_request_id=? ORDER BY o.id DESC LIMIT 100"""), (partner_id,)).fetchall()
    if not partner or partner["status"] != "অনুমোদিত":
        request.session.pop("partner_id", None)
        return RedirectResponse("/partner/login", status_code=303)
    def product_row(p):
        action_status = "বন্ধ" if p["status"] == "সক্রিয়" else "সক্রিয়"
        action_label = "বন্ধ করুন" if p["status"] == "সক্রিয়" else "আবার চালু করুন"
        photo = f'<img class="partner-product-thumb" src="/partner/product-image/{p["id"]}" alt="পণ্যের ছবি">' if p["image_data"] else "ছবি নেই"
        return f"""<tr><td>{photo}<br><b>{esc(p['name'])}</b><br><small>{esc(p['description'])}</small></td><td>{esc(p['price'])} টাকা / {esc(p['unit'])}</td><td>{esc(p['status'])}</td><td><a class="mini partner-action-link" href="/partner/product/{p['id']}/edit">এডিট / ছবি পরিবর্তন</a><form method="post" action="/partner/product/status"><input type="hidden" name="product_id" value="{p['id']}"><input type="hidden" name="status" value="{action_status}"><button class="mini">{action_label}</button></form><form method="post" action="/partner/product/delete" onsubmit="return confirm('এই পণ্যটি স্থায়ীভাবে মুছে ফেলবেন?')"><input type="hidden" name="product_id" value="{p['id']}"><button class="mini danger-mini">ডিলিট করুন</button></form></td></tr>"""
    body = f"""<main class="admin-main"><div class="admin-head"><div><div class="eyebrow">iFarmer PARTNER</div><h1>পার্টনার ড্যাশবোর্ড</h1><p>{esc(partner['shop_name'])} · {esc(partner['subdomain'])}</p></div><form method="post" action="/partner/logout"><button class="btn light">লগআউট</button></form></div>
<div class="stats admin-stats"><div><b>{len(products)}</b><span>পণ্য তালিকা</span></div><div><b>{esc(partner['area'])}</b><span>ব্যবসার এলাকা</span></div></div>
<section class="admin-section"><h2>নতুন পণ্য যোগ করুন</h2><form class="form card" method="post" action="/partner/product" enctype="multipart/form-data"><div class="form-grid"><label>পণ্যের নাম<input name="name" required maxlength="140"></label><label class="wide">পণ্যের ছবি (JPG, PNG বা WebP; সর্বোচ্চ ৪ MB)<input type="file" name="image" accept="image/jpeg,image/png,image/webp"></label><label>দাম (টাকা)<input name="price" required maxlength="30" inputmode="decimal" placeholder="যেমন: ২৫০"></label><label>একক<input name="unit" required maxlength="40" placeholder="যেমন: প্যাকেট / কেজি"></label><label class="wide">বিবরণ<textarea name="description" maxlength="400"></textarea></label></div><button class="btn primary" type="submit">পণ্য যোগ করুন</button></form></section>
<section class="admin-section"><h2>আমার পণ্য</h2><div class="table-wrap"><table><thead><tr><th>পণ্য</th><th>দাম</th><th>অবস্থা</th><th>কাজ</th></tr></thead><tbody>{''.join(product_row(p) for p in products) or '<tr><td colspan="4">এখনো পণ্য যোগ করা হয়নি।</td></tr>'}</tbody></table></div><p class="fine">এখান থেকে পণ্যের তথ্য ও ছবি পরিবর্তন, পণ্য সাময়িক বন্ধ/চালু এবং স্থায়ীভাবে মুছে ফেলা যাবে।</p></section>
<section class="admin-section" id="partner-orders"><h2>আমার অর্ডার</h2>
<div class="table-wrap"><table><thead><tr><th>অর্ডার / সময়</th><th>ক্রেতা</th><th>পণ্য ও পরিমাণ</th><th>পেমেন্ট / নোট</th><th>স্ট্যাটাস পরিবর্তন</th></tr></thead><tbody>{''.join(f"""<tr><td><b>IF-{o['id']:05d}</b><br><small>{esc(o['created_at'])}</small></td><td><b>{esc(o['name'])}</b><br><a href="tel:{esc(o['phone'])}">{esc(o['phone'])}</a><br>{esc(o['address'])}</td><td>{esc(o['product'])}<br>পরিমাণ: {esc(o['quantity'])}</td><td>{esc(o['payment'])}<br><small>{esc(o['notes'])}</small></td><td><form method="post" action="/partner/order-status"><input type="hidden" name="order_id" value="{o['id']}"><select name="status">{''.join(f'<option {"selected" if o["status"]==st else ""}>{st}</option>' for st in ["নতুন","ফোনে যোগাযোগ করতে হবে","বাতিলের অনুরোধ","নিশ্চিত","প্রসেসিং","ডেলিভারির পথে","সম্পন্ন","বাতিল"])}</select><button class="mini">আপডেট</button></form></td></tr>""" for o in orders) or '<tr><td colspan="5">এখনো কোনো অর্ডার আসেনি।</td></tr>'}</tbody></table></div>
<p class="fine">শুধু আপনার দোকানের পণ্যের অর্ডার এখানে দেখানো হয়। ক্রেতার সঙ্গে ফোনে যোগাযোগ করে অর্ডার নিশ্চিত করুন।</p></section></main>"""
    return page("পার্টনার ড্যাশবোর্ড", body)

@app.post("/partner/order-status")
def partner_order_status(request: Request, order_id: int=Form(...), status: str=Form(...)):
    partner_id = request.session.get("partner_id")
    if not partner_id:
        return RedirectResponse("/partner/login", status_code=303)
    allowed = ["নতুন","ফোনে যোগাযোগ করতে হবে","নিশ্চিত","প্রসেসিং","ডেলিভারির পথে","সম্পন্ন","বাতিল"]
    if status not in allowed:
        raise HTTPException(400, "অবৈধ স্ট্যাটাস।")
    with db() as c:
        owned = c.execute(sql_placeholders("""SELECT o.id FROM orders o
            JOIN order_product_links l ON l.order_id=o.id
            WHERE o.id=? AND l.partner_request_id=?"""), (order_id, partner_id)).fetchone()
        if not owned:
            raise HTTPException(404, "আপনার দোকানের এই অর্ডারটি পাওয়া যায়নি।")
        c.execute(sql_placeholders("UPDATE orders SET status=? WHERE id=?"), (status, order_id))
    log_action("partner:"+str(partner_id), "order_status:"+status, "order", order_id)
    return RedirectResponse("/partner/dashboard#partner-orders", status_code=303)


@app.get("/partner/product/{product_id}/edit", response_class=HTMLResponse)
def partner_product_edit(request: Request, product_id: int):
    partner_id = request.session.get("partner_id")
    if not partner_id:
        return RedirectResponse("/partner/login", status_code=303)
    with db() as c:
        p = c.execute(sql_placeholders("SELECT * FROM partner_products WHERE id=? AND partner_request_id=?"), (product_id, partner_id)).fetchone()
    if not p:
        raise HTTPException(404, "পণ্য পাওয়া যায়নি।")
    photo = f'<img class="partner-edit-photo" src="/partner/product-image/{product_id}" alt="বর্তমান পণ্যের ছবি">' if p["image_data"] else '<p class="fine">এখনো কোনো ছবি দেওয়া হয়নি।</p>'
    body = f"""<main class="narrow"><section class="section-head"><div><div class="eyebrow">পণ্য ব্যবস্থাপনা</div><h1>পণ্যের তথ্য এডিট করুন</h1></div></section>
<form class="form card" method="post" action="/partner/product/{product_id}/edit" enctype="multipart/form-data">
{photo}
<div class="form-grid"><label class="wide">পণ্যের নাম<input name="name" required maxlength="140" value="{esc(p['name'])}"></label>
<label>দাম (টাকা)<input name="price" required maxlength="30" value="{esc(p['price'])}"></label>
<label>একক<input name="unit" required maxlength="40" value="{esc(p['unit'])}"></label>
<label class="wide">বিবরণ<textarea name="description" maxlength="400">{esc(p['description'])}</textarea></label>
<label class="wide">নতুন ছবি দিন (ঐচ্ছিক; JPG, PNG বা WebP; সর্বোচ্চ ৪ MB)<input type="file" name="image" accept="image/jpeg,image/png,image/webp"></label>
<label class="wide"><span><input type="checkbox" name="remove_image" value="true"> বর্তমান ছবি মুছে ফেলুন</span></label></div>
<button class="btn primary" type="submit">পরিবর্তন সেভ করুন</button> <a class="btn light" href="/partner/dashboard">ফিরে যান</a></form></main>"""
    return page("পণ্য এডিট", body)

@app.get("/partner/product-image/{product_id}")
def partner_product_image(product_id: int):
    with db() as c:
        row = c.execute(sql_placeholders("""SELECT image_data FROM partner_products
            WHERE id=? AND status='সক্রিয়'"""), (product_id,)).fetchone()
    if not row or not row["image_data"]:
        raise HTTPException(404, "ছবি পাওয়া যায়নি।")
    data = bytes(row["image_data"])
    media = "image/jpeg" if data.startswith(bytes([255,216])) else ("image/png" if data.startswith(bytes([137,80,78,71])) else "image/webp")
    return Response(content=data, media_type=media, headers={"Cache-Control":"no-cache"})

@app.post("/partner/product")
async def partner_add_product(request: Request, name: str=Form(...), price: str=Form(...),
                        unit: str=Form(...), description: str=Form(""),
                        image: UploadFile | None=File(default=None)):
    partner_id = request.session.get("partner_id")
    if not partner_id:
        return RedirectResponse("/partner/login", status_code=303)
    values = [clean(name, 140), clean(price, 30), clean(unit, 40), clean(description, 400)]
    if not values[0] or not values[1] or not values[2] or contains_forbidden(*values):
        raise HTTPException(400, "পণ্যের তথ্য সঠিকভাবে দিন।")
    image_data = None
    if image and image.filename:
        if image.content_type not in ["image/jpeg", "image/png", "image/webp"]:
            raise HTTPException(400, "শুধু JPG, PNG বা WebP ছবি দিন।")
        image_data = await image.read(4 * 1024 * 1024 + 1)
        if len(image_data) > 4 * 1024 * 1024:
            raise HTTPException(400, "ছবির সাইজ ৪ MB-এর কম হতে হবে।")
    with db() as c:
        partner = c.execute(sql_placeholders("SELECT status FROM partner_requests WHERE id=?"), (partner_id,)).fetchone()
        if not partner or partner["status"] != "অনুমোদিত":
            raise HTTPException(403, "অনুমোদিত পার্টনার ছাড়া পণ্য যোগ করা যাবে না।")
        c.execute(sql_placeholders("""INSERT INTO partner_products
            (partner_request_id,name,price,unit,description,created_at,image_data) VALUES(?,?,?,?,?,?,?)"""),
            (partner_id, values[0], values[1], values[2], values[3], now(), image_data))
    log_action("partner:"+str(partner_id), "product_created", "partner_product", partner_id)
    return RedirectResponse("/partner/dashboard", status_code=303)

@app.post("/partner/product/{product_id}/edit")
async def partner_product_edit_post(request: Request, product_id: int, name: str=Form(...),
        price: str=Form(...), unit: str=Form(...), description: str=Form(""),
        remove_image: bool=Form(False), image: UploadFile | None=File(default=None)):
    partner_id = request.session.get("partner_id")
    if not partner_id:
        return RedirectResponse("/partner/login", status_code=303)
    values = [clean(name, 140), clean(price, 30), clean(unit, 40), clean(description, 400)]
    if not values[0] or not values[1] or not values[2] or contains_forbidden(*values):
        raise HTTPException(400, "পণ্যের তথ্য সঠিকভাবে দিন।")
    new_image = None
    has_new_image = bool(image and image.filename)
    if has_new_image:
        if image.content_type not in ["image/jpeg", "image/png", "image/webp"]:
            raise HTTPException(400, "শুধু JPG, PNG বা WebP ছবি দিন।")
        new_image = await image.read(4 * 1024 * 1024 + 1)
        if len(new_image) > 4 * 1024 * 1024:
            raise HTTPException(400, "ছবির সাইজ ৪ MB-এর কম হতে হবে।")
    with db() as c:
        cur = c.execute(sql_placeholders("UPDATE partner_products SET name=?,price=?,unit=?,description=? WHERE id=? AND partner_request_id=?"),
            (values[0], values[1], values[2], values[3], product_id, partner_id))
        if not cur.rowcount:
            raise HTTPException(404, "পণ্য পাওয়া যায়নি।")
        if has_new_image:
            c.execute(sql_placeholders("UPDATE partner_products SET image_data=? WHERE id=? AND partner_request_id=?"), (new_image, product_id, partner_id))
        elif remove_image:
            c.execute(sql_placeholders("UPDATE partner_products SET image_data=NULL WHERE id=? AND partner_request_id=?"), (product_id, partner_id))
    log_action("partner:"+str(partner_id), "product_updated", "partner_product", product_id)
    return RedirectResponse("/partner/dashboard", status_code=303)

@app.post("/partner/product/delete")
def partner_product_delete(request: Request, product_id: int=Form(...)):
    partner_id = request.session.get("partner_id")
    if not partner_id:
        return RedirectResponse("/partner/login", status_code=303)
    with db() as c:
        cur = c.execute(sql_placeholders("DELETE FROM partner_products WHERE id=? AND partner_request_id=?"), (product_id, partner_id))
        if not cur.rowcount:
            raise HTTPException(404, "পণ্য পাওয়া যায়নি।")
    log_action("partner:"+str(partner_id), "product_deleted", "partner_product", product_id)
    return RedirectResponse("/partner/dashboard", status_code=303)

@app.post("/partner/product/status")
def partner_product_status(request: Request, product_id: int=Form(...), status: str=Form(...)):
    partner_id = request.session.get("partner_id")
    if not partner_id:
        return RedirectResponse("/partner/login", status_code=303)
    if status not in ["সক্রিয়", "বন্ধ"]:
        raise HTTPException(400, "অবৈধ স্ট্যাটাস।")
    with db() as c:
        cur = c.execute(sql_placeholders("UPDATE partner_products SET status=? WHERE id=? AND partner_request_id=?"),
                        (status, product_id, partner_id))
        if not cur.rowcount:
            raise HTTPException(404, "পণ্য পাওয়া যায়নি।")
    log_action("partner:"+str(partner_id), "product_status:"+status, "partner_product", product_id)
    return RedirectResponse("/partner/dashboard", status_code=303)

def require_admin(request: Request):
    if not request.session.get("admin"):
        return False
    return True

@app.get("/admin", response_class=HTMLResponse)
def admin_login(request: Request):
    if require_admin(request):
        return RedirectResponse("/admin/dashboard", status_code=303)
    body = """<main class="narrow"><section class="section-head"><div><div class="eyebrow">নিরাপদ প্রবেশ</div><h1>মালিক / সুপার অ্যাডমিন লগইন</h1></div></section>
<form class="form card" method="post" action="/admin/login"><label>ইউজারনেম<input name="username" required autocomplete="username"></label>
<label>পাসওয়ার্ড<input name="password" required type="password" autocomplete="current-password"></label>
<button class="btn primary" type="submit">লগইন</button><p class="fine">অ্যাডমিন লগইন `.env` ফাইলের credentials দিয়ে নিয়ন্ত্রিত হয়।</p></form></main>"""
    return page("মালিক লগইন", body)

@app.post("/admin/login")
def admin_login_post(request: Request, username: str=Form(...), password: str=Form(...)):
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        raise HTTPException(503, "অ্যাডমিন credentials সেট করা নেই। `.env` ফাইল পূরণ করুন।")
    ok = hmac.compare_digest(username, ADMIN_USERNAME) and hmac.compare_digest(password, ADMIN_PASSWORD)
    if not ok:
        log_action("unknown", "admin_login_failed", "auth", None)
        raise HTTPException(401, "ইউজারনেম বা পাসওয়ার্ড সঠিক নয়।")
    request.session.clear()
    request.session["admin"] = ADMIN_USERNAME
    log_action(ADMIN_USERNAME, "admin_login", "auth", None)
    return RedirectResponse("/admin/dashboard", status_code=303)

@app.post("/admin/logout")
def admin_logout(request: Request):
    actor = request.session.get("admin", "unknown")
    request.session.clear()
    log_action(actor, "admin_logout", "auth", None)
    return RedirectResponse("/admin", status_code=303)

@app.get("/admin/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if not require_admin(request):
        return RedirectResponse("/admin", status_code=303)
    with db() as c:
        orders = c.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 100").fetchall()
        partners = c.execute("SELECT * FROM partner_requests ORDER BY id DESC LIMIT 100").fetchall()
        sites = c.execute("SELECT * FROM partner_sites ORDER BY id DESC LIMIT 100").fetchall()
        audits = c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 40").fetchall()
    def order_row(r):
        return f"""<tr><td>IF-{r['id']:05d}<br><small>{esc(r['created_at'])}</small></td><td><b>{esc(r['name'])}</b><br>{esc(r['phone'])}<br>{esc(r['address'])}</td><td>{esc(r['product'])}<br>পরিমাণ: {esc(r['quantity'])}<br>{esc(r['payment'])}<br><small>{esc(r['notes'])}</small></td><td><form method="post" action="/admin/order-status"><input type="hidden" name="order_id" value="{r['id']}"><select name="status">{''.join(f'<option {"selected" if r["status"]==s else ""}>{s}</option>' for s in ["নতুন","ফোনে যোগাযোগ করতে হবে","নিশ্চিত","প্রসেসিং","ডেলিভারির পথে","সম্পন্ন","বাতিল"])}</select><button class="mini">আপডেট</button></form></td></tr>"""
    def partner_row(r):
        return f"""<tr class="partner-approval-row"><td><span class="mobile-label">আবেদন</span>IP-{r['id']:05d}<br><small>{esc(r['created_at'])}</small></td><td><span class="mobile-label">দোকান/যোগাযোগ</span><b>{esc(r['shop_name'])}</b><br>{esc(r['owner_name'])}<br>{esc(r['phone'])}<br>{esc(r['email'])}</td><td><span class="mobile-label">সাবডোমেইন/এলাকা</span><code>{esc(r['subdomain'])}</code><br>{esc(r['area'])}<br><small>{esc(r['description'])}</small></td><td class="partner-decision-cell"><span class="mobile-label">সিদ্ধান্ত</span><b>{esc(r['status'])}</b><form method="post" action="/admin/partner-status"><input type="hidden" name="partner_id" value="{r['id']}"><select name="status">{''.join(f'<option {"selected" if r["status"]==s else ""}>{s}</option>' for s in ["অপেক্ষমাণ","অনুমোদিত","বাতিল","স্থগিত"])}</select><button type="submit" class="mini">সিদ্ধান্ত সেভ</button></form></td></tr>"""
    def site_row(r):
        return f"""<tr><td>PS-{r['id']:05d}</td><td><b>{esc(r['shop_name'])}</b><br>{esc(r['owner_name'])}<br>{esc(r['phone'])}</td><td><code>{esc(r['subdomain'])}</code><br>{esc(r['area'])}</td><td>{esc(r['status'])}<br><small>{esc(r['created_at'])}</small></td></tr>"""
    body = f"""<main class="admin-main"><div class="admin-head"><div><div class="eyebrow">OWNER CONTROL</div><h1>সুপার অ্যাডমিন ড্যাশবোর্ড</h1><p>লগইন: {esc(request.session.get('admin'))}</p></div><form method="post" action="/admin/logout"><button class="btn light">লগআউট</button></form></div>
<div class="stats admin-stats"><div><b>{len(orders)}</b><span>সাম্প্রতিক অর্ডার</span></div><div><b>{len(partners)}</b><span>পার্টনার আবেদন</span></div><div><b>{len(sites)}</b><span>পার্টনার সাইট</span></div><div><b>{sum(1 for r in partners if r['status']=='অপেক্ষমাণ')}</b><span>অনুমোদনের অপেক্ষায়</span></div></div>
<section class="admin-section"><h2>অর্ডার ব্যবস্থাপনা</h2><div class="table-wrap"><table><thead><tr><th>নম্বর / সময়</th><th>ক্রেতা</th><th>অর্ডার</th><th>স্ট্যাটাস</th></tr></thead><tbody>{''.join(order_row(r) for r in orders) or '<tr><td colspan="4">এখনো কোনো অর্ডার নেই।</td></tr>'}</tbody></table></div></section>
<section class="admin-section"><h2>পার্টনার সাইট অনুমোদন</h2><div class="table-wrap"><table><thead><tr><th>আবেদন</th><th>দোকান/যোগাযোগ</th><th>সাবডোমেইন/এলাকা</th><th>সিদ্ধান্ত</th></tr></thead><tbody>{''.join(partner_row(r) for r in partners) or '<tr><td colspan="4">এখনো কোনো আবেদন নেই।</td></tr>'}</tbody></table></div><p class="fine">স্ট্যাটাস অনুমোদিত করলেও DNS বা সাবডোমেইন স্বয়ংক্রিয়ভাবে তৈরি হয় না।</p></section>
<section class="admin-section"><h2>পার্টনার সাইট ব্যবস্থাপনা</h2><div class="table-wrap"><table><thead><tr><th>সাইট আইডি</th><th>দোকান/মালিক</th><th>সাবডোমেইন/এলাকা</th><th>অবস্থা</th></tr></thead><tbody>{''.join(site_row(r) for r in sites) or '<tr><td colspan="4">এখনো কোনো অনুমোদিত পার্টনার সাইট নেই। কোনো আবেদনকে “অনুমোদিত” করলে এখানে যুক্ত হবে।</td></tr>'}</tbody></table></div><p class="fine">এটি অনুমোদিত সাইটের তালিকা ও অবস্থা পরিচালনা করে। বাস্তবে সাবডোমেইন চালু করতে নিজস্ব ডোমেইন, DNS ও হোস্টিং কনফিগারেশন লাগবে।</p></section>
<section class="admin-section"><h2>সাম্প্রতিক কার্যকলাপ</h2><div class="table-wrap"><table><thead><tr><th>সময়</th><th>ব্যবহারকারী</th><th>কাজ</th><th>বিষয়</th></tr></thead><tbody>{''.join(f"<tr><td>{esc(r['created_at'])}</td><td>{esc(r['actor'])}</td><td>{esc(r['action'])}</td><td>{esc(r['item_type'])} {esc(r['item_id'])}</td></tr>" for r in audits) or '<tr><td colspan="4">কোনো লগ নেই।</td></tr>'}</tbody></table></div></section></main>"""
    return page("সুপার অ্যাডমিন", body)

@app.post("/admin/order-status")
def order_status(request: Request, order_id: int=Form(...), status: str=Form(...)):
    if not require_admin(request):
        raise HTTPException(401, "লগইন প্রয়োজন।")
    allowed = ["নতুন","ফোনে যোগাযোগ করতে হবে","নিশ্চিত","প্রসেসিং","ডেলিভারির পথে","সম্পন্ন","বাতিল"]
    if status not in allowed: raise HTTPException(400, "অবৈধ স্ট্যাটাস।")
    with db() as c:
        cur = c.execute(sql_placeholders("UPDATE orders SET status=? WHERE id=?"), (status, order_id))
        if not cur.rowcount: raise HTTPException(404, "অর্ডার পাওয়া যায়নি।")
    log_action(request.session["admin"], "order_status:"+status, "order", order_id)
    return RedirectResponse("/admin/dashboard", status_code=303)

@app.post("/admin/partner-status")
def partner_status(request: Request, partner_id: int=Form(...), status: str=Form(...)):
    if not require_admin(request):
        raise HTTPException(401, "লগইন প্রয়োজন।")
    allowed = ["অপেক্ষমাণ","অনুমোদিত","বাতিল","স্থগিত"]
    if status not in allowed: raise HTTPException(400, "অবৈধ স্ট্যাটাস।")
    with db() as c:
        partner = c.execute(sql_placeholders("SELECT * FROM partner_requests WHERE id=?"), (partner_id,)).fetchone()
        if not partner: raise HTTPException(404, "আবেদন পাওয়া যায়নি।")
        c.execute(sql_placeholders("UPDATE partner_requests SET status=? WHERE id=?"), (status, partner_id))
        if status == "অনুমোদিত":
            c.execute(sql_placeholders("""INSERT INTO partner_sites
                (partner_request_id,shop_name,owner_name,phone,subdomain,area,status,created_at)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(partner_request_id) DO UPDATE SET
                shop_name=excluded.shop_name, owner_name=excluded.owner_name,
                phone=excluded.phone, subdomain=excluded.subdomain, area=excluded.area,
                status='সক্রিয়'"""),
                (partner["id"], partner["shop_name"], partner["owner_name"], partner["phone"],
                 partner["subdomain"], partner["area"], "সক্রিয়", now()))
        else:
            c.execute(sql_placeholders("UPDATE partner_sites SET status=? WHERE partner_request_id=?"),
                      ("বন্ধ", partner_id))
    log_action(request.session["admin"], "partner_status:"+status, "partner", partner_id)
    return RedirectResponse("/admin/dashboard", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def farmer_login():
    # Firebase Phone Auth UI. Configure Firebase test numbers in the console for zero-SMS testing.
    firebase_config = {
        "apiKey": "AIzaSyC8M0e0yNK-I61QxEty0HJsVN8a-cRylVo",
        "authDomain": "ifarmer-24643.firebaseapp.com",
        "projectId": "ifarmer-24643",
        "storageBucket": "ifarmer-24643.firebasestorage.app",
        "messagingSenderId": "973721838048",
        "appId": "1:973721838048:web:44d2011431c58d26880b85",
        "measurementId": "G-7RWZ4DJ0LW"
    }
    import json
    config_json = json.dumps(firebase_config)
    body = f"""
    <div class="eyebrow">iFarmer · কৃষকের অ্যাকাউন্ট</div>
    <h1>মোবাইল নম্বর দিয়ে লগইন</h1>
    <p>আপনার মোবাইল নম্বরে OTP পাঠিয়ে পরিচয় যাচাই করুন।</p>
    <div class="card form">
      <label>বাংলাদেশি মোবাইল নম্বর
        <input id="phone" type="tel" inputmode="tel" placeholder="+8801XXXXXXXXX" autocomplete="tel" required>
      </label>
      <div id="recaptcha-container"></div>
      <button id="send" class="btn primary" type="button">OTP পাঠান</button>
      <label>OTP কোড
        <input id="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="৬ সংখ্যার কোড">
      </label>
      <button id="verify" class="btn primary" type="button">যাচাই ও লগইন</button>
      <p id="status" role="status" aria-live="polite"></p>
      <button id="logout" class="btn light" type="button" hidden>লগআউট</button>
    </div>
    <p class="fine">SMS খরচ ছাড়া পরীক্ষা করতে Firebase Console → Authentication → Sign-in method → Phone-এ test phone number ও test code যোগ করুন। বাস্তব SMS পাঠালে চার্জ হতে পারে।</p>
    <p><a href="/">iFarmer হোমে ফিরুন</a></p>
    <script type="module">
      import {{ initializeApp }} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
      import {{ getAuth, RecaptchaVerifier, signInWithPhoneNumber, onAuthStateChanged, signOut }} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
      const app = initializeApp({config_json});
      const auth = getAuth(app);
      const status = document.getElementById("status");
      let confirmation = null;
      const recaptcha = new RecaptchaVerifier(auth, "recaptcha-container", {{
        size: "normal",
        callback: () => {{ document.getElementById("send").disabled = false; }},
        "expired-callback": () => {{ status.textContent = "reCAPTCHA মেয়াদ শেষ—আবার যাচাই করুন।"; }}
      }});
      document.getElementById("send").disabled = true;
      recaptcha.render().catch(e => status.textContent = e.message);
      document.getElementById("send").addEventListener("click", async () => {{
        const phone = document.getElementById("phone").value.trim();
        if (!/^\+8801[3-9]\d{{8}}$/.test(phone)) {{
          status.textContent = "নম্বরটি +8801XXXXXXXXX ফরম্যাটে লিখুন।"; return;
        }}
        try {{
          confirmation = await signInWithPhoneNumber(auth, phone, recaptcha);
          status.textContent = "OTP পাঠানো হয়েছে। কোড লিখে যাচাই করুন।";
        }} catch (e) {{ status.textContent = "OTP পাঠানো যায়নি: " + e.message; }}
      }});
      document.getElementById("verify").addEventListener("click", async () => {{
        if (!confirmation) {{ status.textContent = "আগে OTP পাঠান।"; return; }}
        try {{
          const result = await confirmation.confirm(document.getElementById("code").value.trim());
          status.textContent = "লগইন সফল! " + result.user.phoneNumber;
        }} catch (e) {{ status.textContent = "OTP যাচাই হয়নি: " + e.message; }}
      }});
      onAuthStateChanged(auth, user => {{
        document.getElementById("logout").hidden = !user;
        if (user) status.textContent = "লগইন করা নম্বর: " + user.phoneNumber;
      }});
      document.getElementById("logout").addEventListener("click", async () => {{
        await signOut(auth); status.textContent = "লগআউট করা হয়েছে।";
      }});
    </script>
    """
    return page("মোবাইল OTP লগইন", body)

@app.get("/privacy", response_class=HTMLResponse)
def privacy():
    return page("গোপনীয়তা", """<main class="narrow section"><h1>গোপনীয়তা নীতি</h1><p>এই স্টার্টার সাইটে জমা দেওয়া অর্ডার ও পার্টনার আবেদন স্থানীয় SQLite ডেটাবেসে সংরক্ষিত হয়। লাইভ করার আগে ডেটা ব্যবহারের উদ্দেশ্য, সংরক্ষণকাল, যোগাযোগের তথ্য এবং ব্যবহারকারীর অধিকার নিয়ে পূর্ণ নীতি প্রকাশ করুন।</p><p>এটি আইনি পরামর্শ নয়।</p></main>""")

@app.get("/terms", response_class=HTMLResponse)
def terms():
    return page("শর্তাবলি", """<main class="narrow section"><h1>ব্যবহারের শর্তাবলি</h1><p>অর্ডারের অনুরোধ চূড়ান্ত বিক্রয় নয়। পণ্যের প্রাপ্যতা, মূল্য, ডেলিভারি, পেমেন্ট ও ফেরতের শর্ত বিক্রেতার সঙ্গে নিশ্চিত করতে হবে। কৃষি উপকরণ ব্যবহারে পণ্যের লেবেল ও প্রযোজ্য আইন অনুসরণ করুন। লাইভ করার আগে আপনার ব্যবসার উপযোগী পূর্ণ শর্তাবলি যুক্ত করুন।</p></main>""")
