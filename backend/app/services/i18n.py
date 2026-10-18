"""Backend strings used by the agent (UI strings live in the React app)."""
STRINGS = {
    "followup_intro": {"en": "To understand this better, could you tell me:",
                       "ta": "இதைச் சிறப்பாகப் புரிந்துகொள்ள, தயவுசெய்து சொல்லுங்கள்:",
                       "hi": "इसे बेहतर समझने के लिए कृपया बताइए:"},
    "q_duration": {"en": "How long has this been going on?", "ta": "இது எவ்வளவு காலமாக இருக்கிறது?", "hi": "यह कब से हो रहा है?"},
    "q_severity": {"en": "How severe is it, from 1 (mild) to 10 (worst)?",
                   "ta": "இது எவ்வளவு தீவிரம்? 1 (லேசானது) முதல் 10 (மிக மோசம்) வரை?",
                   "hi": "यह कितना गंभीर है, 1 (हल्का) से 10 (सबसे ज़्यादा) तक?"},
    "q_trigger": {"en": "Does anything trigger it or make it better or worse (food, activity, time of day)?",
                  "ta": "ஏதாவது இதைத் தூண்டுகிறதா அல்லது கூட்டுகிறதா/குறைக்கிறதா (உணவு, செயல்பாடு, நேரம்)?",
                  "hi": "क्या कुछ इसे बढ़ाता या घटाता है (खाना, गतिविधि, दिन का समय)?"},
    "no_llm": {"en": "Echo can't generate a reply right now because the Gemini API key isn't configured or couldn't be reached. Your message is saved.",
               "ta": "Gemini API விசை அமைக்கப்படாததால் எக்கோவால் இப்போது பதிலளிக்க முடியவில்லை. உங்கள் செய்தி சேமிக்கப்பட்டது.",
               "hi": "Gemini API कुंजी कॉन्फ़िगर न होने से इको अभी उत्तर नहीं दे सकता। आपका संदेश सहेज लिया गया है।"},
}


def t(key: str, lang: str = "en") -> str:
    e = STRINGS.get(key, {})
    return e.get(lang) or e.get("en") or key
