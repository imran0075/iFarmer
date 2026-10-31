import json
from ai_diagnosis import diagnose_crop_image
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
    <article class="card"><h2>📚 সরকারি সার সুপারিশ</h2><p>BARC, Crop Zoning ও DAE-এর সরকারি কৃষি তথ্যসূত্র দেখুন।</p><a class="btn primary" href="/agri/official-data">সরকারি তথ্য দেখুন</a></article><article class="card"><h2>🌦️ দৈনিক আবহাওয়া</h2><p>জেলা নির্বাচন করে তাপমাত্রা, বৃষ্টি, আর্দ্রতা ও বাতাসের তথ্য দেখুন।</p><a class="btn primary" href="/agri/weather">আবহাওয়া দেখুন</a></article>
    <article class="card"><h2>🧮 সার হিসাব</h2><p>কৃষি কর্মকর্তার সুপারিশকৃত একক মাত্রা দিয়ে জমির মোট পরিমাণ হিসাব করুন।</p><a class="btn primary" href="/agri/fertilizer">হিসাব করুন</a></article>
    <article class="card"><h2>🧴 কীটনাশক হিসাব</h2><p>শুধু পণ্যের অনুমোদিত লেবেলে লেখা মাত্রা বসিয়ে পরিমাণ হিসাব করুন।</p><a class="btn primary" href="/agri/pesticide">লেবেলভিত্তিক হিসাব</a></article>
    <article class="card"><h2>📷 রোগ-পোকা শনাক্তকরণ</h2><p>ফসলের ছবি জমা দিন। AI শনাক্তকরণ চালু না হওয়া পর্যন্ত নিশ্চিত রোগনির্ণয় দেখানো হবে না।</p><a class="btn primary" href="/agri/diagnose">ছবি জমা দিন</a></article></div>"""
    return shell("কৃষি সহায়ক", body)

@router.get("/agri/official-data", response_class=HTMLResponse)
def official_data():
    # Verified starter records transcribed from DAE BAMIS public crop package.
    # These are national/seasonal package values, not soil-test/union-specific advice.
    maize = {
        "Rabi": {"Urea": "172–312", "TSP": "168–216", "MOP": "96–144", "Gypsum": "144–168", "Zinc sulphate": "10–15", "Boric acid": "5–7 (প্রয়োজন অনুযায়ী)", "Gobar": "4–6"},
        "Kharif-1": {"Urea": "216–268", "TSP": "132–216", "MOP": "72–120", "Gypsum": "96–144", "Zinc sulphate": "7–12", "Boric acid": "5–7 (প্রয়োজন অনুযায়ী)", "Gobar": "4–6"}
    }
    rows = "".join(
        f"<tr><td>{html.escape(season)}</td><td>{html.escape(fertilizer)}</td><td>{html.escape(rate)}</td><td>কেজি/হেক্টর</td></tr>"
        for season, values in maize.items() for fertilizer, rate in values.items()
    )
    body = f"""<div class="eyebrow">সরকারি কৃষি তথ্য</div><h1>ফসলভিত্তিক সরকারি সার সুপারিশ</h1>
<p>প্রথম পর্যায়: নরসিংদী জেলার রায়পুরা উপজেলা। নিচে সরকারি BAMIS ফসল উৎপাদন প্যাকেজ থেকে যাচাই করে একটি প্রাথমিক রেকর্ড যুক্ত করা হয়েছে।</p>
<div class="card"><h2>🌽 ভুট্টা — সার সুপারিশ</h2><p><b>উৎস:</b> DAE BAMIS, ভুট্টা উৎপাদন প্যাকেজ।</p>
<table><thead><tr><th>মৌসুম</th><th>সার</th><th>মাত্রা</th><th>একক</th></tr></thead><tbody>{rows}</tbody></table>
<p class="fine">BAMIS প্যাকেজে দেওয়া জাতীয় মৌসুমভিত্তিক পরিসর। এটি রায়পুরার নির্দিষ্ট জমির মাটি-পরীক্ষাভিত্তিক সুপারিশ নয়। মাটির ধরন, জাত ও স্থানীয় কৃষি কর্মকর্তার পরামর্শ অনুযায়ী চূড়ান্ত মাত্রা নির্ধারণ করুন।</p>
<a href="https://www.bamis.gov.bd/en/croppnp/1/all/8/" target="_blank" rel="noopener">BAMIS-এর মূল ভুট্টা উৎপাদন প্যাকেজ</a></div>
<div class="card"><h2>🌾 বোরো ধান — সরকারি সার সুপারিশ</h2>
<p><b>উৎস:</b> DAE BAMIS, বোরো ধান উৎপাদন প্যাকেজ।</p>
<table><thead><tr><th>জমির ধরন</th><th>ইউরিয়া</th><th>TSP</th><th>MP</th><th>জিপসাম</th><th>জিংক সালফেট</th><th>একক</th></tr></thead><tbody>
<tr><td>নিচু জমি, দীর্ঘমেয়াদি</td><td>40</td><td>13</td><td>22</td><td>15</td><td>1.5</td><td>কেজি/বিঘা</td></tr>
<tr><td>মাঝারি জমি, স্বল্পমেয়াদি</td><td>35</td><td>12</td><td>20</td><td>15</td><td>1.5</td><td>কেজি/বিঘা</td></tr>
<tr><td>হাওর অঞ্চল</td><td>27</td><td>12</td><td>22</td><td>8</td><td>1.5</td><td>কেজি/বিঘা</td></tr></tbody></table>
<p class="fine">ইউরিয়া ৩ কিস্তিতে প্রয়োগের নির্দেশনাও BAMIS প্যাকেজে দেওয়া আছে। জমির ধরন, জাত ও স্থানীয় পরামর্শ অনুযায়ী প্রয়োগ করুন।</p>
<a href="https://www.bamis.gov.bd/en/croppnp/1/all/75/" target="_blank" rel="noopener">মূল বোরো ধান প্যাকেজ</a></div>
<div class="card"><h2>🌿 গম — সরকারি সার সুপারিশ</h2><p><b>উৎস:</b> DAE BAMIS, গম উৎপাদন প্যাকেজ।</p>
<table><thead><tr><th>সার</th><th>মাত্রা</th><th>একক</th></tr></thead><tbody>
<tr><td>ইউরিয়া (জমি তৈরির সময়)</td><td>150–175</td><td>কেজি/হেক্টর</td></tr>
<tr><td>TSP</td><td>135–150</td><td>কেজি/হেক্টর</td></tr>
<tr><td>পটাশ</td><td>100–110</td><td>কেজি/হেক্টর</td></tr>
<tr><td>জিপসাম</td><td>110–125</td><td>কেজি/হেক্টর</td></tr>
<tr><td>জিংক সালফেট</td><td>12.5</td><td>কেজি/হেক্টর</td></tr>
<tr><td>বোরিক অ্যাসিড</td><td>6.5</td><td>কেজি/হেক্টর</td></tr>
<tr><td>ইউরিয়া (৩ পাতার পর্যায়ে, সেচের সঙ্গে)</td><td>75–90</td><td>কেজি/হেক্টর</td></tr></tbody></table>
<a href="https://www.bamis.gov.bd/en/croppnp/1/all/9/" target="_blank" rel="noopener">মূল গম প্যাকেজ</a></div>
<div class="card"><h2>🥔 আলু — সরকারি সার সুপারিশ</h2><p><b>উৎস:</b> DAE BAMIS কৃষি আবহাওয়া বুলেটিনে প্রকাশিত আলু নির্দেশনা; জাতভেদে মাত্রা পরিবর্তন হতে পারে।</p>
<table><thead><tr><th>সার</th><th>মাত্রা</th><th>একক</th></tr></thead><tbody>
<tr><td>ইউরিয়া</td><td>160–175</td><td>কেজি/হেক্টর</td></tr>
<tr><td>TSP</td><td>200–220</td><td>কেজি/হেক্টর</td></tr>
<tr><td>MOP</td><td>250–300</td><td>কেজি/হেক্টর</td></tr>
<tr><td>জিপসাম</td><td>100–120</td><td>কেজি/হেক্টর</td></tr>
<tr><td>জিংক সালফেট</td><td>8–10</td><td>কেজি/হেক্টর</td></tr>
<tr><td>বোরিক অ্যাসিড</td><td>6–9</td><td>কেজি/হেক্টর</td></tr></tbody></table>
<p class="fine">প্রাথমিক/বেসাল প্রয়োগের নির্দেশনা। ইউরিয়ার টপ ড্রেসিংয়ের জন্য BAMIS বুলেটিনে রোপণের ৩০–৩৫ দিন পর ১৬০–১৭৫ কেজি/হেক্টর উল্লেখ আছে; জাত ও নির্দেশনা মিলিয়ে নিন।</p>
<a href="https://www.bamis.gov.bd/en/bulletin/view/38262/" target="_blank" rel="noopener">BAMIS আলু নির্দেশনা</a></div>
<h2>সরকারি তথ্যসূত্র</h2><ul>
<li><a href="https://portal.cropzoning.gov.bd/" target="_blank" rel="noopener">BARC কৃষি পরামর্শক বাতায়ন / Crop Zoning</a></li>
<li><a href="https://portal.cropzoning.gov.bd/cropSuitability" target="_blank" rel="noopener">উপজেলাভিত্তিক ফসলের উপযোগিতা</a></li>
<li><a href="https://apps.barc.gov.bd/fertilizer_recommendation/FRG%20English%2030.10.2024.pdf" target="_blank" rel="noopener">BARC Fertilizer Recommendation Guide 2024 (PDF)</a></li>
<li><a href="https://www.bamis.gov.bd/" target="_blank" rel="noopener">DAE BAMIS — ফসল উৎপাদন প্যাকেজ ও কৃষি পরামর্শ</a></li>
</ul>
<p class="fine"><b>ডেটার অবস্থা:</b> ভুট্টা, বোরো ধান, গম ও আলুর প্রাথমিক সরকারি সুপারিশ যুক্ত হয়েছে। এগুলো জাতীয়/মৌসুমভিত্তিক প্যাকেজ বা BAMIS নির্দেশনা; রায়পুরার নির্দিষ্ট জমির মাটি-পরীক্ষাভিত্তিক ডোজ নয়। স্থানীয় কৃষি কর্মকর্তার পরামর্শ এবং মাটি পরীক্ষার ফল প্রাধান্য পাবে। রায়পুরার জমির নির্দিষ্ট ডোজের জন্য খামারি অ্যাপ/স্থানীয় কৃষি কর্মকর্তার মাটি- ও জমিভিত্তিক সুপারিশ প্রাধান্য পাবে।</p>
<a class="btn primary" href="/agri">কৃষি সহায়কে ফিরুন</a>"""
    return shell("সরকারি সার সুপারিশ", body)

@router.get("/agri/weather", response_class=HTMLResponse)
def weather_form():
    opts = "".join(f'<option>{html.escape(c)}</option>' for c in CITIES)
    return shell("আবহাওয়া", f"""<div class="eyebrow">দৈনিক আবহাওয়া বার্তা</div><h1>আপনার এলাকার আবহাওয়া</h1>
<div class="card"><p>পাতা খোলার সঙ্গে সঙ্গে আপনার ফোনের অবস্থান শনাক্ত করার অনুমতি চাওয়া হবে। অনুমতি দিলে আপনার অবস্থানের আবহাওয়া দেখাবে।</p>
<button class="btn primary" type="button" onclick="detectMyLocation()">📍 লোকেশন শনাক্তকরণ</button>
<p id="gps-status" class="fine" role="status" aria-live="polite">আপনার অবস্থানের অনুমতি চাওয়া হচ্ছে…</p>
<div id="gps-weather"></div></div>
<form class="form card" method="post"><label>জেলা/এলাকা<select name="city">{opts}</select></label><button class="btn primary">জেলার আবহাওয়া দেখুন</button></form>
<p class="fine">লোকেশন অনুমতি না দিলে জেলা নির্বাচন করে আবহাওয়া দেখা যাবে। আপনার অবস্থান এই পাতায় আবহাওয়া দেখানোর জন্য ব্যবহার করা হবে।</p>
<script>
async function detectMyLocation() {{
  const status = document.getElementById('gps-status');
  const result = document.getElementById('gps-weather');
  if (!navigator.geolocation) {{ status.textContent = 'আপনার ব্রাউজারে GPS লোকেশন সুবিধা নেই।'; return; }}
  status.textContent = 'আপনার অবস্থানের অনুমতি চাওয়া হচ্ছে…';
  result.innerHTML = '';
  navigator.geolocation.getCurrentPosition(async function(position) {{
    const lat = position.coords.latitude;
    const lon = position.coords.longitude;
    status.textContent = 'অবস্থান শনাক্ত হয়েছে। আবহাওয়ার তথ্য আনা হচ্ছে…';
    try {{
      const url = 'https://api.open-meteo.com/v1/forecast?latitude=' + lat + '&longitude=' + lon + '&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m&daily=precipitation_probability_max,temperature_2m_max,temperature_2m_min&timezone=Asia%2FDhaka&forecast_days=1';
      const response = await fetch(url);
      if (!response.ok) throw new Error('weather unavailable');
      const data = await response.json();
      const cur = data.current;
      const rain = data.daily.precipitation_probability_max[0];
      status.textContent = 'আপনার বর্তমান অবস্থানের আবহাওয়া';
      result.innerHTML = '<div class="card"><h2>এখন ' + cur.temperature_2m + '°C</h2><p>আর্দ্রতা: ' + cur.relative_humidity_2m + '%</p><p>বৃষ্টিপাত: ' + cur.precipitation + ' মিমি</p><p>বাতাস: ' + cur.wind_speed_10m + ' কিমি/ঘণ্টা</p><p>আজ বৃষ্টির সম্ভাবনা: ' + (rain == null ? 'তথ্য নেই' : rain + '%') + '</p><p>সর্বোচ্চ: ' + data.daily.temperature_2m_max[0] + '°C · সর্বনিম্ন: ' + data.daily.temperature_2m_min[0] + '°C</p></div>';
    }} catch (e) {{
      status.textContent = 'লোকেশন পাওয়া গেছে, কিন্তু আবহাওয়ার তথ্য আনা যায়নি। ইন্টারনেট পরীক্ষা করে আবার চেষ্টা করুন।';
    }}
  }}, function(error) {{
    const messages = {{1:'লোকেশন অনুমতি দেওয়া হয়নি। Chrome Site settings থেকে Location → Allow করুন।',2:'ফোনের অবস্থান পাওয়া যাচ্ছে না। ফোনের Location চালু করুন।',3:'লোকেশন পেতে সময় শেষ হয়েছে। আবার চেষ্টা করুন।'}};
    status.textContent = messages[error.code] || 'লোকেশন পাওয়া যায়নি। আবার চেষ্টা করুন.';
  }}, {{enableHighAccuracy:true, timeout:15000, maximumAge:60000}});
}}
window.addEventListener('load', detectMyLocation);
</script>""")

@router.post("/agri/weather", response_class=HTMLResponse)
def weather_result(city: str=Form(...)):
    if city not in CITIES: raise HTTPException(400, "এলাকা নির্বাচন করুন")
    lat, lon = CITIES[city]
    query = urlencode({
        "latitude":lat,"longitude":lon,
        "current":"temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "daily":"weather_code,precipitation_probability_max,precipitation_sum,temperature_2m_max,temperature_2m_min",
        "timezone":"Asia/Dhaka","forecast_days":7
    })
    try:
        with urlopen("https://api.open-meteo.com/v1/forecast?"+query, timeout=12) as r:
            data=json.loads(r.read().decode())
        cur=data["current"]; day=data["daily"]
        rain=day["precipitation_probability_max"][0] or 0
        advice="বৃষ্টির সম্ভাবনা বেশি—সেচের আগে জমির অবস্থা দেখুন এবং স্প্রে করার সময় বৃষ্টি/বাতাসের নির্দেশনা মানুন।" if rain >= 60 else "বৃষ্টির সম্ভাবনা কম। জমির আর্দ্রতা ও ফসলের অবস্থা দেখে সেচ দিন।"
        weather_labels={0:"পরিষ্কার",1:"মূলত পরিষ্কার",2:"আংশিক মেঘলা",3:"মেঘলা",45:"কুয়াশা",48:"ঘন কুয়াশা",51:"হালকা গুঁড়ি বৃষ্টি",53:"গুঁড়ি বৃষ্টি",55:"ঘন গুঁড়ি বৃষ্টি",61:"হালকা বৃষ্টি",63:"মাঝারি বৃষ্টি",65:"ভারী বৃষ্টি",71:"হালকা তুষার",80:"হালকা বৃষ্টির ঝাপটা",81:"মাঝারি বৃষ্টির ঝাপটা",82:"ভারী বৃষ্টির ঝাপটা",95:"বজ্রসহ বৃষ্টি"}
        forecast_rows=[]
        for i, date in enumerate(day["time"]):
            code=day["weather_code"][i]
            label=weather_labels.get(code,"পরিবর্তনশীল আবহাওয়া")
            p=day["precipitation_probability_max"][i]
            p="তথ্য নেই" if p is None else f"{p}%"
            forecast_rows.append(f"<tr><td>{html.escape(date)}</td><td>{html.escape(label)}</td><td>{day['temperature_2m_min'][i]}°–{day['temperature_2m_max'][i]}°C</td><td>{p}</td><td>{day['precipitation_sum'][i]} মিমি</td></tr>")
        rows="".join(forecast_rows)
        body=f"""<h1>{html.escape(city)}: আবহাওয়া বার্তা</h1>
<div class="card"><h2>এখন {cur['temperature_2m']}°C</h2><p>আর্দ্রতা: {cur['relative_humidity_2m']}%</p><p>বর্তমান বৃষ্টিপাত: {cur['precipitation']} মিমি</p><p>বাতাস: {cur['wind_speed_10m']} কিমি/ঘণ্টা</p><b>{advice}</b></div>
<h2>আগামী ৭ দিনের পূর্বাভাস</h2><div class="card"><table><thead><tr><th>তারিখ</th><th>আবহাওয়া</th><th>তাপমাত্রা</th><th>বৃষ্টির সম্ভাবনা</th><th>বৃষ্টির পরিমাণ</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="fine">সর্বশেষ তথ্য: {html.escape(cur['time'])} (বাংলাদেশ সময়)। এই বার্তা Open-Meteo পূর্বাভাসের ওপর ভিত্তি করে; স্থানীয় মাঠের অবস্থা ভিন্ন হতে পারে। কৃষিকাজের সিদ্ধান্তের আগে স্থানীয় পূর্বাভাস/কৃষি কর্মকর্তার পরামর্শ যাচাই করুন।</p><a class="btn primary" href="/agri/weather">অন্য জেলা দেখুন</a>"""
    except Exception:
        body="<h1>আবহাওয়ার তথ্য এখন পাওয়া যাচ্ছে না</h1><p>সার্ভার বা আবহাওয়া সেবার সংযোগে সমস্যা হতে পারে। ইন্টারনেট সংযোগ পরীক্ষা করে কিছুক্ষণ পর আবার চেষ্টা করুন।</p><a class='btn primary' href='/agri/weather'>আবার চেষ্টা করুন</a>"
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
    return shell("রোগ-পোকা ছবি",f"""<h1>ফসলের রোগ-পোকার ছবি জমা দিন</h1><form class="form card" method="post" enctype="multipart/form-data"><label>ফসল<select name="crop">{crops}</select></label><label>জেলা<input name="area" maxlength="80" required placeholder="যেমন নরসিংদী"></label><label>লক্ষণ/সমস্যা<input name="symptoms" maxlength="500" placeholder="পাতায় দাগ, পোকা, পচন ইত্যাদি"></label><label>ছবি (JPG/PNG/WebP)<input type="file" name="photo" accept="image/jpeg,image/png,image/webp" capture="environment" required></label><button class="btn primary">ছবি জমা দিন</button></form><p class="fine">সতর্কতা: এই মুহূর্তে AI রোগ শনাক্তকরণ মডেল সংযুক্ত নয়। ছবি গ্রহণ করা হলেও স্বয়ংক্রিয় রোগনির্ণয় বা কীটনাশক পরামর্শ দেওয়া হবে না। নিশ্চিত পরামর্শের জন্য কৃষি কর্মকর্তা/উপসহকারী কৃষি কর্মকর্তার সঙ্গে যোগাযোগ করুন।</p>""")

@router.post("/agri/diagnose", response_class=HTMLResponse)
async def diagnose_submit(crop: str=Form(...), area: str=Form(...), symptoms: str=Form(""), photo: UploadFile=File(...)):
    if crop not in CROPS or photo.content_type not in ("image/jpeg","image/png","image/webp"):
        raise HTTPException(400,"ফসল ও JPG/PNG/WebP ছবি দিন")
    data=await photo.read(5*1024*1024+1)
    if len(data)>5*1024*1024: raise HTTPException(400,"ছবি ৫ MB-এর কম হতে হবে")
    if not data: raise HTTPException(400,"ছবি খালি")
    answer, error = diagnose_crop_image(crop, area[:80], symptoms[:500], data, photo.content_type)
    if error:
        message = html.escape(error)
        body=f"<h1>AI বিশ্লেষণ আপাতত পাওয়া যাচ্ছে না</h1><div class='card'><p>{message}</p><p>কোনো পেইড সেবা বা চার্জ চালু করা হয়নি।</p></div><a href='/agri/diagnose'>আবার চেষ্টা করুন</a>"
    else:
        safe_answer = html.escape(answer).replace("\\n", "<br>")
        body=f"<h1>সম্ভাব্য রোগ/পোকা বিশ্লেষণ</h1><div class='card'><p>{safe_answer}</p></div><p class='fine'>এটি ছবিভিত্তিক AI-এর সম্ভাব্য মূল্যায়ন, নিশ্চিত রোগনির্ণয় নয়। স্প্রে বা চিকিৎসার আগে স্থানীয় কৃষি কর্মকর্তা এবং নিবন্ধিত পণ্যের লেবেল অনুসরণ করুন।</p><a href='/agri/diagnose'>আরেকটি ছবি বিশ্লেষণ করুন</a>"
    return shell("AI বিশ্লেষণ", body)
