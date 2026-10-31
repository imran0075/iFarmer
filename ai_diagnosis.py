import os
import json
import base64
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

MODEL = 'gemini-2.5-flash'

def diagnose_crop_image(crop, area, symptoms, image_bytes, mime_type):
    key = os.getenv('GEMINI_API_KEY')
    if not key:
        return None, 'AI সেবা কনফিগার করা নেই।'
    prompt = ('বাংলায় সম্ভাব্য ফসলের রোগ/পোকা/পুষ্টি সমস্যা বিশ্লেষণ করুন। '
      'ফসল: '+crop+'; এলাকা: '+area+'; লক্ষণ: '+(symptoms or 'উল্লেখ নেই')+'. '
      'ছবিতে কী দেখা যায়, সম্ভাব্য কারণ, আত্মবিশ্বাস (উচ্চ/মাঝারি/কম), বিকল্প কারণ, '
      'নিরাপদ করণীয় ও প্রতিরোধ লিখুন। অনিশ্চিত হলে তা বলুন। কোনো ব্র্যান্ড বা কীটনাশকের '
      'ডোজ বানাবেন না; নিবন্ধিত পণ্যের লেবেল ও স্থানীয় কৃষি কর্মকর্তার পরামর্শ মানতে বলুন।')
    body = {'contents':[{'parts':[{'text':prompt},{'inline_data':{'mime_type':mime_type,'data':base64.b64encode(image_bytes).decode('ascii')}}]}], 'generationConfig':{'temperature':0.2,'maxOutputTokens':1100}}
    req = Request('https://generativelanguage.googleapis.com/v1beta/models/'+MODEL+':generateContent', data=json.dumps(body).encode(), headers={'Content-Type':'application/json','x-goog-api-key':key}, method='POST')
    try:
        with urlopen(req, timeout=35) as r:
            result=json.loads(r.read().decode())
        parts=result.get('candidates',[{}])[0].get('content',{}).get('parts',[])
        answer='\n'.join(p.get('text','') for p in parts if p.get('text'))
        return (answer,None) if answer else (None,'বিশ্লেষণ পাওয়া যায়নি।')
    except HTTPError as e:
        if e.code == 429:
            return None,'ফ্রি AI ব্যবহারের সীমা শেষ হয়েছে। কোনো পেইড সেবা চালু করা হয়নি। পরে আবার চেষ্টা করুন।'
        return None,'AI সেবা সাময়িকভাবে পাওয়া যাচ্ছে না।'
    except (URLError, TimeoutError, ValueError, KeyError, IndexError):
        return None,'সংযোগ বা বিশ্লেষণে সমস্যা হয়েছে। পরে আবার চেষ্টা করুন।'
