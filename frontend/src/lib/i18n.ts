export type Lang = 'en' | 'ta' | 'hi'
export const LANGS: { code: Lang; label: string }[] = [{ code: 'en', label: 'English' }, { code: 'ta', label: 'தமிழ்' }, { code: 'hi', label: 'हिन्दी' }]
type D = Record<string, Record<Lang, string>>
const S = (en: string, ta: string, hi: string) => ({ en, ta, hi })
export const STRINGS: D = {
  dashboard: S('Dashboard', 'டாஷ்போர்டு', 'डैशबोर्ड'), story: S('My Story', 'என் கதை', 'मेरी कहानी'), survey: S('Health Survey', 'ஆரோக்கிய கணக்கெடுப்பு', 'स्वास्थ्य सर्वेक्षण'),
  tracker: S('Daily Tracker', 'தினசரி கண்காணிப்பு', 'दैनिक ट्रैकर'), vitals: S('Vitals', 'உடல்நிலை', 'वाइटल्स'), reports: S('Medical Reports', 'மருத்துவ அறிக்கைகள்', 'मेडिकल रिपोर्ट'),
  labs: S('Lab Trends', 'ஆய்வக போக்குகள்', 'लैब ट्रेंड्स'), medicines: S('Medicines', 'மருந்துகள்', 'दवाइयाँ'), timeline: S('Health Timeline', 'ஆரோக்கிய காலவரிசை', 'स्वास्थ्य टाइमलाइन'),
  insights: S('AI Insights', 'AI நுண்ணறிவுகள்', 'AI इनसाइट्स'), echo: S('Echo Companion', 'எக்கோ துணை', 'इको साथी'), guard: S('Diagnostic Guard', 'நோயறிதல் பாதுகாப்பு', 'डायग्नोस्टिक गार्ड'),
  doctors: S('Find Doctors', 'மருத்துவரைத் தேடு', 'डॉक्टर खोजें'), appointments: S('Appointments', 'சந்திப்புகள்', 'अपॉइंटमेंट'), family: S('Family Profiles', 'குடும்ப சுயவிவரங்கள்', 'परिवार प्रोफ़ाइल'),
  emergency: S('Emergency Card', 'அவசர அட்டை', 'आपातकालीन कार्ड'), consult: S('Consultation Report', 'ஆலோசனை அறிக்கை', 'परामर्श रिपोर्ट'), wellness: S('Wellness & Goals', 'நலன் & இலக்குகள்', 'वेलनेस और लक्ष्य'),
  learn: S('Learning Hub', 'கற்றல் மையம்', 'लर्निंग हब'), analytics: S('Analytics', 'பகுப்பாய்வு', 'एनालिटिक्स'), settings: S('Settings', 'அமைப்புகள்', 'सेटिंग्स'), admin: S('Admin Console', 'நிர்வாகம்', 'एडमिन'),
  search: S('Search your health data…', 'உங்கள் தரவைத் தேடுங்கள்…', 'अपना डेटा खोजें…'), signout: S('Sign out', 'வெளியேறு', 'साइन आउट'),
  welcome: S('Welcome back', 'மீண்டும் வருக', 'वापसी पर स्वागत है'), save: S('Save', 'சேமி', 'सहेजें'), cancel: S('Cancel', 'ரத்து', 'रद्द करें'), delete: S('Delete', 'நீக்கு', 'हटाएँ'),
  add: S('Add', 'சேர்', 'जोड़ें'), loading: S('Loading…', 'ஏற்றுகிறது…', 'लोड हो रहा है…'), not_a_doctor: S('EchoCare is not a doctor and cannot diagnose. In an emergency call 112.', 'எக்கோகேர் மருத்துவர் அல்ல; நோயறிதல் செய்யாது. அவசரத்தில் 112 ஐ அழைக்கவும்.', 'इकोकेयर डॉक्टर नहीं है और निदान नहीं करता। आपातकाल में 112 पर कॉल करें।'),
  notifications: S('Notifications', 'அறிவிப்புகள்', 'सूचनाएँ'), health_score: S('Wellness score', 'நல மதிப்பெண்', 'वेलनेस स्कोर'), ask_echo: S('Ask Echo anything…', 'எக்கோவிடம் கேளுங்கள்…', 'इको से कुछ भी पूछें…'),
  main: S('Main', 'முதன்மை', 'मुख्य'), record: S('Record', 'பதிவு', 'रिकॉर्ड'), ai: S('AI & Safety', 'AI & பாதுகாப்பு', 'AI और सुरक्षा'), care: S('Care', 'பராமரிப்பு', 'देखभाल'), more: S('More', 'மேலும்', 'और'),
  trust: S('Trust & Safety', 'நம்பிக்கை & பாதுகாப்பு', 'विश्वास और सुरक्षा'), alerts: S('Alerts', 'எச்சரிக்கைகள்', 'अलर्ट'), vault: S('Document Vault', 'ஆவணப் பெட்டகம்', 'दस्तावेज़ तिजोरी'),
  verified_report: S('Verified Report', 'சரிபார்க்கப்பட்ட அறிக்கை', 'सत्यापित रिपोर्ट'), verification: S('Verification', 'சரிபார்ப்பு', 'सत्यापन'), sharing: S('Sharing & Access', 'பகிர்வு & அணுகல்', 'साझाकरण और पहुँच'), privacy: S('Privacy & Consent', 'தனியுரிமை & ஒப்புதல்', 'गोपनीयता और सहमति'),
  theme: S('Theme', 'தீம்', 'थीम'), language: S('Language', 'மொழி', 'भाषा'), profile: S('Profile', 'சுயவிவரம்', 'प्रोफ़ाइल'),
}
export const tr = (lang: Lang, key: string) => STRINGS[key]?.[lang] || STRINGS[key]?.en || key
