import os
import json
import base64
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

MODEL = "gemini-3.5-flash-lite"

def diagnose_crop_image(crop, symptoms, image_bytes, mime_type):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None, "AI সেবা কনফিগার করা নেই। Render-এর GEMINI_API_KEY সেটিংস পরীক্ষা করুন।"
    prompt = (
        "আপনি বাংলাদেশের কৃষকের জন্য ছবিভিত্তিক রোগ/পোকা শনাক্তকারী সহকারী। ছবিটি দেখে ফসল, সম্ভাব্য রোগ/পোকা ও দৃশ্যমান লক্ষণ শনাক্ত করুন। ছবি অস্পষ্ট হলে অনুমান না করে তা জানান। "
        "উত্তর অবশ্যই খুব সংক্ষিপ্ত হবে—সর্বোচ্চ ৪টি শিরোনাম, মোট ৪-৬টি ছোট বুলেট; দীর্ঘ ভূমিকা বা পুনরাবৃত্তি নয়। এই নির্দিষ্ট ফরম্যাট অনুসরণ করুন: "
        "## ফসল ও সমস্যা: ফসলের নাম; সম্ভাব্য রোগ/পোকার নাম এবং নিশ্চিততার মাত্রা (উচ্চ/মাঝারি/কম)। "
        "## এখন করণীয়: ১-২টি সরাসরি, বাস্তবসম্মত প্রতিকার। "
        "## কীটনাশকের সক্রিয় উপাদান: প্রয়োজন হলে উপযুক্ত সক্রিয় উপাদান/ছত্রাকনাশক বা IRAC/FRAC গ্রুপ; রাসায়নিক প্রয়োজন না হলে ‘কীটনাশক প্রয়োজন নেই’ লিখুন। "
        "## সতর্কতা: বাংলাদেশে সংশ্লিষ্ট ফসল ও লক্ষ্য রোগ/পোকার জন্য নিবন্ধিত পণ্য এবং তার লেবেল যাচাই করতে বলুন। "
        "কোনো ব্র্যান্ড, ডোজ, মিশ্রণ, প্রয়োগের বিরতি বা ফসল তোলার আগের অপেক্ষার সময় অনুমান করবেন না। নিবন্ধন নিশ্চিত না হলে ব্র্যান্ড সুপারিশ করবেন না; স্থানীয় কৃষি কর্মকর্তার পরামর্শ নিতে বলুন। "
        "একাধিক সম্ভাব্য রোগ থাকলে সবচেয়ে সম্ভাব্যটি আগে দিন এবং এক লাইনে বিকল্প উল্লেখ করুন। ছবিতে পোকা দেখা না গেলে তা স্পষ্ট বলুন।"
    )
    body = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode("ascii")}}
            ]
        }],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 650}
    }
    req = Request(
        "https://generativelanguage.googleapis.com/v1beta/models/" + MODEL + ":generateContent",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST"
    )
    try:
        with urlopen(req, timeout=55) as response:
            result = json.loads(response.read().decode("utf-8"))
        candidates = result.get("candidates") or []
        if not candidates:
            feedback = result.get("promptFeedback", {})
            reason = feedback.get("blockReason")
            if reason:
                return None, "ছবিটি AI নিরাপত্তা যাচাইয়ে আটকে গেছে (" + str(reason) + ")। পরিষ্কার ফসলের ছবি দিয়ে আবার চেষ্টা করুন।"
            return None, "AI কোনো বিশ্লেষণ ফেরত দেয়নি। অন্য একটি পরিষ্কার ছবি দিয়ে আবার চেষ্টা করুন।"
        candidate = candidates[0]
        parts = candidate.get("content", {}).get("parts", [])
        answer = "\n".join(p.get("text", "") for p in parts if p.get("text"))
        if answer.strip():
            return answer, None
        finish = candidate.get("finishReason", "অজানা")
        return None, "AI উত্তর তৈরি করতে পারেনি (কারণ: " + str(finish) + ")। পরিষ্কার ও কাছ থেকে তোলা ছবি দিয়ে আবার চেষ্টা করুন।"
    except HTTPError as error:
        if error.code == 429:
            return None, "ফ্রি AI ব্যবহারের সীমা শেষ হয়েছে। কোনো পেইড সেবা বা চার্জ চালু করা হয়নি। পরে আবার চেষ্টা করুন।"
        if error.code in (400, 401, 403, 404):
            try:
                details = json.loads(error.read().decode("utf-8"))
                message = details.get("error", {}).get("message", "")
            except Exception:
                message = ""
            if error.code in (401, 403):
                return None, "Gemini API Key গ্রহণ করা হয়নি। Render-এর GEMINI_API_KEY সেটিংস পরীক্ষা করুন।"
            if error.code == 404:
                return None, "AI মডেলটি পাওয়া যাচ্ছে না। সার্ভারের মডেল সেটিংস পরীক্ষা করতে হবে."
            return None, "ছবি বা অনুরোধটি AI গ্রহণ করেনি। JPG/PNG/WebP ছবি দিয়ে আবার চেষ্টা করুন।"
        return None, "AI সার্ভারে সমস্যা হয়েছে (HTTP " + str(error.code) + ")। পরে আবার চেষ্টা করুন।"
    except (URLError, TimeoutError):
        return None, "AI সার্ভারের সঙ্গে সংযোগ হচ্ছে না বা সময় শেষ হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করুন।"
    except (ValueError, KeyError, IndexError, TypeError):
        return None, "AI-এর উত্তর পড়তে সমস্যা হয়েছে। আবার চেষ্টা করুন।"
    except Exception:
        return None, "AI বিশ্লেষণে অপ্রত্যাশিত সমস্যা হয়েছে। পরে আবার চেষ্টা করুন।"
