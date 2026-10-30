import json
from urllib.request import urlopen
from urllib.parse import urlencode
from fastapi import APIRouter, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
import html

router = APIRouter()
CITIES = {
    "ঢাকা": (23.8103, 90.4125), "নরসিংদী": (23.9229, 90.7177),
    "ময়মনসিংহ": (24.7471, 90.4203), "কুমিল্লা": (23.4607, 91.1809),
    "চট্টগ্রাম": (22.3569, 91.7832), "রাজশাহী": (24.3745, 88.6042),
    "রংপুর": (25.7439, 89.2752), "খুলনা": (22.8456, 89.5403),
    "বরিশাল": (22.7010, 90.3535), "সিলেট": (24.8949, 91.8687),
    "যশোর": (23.1667, 89.2167), "বগুড়া": (24.8465, 89.3773)
}
CROPS = ["ধান","গম","ভুট্টা","আলু","টমেটো","মরিচ","বেগুন","পাট","পেঁয়াজ","রসুন","শাকসবজি","আম","লিচু","কলা"]
UNITS = {"একর":1.0,"শতক":0.01,"বিঘা":0.33,"হেক্টর":2.471}

def shell(title, body):
    return f"""<!doctype html><html lang="bn"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#176b45"><title>{title} · iFarmer</title><link rel="stylesheet" href="/static/style.css"><body><header class="top"><a class="brand" href="/">🌱 iFarmer</a><nav><a href="/">হোম</a><a href="/agri">কৃষি সহায়ক</a></nav></header><main class="narrow section">{body}</main><footer><b>iFarmer</b><p>কৃষির ডিজিটাল সহযাত্রী</p></footer></body></html>"""

@router.get("/agri", response_class=HTMLResponse)
def agri_home():
    body = """<div class="eyebrow">কৃষকের ডিজিটাল সহকারী</div><h1>কৃষি সহায়ক</h1><p>আবহাওয়া, সার ও কীটনাশকের হিসাব এবং ফসলের ছবি জমা দেওয়ার সুবিধা।</p><div class="cards">
    <article class="card"><h2>🌦️ দৈনিক আবহাওয়া</h2><p>জেলা নির্বাচন করে তাপমাত্রা, বৃষ্টি, আর্দ্রতা ও বাতাসের তথ্য দেখুন।</p><a class="btn primary" href="/agri/weather">আবহাওয়া দেখুন</a></article>
    <article class="card"><h2>🧮 সার হিসাব</h2><p>কৃষি কর্মকর্তার সুপারিশকৃত একক মাত্রা দিয়ে জমির মোট পরিমাণ হিসাব করুন।</p><a class="btn primary" href="/agri/fertilizer">হিসাব করুন</a></article>
    <article class="card"><h2>🧴 কীটনাশক হিসাব</h2><p>শুধু পণ্যের অনুমোদিত লেবেলে লেখা মাত্রা বসিয়ে পরিমাণ হিসাব করুন।</p><a class="btn primary" href="/agri/pesticide">লেবেলভিত্তিক হিসাব</a></article>
    <article class="card"><h2>📷 রোগ-পোকা শনাক্তকরণ</h2><p>ফসলের ছবি জমা দিন। AI শনাক্তকরণ চালু না হওয়া পর্যন্ত নিশ্চিত রোগনির্ণয় দেখানো হবে না।</p><a class="btn primary" href="/agri/diagnose">ছবি জমা দিন</a></article></div>"""
    return shell("কৃষি সহায়ক", body)

@router.get("/agri/weather", response_class=HTMLResponse)
def weather_form():
    opts = "".join(f'<option>{html.escape(c)}</option>' for c in CITIES)
    return shell("আবহাওয়া", f"""<h1>জেলার আবহাওয়া</h1><form class="form card" method="post"><label>জেলা/এলাকা<select name="city">{opts}</select></label><button class="btn primary">আজকের আবহাওয়া দেখুন</button></form><p class="fine">তথ্য Open-Meteo আবহাওয়া সেবা থেকে আসে। এটি পূর্বাভাস; স্থানীয় মাঠের অবস্থা ভিন্ন হতে পারে।</p>""")

@router.post("/agri/weather", response_class=HTMLResponse)
def weather_result(city: str=Form(...)):
    if city not in CITIES: raise HTTPException(400, "এলাকা নির্বাচন করুন")
    lat, lon = CITIES[city]
    query = urlencode({"latitude":lat,"longitude":lon,"current":"temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m","daily":"precipitation_probability_max,temperature_2m_max,temperature_2m_min","timezone":"Asia/Dhaka","forecast_days":1})
    try:
        with urlopen("https://api.open-meteo.com/v1/forecast?"+query, timeout=8) as r: data=json.loads(r.read().decode())
        cur=data["current"]; day=data["daily"]
        rain=day["precipitation_probability_max"][0]
        advice="বৃষ্টির সম্ভাবনা বেশি—সেচ ও স্প্রে করার আগে স্থানীয় আকাশের অবস্থা দেখুন।" if rain >= 60 else "বৃষ্টির সম্ভাবনা তুলনামূলক কম। জমির আর্দ্রতা দেখে সেচ দিন।"
        body=f"""<h1>{html.escape(city)}: আজকের আবহাওয়া</h1><div class="card"><h2>{cur['temperature_2m']}°C</h2><p>আর্দ্রতা: {cur['relative_humidity_2m']}%</p><p>বর্তমান বৃষ্টিপাত: {cur['precipitation']} মিমি</p><p>বাতাস: {cur['wind_speed_10m']} কিমি/ঘণ্টা</p><p>সর্বোচ্চ/সর্বনিম্ন: {day['temperature_2m_max'][0]}° / {day['temperature_2m_min'][0]}°C</p><p>বৃষ্টির সম্ভাবনা: {rain}%</p><b>{advice}</b></div><p class="fine">আবহাওয়ার তথ্য {html.escape(cur['time'])} সময়ের। কৃষিকাজের সিদ্ধান্তের আগে স্থানীয় পূর্বাভাস যাচাই করুন।</p><a href="/agri/weather">অন্য এলাকা</a>"""
    except Exception:
        body="<h1>এখন আবহাওয়ার তথ্য পাওয়া যাচ্ছে না</h1><p>ইন্টারনেট সংযোগ বা আবহাওয়া সেবা পরে আবার চেষ্টা করুন।</p><a href='/agri/weather'>আবার চেষ্টা করুন</a>"
    return shell("আবহাওয়ার ফলাফল", body)

def calc_form(kind):
    cropopts="".join(f"<option>{c}</option>" for c in CROPS)
    return shell(kind, f"""<h1>{kind}</h1><form class="form card" method="post"><label>ফসল<select name="crop">{cropopts}</select></label><label>জমির পরিমাণ<input name="area" type="number" min="0.001" step="any" required></label><label>জমির একক<select name="unit">{''.join(f'<option>{u}</option>' for u in UNITS)}</select></label><label>প্রতি এককে সুপারিশকৃত মাত্রা (কেজি/লিটার/গ্রাম)<input name="rate" type="number" min="0" step="any" required></label><label>মাত্রার একক<input name="measure" maxlength="25" placeholder="যেমন কেজি বা গ্রাম" required></label><button class="btn primary">হিসাব করুন</button></form><p class="fine">সঠিক মাত্রা ফসল, মাটি, জাত, বয়স ও পণ্যের লেবেল/সরকারি সুপারিশের ওপর নির্ভর করে। এখানে কোনো ডিফল্ট ডোজ দেওয়া হয় না; অনুমোদিত সুপারিশ থেকে মাত্রা লিখুন।</p>""")

@router.get("/agri/fertilizer", response_class=HTMLResponse)
def fertilizer_form(): return calc_form("সার হিসাব")
@router.get("/agri/pesticide", response_class=HTMLResponse)
def pesticide_form(): return calc_form("কীটনাশক হিসাব")

@router.post("/agri/{kind}", response_class=HTMLResponse)
def calculate(kind: str, crop: str=Form(...), area: float=Form(...), unit: str=Form(...), rate: float=Form(...), measure: str=Form(...)):
    if kind not in ("fertilizer","pesticide") or crop not in CROPS or unit not in UNITS or area<=0 or rate<0:
        raise HTTPException(400,"সঠিক তথ্য দিন")
    total=area*UNITS[unit]*rate
    label="সার" if kind=="fertilizer" else "কীটনাশক"
    warning = "কীটনাশকের ক্ষেত্রে শুধু সংশ্লিষ্ট ফসল ও পোকার জন্য নিবন্ধিত পণ্যের লেবেল অনুসরণ করুন। PPE, অপেক্ষাকাল (PHI), পুনঃপ্রবেশ সময় ও বাতাসের নির্দেশনা মানুন।" if kind=="pesticide" else "মাটি পরীক্ষা ও কৃষি সম্প্রসারণ অধিদপ্তরের ফসলভিত্তিক সুপারিশ মিলিয়ে নিন।"
    return shell("হিসাবের ফল",f"<h1>{label}র হিসাব</h1><div class='card'><p>ফসল: {html.escape(crop)}</p><p>জমি: {area:g} {html.escape(unit)}</p><h2>মোট প্রয়োজন: {total:.3f} {html.escape(measure)}</h2></div><p class='fine'>{warning}</p><a href='/agri'>কৃষি সহায়কে ফিরুন</a>")

@router.get("/agri/diagnose", response_class=HTMLResponse)
def diagnose_form():
    crops="".join(f"<option>{c}</option>" for c in CROPS)
    return shell("রোগ-পোকা ছবি",f"""<h1>ফসলের রোগ-পোকার ছবি জমা দিন</h1><form class="form card" method="post" enctype="multipart/form-data"><label>ফসল<select name="crop">{crops}</select></label><label>জেলা<input name="area" maxlength="80" required placeholder="যেমন নরসিংদী"></label><label>লক্ষণ/সমস্যা<input name="symptoms" maxlength="500" placeholder="পাতায় দাগ, পোকা, পচন ইত্যাদি"></label><label>ছবি (JPG/PNG/WebP)<input type="file" name="photo" accept="image/jpeg,image/png,image/webp" required></label><button class="btn primary">ছবি জমা দিন</button></form><p class="fine">সতর্কতা: এই মুহূর্তে AI রোগ শনাক্তকরণ মডেল সংযুক্ত নয়। ছবি গ্রহণ করা হলেও স্বয়ংক্রিয় রোগনির্ণয় বা কীটনাশক পরামর্শ দেওয়া হবে না। নিশ্চিত পরামর্শের জন্য কৃষি কর্মকর্তা/উপসহকারী কৃষি কর্মকর্তার সঙ্গে যোগাযোগ করুন।</p>""")

@router.post("/agri/diagnose", response_class=HTMLResponse)
async def diagnose_submit(crop: str=Form(...), area: str=Form(...), symptoms: str=Form(""), photo: UploadFile=File(...)):
    if crop not in CROPS or photo.content_type not in ("image/jpeg","image/png","image/webp"):
        raise HTTPException(400,"ফসল ও JPG/PNG/WebP ছবি দিন")
    data=await photo.read(5*1024*1024+1)
    if len(data)>5*1024*1024: raise HTTPException(400,"ছবি ৫ MB-এর কম হতে হবে")
    if not data: raise HTTPException(400,"ছবি খালি")
    return shell("ছবি গ্রহণ",f"<h1>ছবি গ্রহণ করা হয়েছে</h1><p>ফসল: {html.escape(crop)} · এলাকা: {html.escape(area)}</p><p>ছবিটি আপলোড হয়েছে, তবে AI মডেল সংযুক্ত না থাকায় রোগ শনাক্ত করা হয়নি।</p><p>লক্ষণ: {html.escape(symptoms)}</p><p><b>এখনই অনুমান করে কীটনাশক প্রয়োগ করবেন না।</b> পরিষ্কার আলোতে আক্রান্ত অংশ ও পুরো গাছের আলাদা ছবি তুলে স্থানীয় কৃষি কর্মকর্তাকে দেখান।</p><a href='/agri'>ফিরুন</a>")
