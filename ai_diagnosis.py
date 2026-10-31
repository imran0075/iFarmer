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
        "আপনি একজন সতর্ক কৃষি সহায়ক। ছবিটি দেখে বাংলাদেশের কৃষকের জন্য সহজ, ছোট বাক্যে বাংলায় ফলাফল দিন। "
        "ফসল: " + crop + "। জেলা: " + area + "। ব্যবহারকারীর লক্ষণ: " + (symptoms or "উল্লেখ নেই") + "। "
        "উত্তর অবশ্যই নিচের নির্দিষ্ট শিরোনামগুলো এই ক্রমে আলাদা আলাদা Markdown অংশে লিখবেন; প্রতিটি শিরোনামের নিচে ২-৪টি ছোট বুলেট দিন। "
        "## ১. সনাক্তকরণ — ছবিতে কী দেখা যাচ্ছে, ফসলের কোন অংশ আক্রান্ত। "
        "## ২. রোগ নির্ণয় — সম্ভাব্য রোগ/সমস্যার নাম, সম্ভাব্যতার মাত্রা (উচ্চ/মাঝারি/কম), লক্ষণ ও কারণ। নিশ্চিত না হলে স্পষ্টভাবে সম্ভাব্য বলুন। "
        "## ৩. পোকা — পোকা দেখা গেলে নাম/ধরন ও লক্ষণ; পোকা না দেখা গেলে লিখুন ‘ছবিতে পোকা স্পষ্ট দেখা যায়নি’। "
        "## ৪. সমাধান — কৃষক এখন কী করবেন, ধাপে ধাপে ১, ২, ৩ করে। প্রয়োজনে সম্ভাব্য সক্রিয় উপাদান/পণ্যের ধরন উল্লেখ করুন; ব্র্যান্ড বা ডোজ অনুমান করবেন না। "
        "## ৫. প্রতিকার ও প্রতিরোধ — ভবিষ্যতে কীভাবে ঠেকাবেন, পর্যবেক্ষণ ও পরিচর্যা। "
        "## ৬. ফলাফল — করণীয় মানলে কী উন্নতি আশা করা যায় এবং কতদিন পর ক্ষেত পুনরায় দেখবেন; নির্দিষ্ট সময় নিশ্চিত না হলে আনুমানিক বলুন। "
        "## ৭. সতর্কতা — নিবন্ধিত পণ্যের লেবেল, সুরক্ষা সরঞ্জাম ও স্থানীয় কৃষি কর্মকর্তার পরামর্শ মানতে বলুন। "
        "প্রতিটি অংশে সহজ ভাষা, সংক্ষিপ্ত বাক্য, কৃষকের কাজে লাগবে এমন নির্দেশ দিন। একই কথা পুনরাবৃত্তি করবেন না। "
        "বাংলাদেশে ওই ফসল/সমস্যার জন্য পণ্য নিবন্ধিত কি না নিশ্চিত না হলে পণ্য বা ডোজ নিশ্চিতভাবে বলবেন না। "
        "ডোজ, প্রয়োগের বিরতি ও ফসল তোলার আগের অপেক্ষার সময় অনুমান করবেন না। ছবি অস্পষ্ট বা যথেষ্ট না হলে তা বলুন এবং আরও পরিষ্কার ছবি/কৃষি কর্মকর্তার সহায়তা নিতে বলুন।"
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
