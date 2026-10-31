import os
import json
import base64
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

MODEL = "gemini-3.5-flash-lite"

def diagnose_crop_image(crop, area, symptoms, image_bytes, mime_type):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None, "AI সেবা কনফিগার করা নেই। Render-এর GEMINI_API_KEY সেটিংস পরীক্ষা করুন।"
    prompt = (
        "আপনি একজন সতর্ক কৃষি সহায়ক। ছবিটি দেখে বাংলায় সহজ ভাষায় বিশ্লেষণ দিন। "
        "ফসল: " + crop + "। এলাকা: " + area + "। ব্যবহারকারীর বলা লক্ষণ: " + (symptoms or "উল্লেখ নেই") + "। "
        "উত্তরে এই শিরোনামগুলো অবশ্যই দিন: ১) ছবিতে যা দেখা যাচ্ছে ২) সম্ভাব্য রোগ/পোকা/পুষ্টিঘাটতি "
        "৩) রোগের লক্ষণ ও ছবির সঙ্গে মিল ৪) সম্ভাব্য কারণ ৫) এখনই করণীয় ৬) সম্ভাব্য কীটনাশক/ছত্রাকনাশক বিকল্প ৭) প্রতিরোধ ৮) নিশ্চিত হওয়ার উপায়। "
        "সম্ভাব্যতার মাত্রা জানান এবং ছবি অস্পষ্ট হলে তা স্পষ্ট বলুন। একাধিক সম্ভাবনা থাকলে আলাদা করুন। "
        "সমস্যার জন্য সাধারণত ব্যবহৃত সক্রিয় উপাদান বা কীটনাশক/ছত্রাকনাশকের সম্ভাব্য বিকল্প ও কেন উপযোগী তা উল্লেখ করুন। বাংলাদেশে ওই ফসল ও সমস্যার জন্য পণ্য নিবন্ধিত কি না নিশ্চিত না হলে ব্র্যান্ড বা ডোজ নিশ্চিতভাবে বলবেন না; স্থানীয় কৃষি কর্মকর্তা বা অনুমোদিত ডিলারের কাছে যাচাই করতে বলুন। ডোজ, প্রয়োগের বিরতি ও ফসল তোলার আগের অপেক্ষার সময় কেবল নির্ভরযোগ্য লেবেল-তথ্য নিশ্চিত থাকলে বলুন, অনুমান করবেন না। নিবন্ধিত পণ্যের লেবেল, সুরক্ষা সরঞ্জাম "
        "এবং স্থানীয় কৃষি কর্মকর্তার পরামর্শ মানতে বলুন।"
    )
    body = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode("ascii")}}
            ]
        }],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1800}
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
