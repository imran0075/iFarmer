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
        "আপনি বাংলাদেশের কৃষকের জন্য সহজ ভাষায় সংক্ষিপ্ত কৃষি সহায়তা দেবেন। "
        "ফসল: " + crop + "। জেলা: " + area + "। লক্ষণ: " + (symptoms or "উল্লেখ নেই") + "। "
        "শিরোনামগুলো এই ক্রমে দিন: ## ১. সনাক্তকরণ, ## ২. রোগ নির্ণয়, ## ৩. পোকা, ## ৪. সমাধান, ## ৫. প্রতিকার ও প্রতিরোধ, ## ৬. ফলাফল, ## ৭. সতর্কতা। "
        "প্রতিটি অংশে সর্বোচ্চ 1-3টি ছোট বুলেট দিন। প্রতিটি বুলেট এক বাক্য, সরাসরি করণীয়। সমাধান অংশে সর্বোচ্চ ৩টি ধাপ দিন: প্রথমে আক্রান্ত অংশ/গাছ আলাদা বা অপসারণের মতো নিরাপদ ব্যবস্থা (যদি উপযুক্ত হয়), তারপর পরিচর্যা/ব্যবস্থাপনা, শেষে প্রয়োজন হলে অনুমোদিত পণ্য যাচাই। "
        "একই তথ্য বা উপদেশ একাধিক অংশে পুনরায় লিখবেন না। সমাধান অংশে শুধু এখন কী করবেন; প্রতিরোধ অংশে শুধু ভবিষ্যতে কীভাবে ঠেকাবেন; ফলাফল অংশে শুধু কী উন্নতি আশা করা যায় এবং কখন আবার পরীক্ষা করবেন—এই তথ্য রাখুন। "
        "রোগ নির্ণয় অংশে সম্ভাব্য রোগ ও সম্ভাব্যতা (উচ্চ/মাঝারি/কম) বলুন; নিশ্চিত না হলে সম্ভাব্য বলুন। পোকা অংশে পোকা দেখা গেলে নাম/লক্ষণ বলুন, না দেখা গেলে ‘ছবিতে পোকা স্পষ্ট দেখা যায়নি’ বলুন। "
        "কৃষকের কাছে সহজ শব্দ ব্যবহার করুন; জটিল বৈজ্ঞানিক শব্দ হলে সঙ্গে সহজ ব্যাখ্যা দিন। দীর্ঘ ভূমিকা, অপ্রয়োজনীয় ব্যাখ্যা, পুনরাবৃত্তি ও সাধারণ উপদেশ বাদ দিন। "
        "কোনো ব্র্যান্ড, ডোজ, প্রয়োগের বিরতি বা ফসল তোলার আগের অপেক্ষার সময় অনুমান করবেন না। পণ্য/সক্রিয় উপাদান কেবল নির্ভরযোগ্য হলে উল্লেখ করুন; বাংলাদেশে নিবন্ধন নিশ্চিত না হলে স্থানীয় কৃষি কর্মকর্তা/অনুমোদিত ডিলারের কাছে যাচাই করতে বলুন। "
        "ছবি অস্পষ্ট হলে তা বলুন এবং আরও পরিষ্কার ছবি বা স্থানীয় কৃষি কর্মকর্তার সাহায্য নিতে বলুন।"
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
