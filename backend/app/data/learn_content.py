"""Health-literacy content (general education, not medical advice): flashcards, slide decks, quiz, wellness programs."""

FLASHCARDS = [
    {"id": "fc1", "category": "Vitals", "q": "What is a typical target blood pressure for most adults?", "a": "Below 120/80 mmHg. Readings of 130/80 or higher are in ranges clinicians usually follow up on."},
    {"id": "fc2", "category": "Vitals", "q": "How is BMI calculated?", "a": "Weight in kg divided by height in metres squared. 18.5–24.9 is the usual target range for adults."},
    {"id": "fc3", "category": "Vitals", "q": "What is a normal fasting blood sugar range?", "a": "70–99 mg/dL. 100–125 is above target; 126 or more is in the range clinicians follow up."},
    {"id": "fc4", "category": "Labs", "q": "What does 'out of reference range' mean on a lab report?", "a": "The value is outside the range the lab considers typical for most healthy people. It is a prompt for a conversation, not a diagnosis."},
    {"id": "fc5", "category": "Labs", "q": "Why are trends across lab reports useful?", "a": "A value slowly rising or falling over months can matter more than a single reading. Trends show direction."},
    {"id": "fc6", "category": "Sleep", "q": "How much sleep do most adults need?", "a": "Around 7–9 hours per night. Regularly sleeping under 6 hours is worth discussing with a clinician."},
    {"id": "fc7", "category": "Sleep", "q": "Name two habits that support better sleep.", "a": "A consistent sleep/wake time and avoiding screens and caffeine late in the evening."},
    {"id": "fc8", "category": "Medicines", "q": "Why is adherence important?", "a": "Medicines work best when taken as prescribed. Missing doses can reduce benefit and mask whether a treatment is working."},
    {"id": "fc9", "category": "Medicines", "q": "What should you do before stopping a prescribed medicine?", "a": "Speak to your prescriber or pharmacist first; some medicines must be tapered."},
    {"id": "fc10", "category": "Emergency", "q": "Which symptoms need emergency help immediately?", "a": "Chest pain, trouble breathing, signs of stroke (face drooping, arm weakness, speech difficulty), severe bleeding, or thoughts of self-harm. In India call 112."},
    {"id": "fc11", "category": "Emergency", "q": "What belongs on an emergency health card?", "a": "Blood group, allergies, chronic conditions, current medicines and an emergency contact."},
    {"id": "fc12", "category": "Mental health", "q": "What is one quick grounding technique for anxiety?", "a": "5-4-3-2-1: name 5 things you see, 4 you feel, 3 you hear, 2 you smell, 1 you taste."},
    {"id": "fc13", "category": "Mental health", "q": "When should low mood be discussed with a professional?", "a": "If it lasts more than two weeks, affects sleep, appetite or daily life, or you feel hopeless."},
    {"id": "fc14", "category": "Nutrition", "q": "What does a balanced plate look like?", "a": "About half vegetables and fruit, a quarter whole grains, a quarter protein, with water as the main drink."},
    {"id": "fc15", "category": "Nutrition", "q": "How much water is a common daily target?", "a": "Roughly 6–8 glasses, more in hot weather or with exercise. Needs vary by person."},
    {"id": "fc16", "category": "Activity", "q": "What activity level do health bodies commonly recommend?", "a": "About 150 minutes of moderate activity per week, plus muscle-strengthening twice weekly."},
    {"id": "fc17", "category": "Consultation", "q": "How can you get more from a doctor visit?", "a": "Bring a symptom timeline, your medicine list, recent reports and 2–3 prioritised questions."},
    {"id": "fc18", "category": "Consultation", "q": "Why is a second opinion sometimes sought?", "a": "To confirm a plan for a significant decision or when opinions differ. EchoCare helps you compare opinions side by side."},
]

SLIDE_DECKS = [
    {"id": "deck-heart", "title": "Heart Health Basics", "tag": "Cardiology", "slides": [
        {"title": "Why heart health matters", "body": "Cardiovascular conditions are a leading cause of illness worldwide, and many risk factors are measurable and modifiable.", "icon": "heart"},
        {"title": "Know your numbers", "body": "Blood pressure, fasting sugar, cholesterol and BMI give an early picture. Track them in Vitals and Lab Trends.", "icon": "activity"},
        {"title": "Move every day", "body": "Aim for about 150 minutes of moderate activity weekly. Brisk walking counts.", "icon": "footprints"},
        {"title": "Eat for your heart", "body": "More vegetables, fruit, whole grains and pulses; less salt, sugary drinks and heavily processed food.", "icon": "apple"},
        {"title": "When to seek help", "body": "Chest pain, breathlessness at rest, fainting or palpitations with dizziness need prompt medical attention. Call 112 in an emergency.", "icon": "siren"}]},
    {"id": "deck-sleep", "title": "Sleep & Stress Reset", "tag": "Wellness", "slides": [
        {"title": "Sleep is medicine", "body": "Consistent, sufficient sleep supports mood, immunity, blood pressure and memory.", "icon": "moon"},
        {"title": "A simple evening routine", "body": "Dim lights, put screens away 60 minutes before bed, keep the room cool and dark.", "icon": "bed"},
        {"title": "Caffeine & timing", "body": "Caffeine can linger 6+ hours. Try cutting it after early afternoon.", "icon": "coffee"},
        {"title": "Breathe it out", "body": "4-7-8 breathing or box breathing for 3 minutes can settle a racing mind.", "icon": "wind"},
        {"title": "Track the pattern", "body": "Log sleep and stress in the Daily Tracker; EchoCare flags short-sleep patterns worth discussing.", "icon": "chart"}]},
    {"id": "deck-visit", "title": "Preparing for a Doctor Visit", "tag": "Consultation", "slides": [
        {"title": "Build your timeline", "body": "Note when symptoms started, how they change, and what helps or worsens them.", "icon": "clock"},
        {"title": "Gather your records", "body": "Bring recent lab reports, current medicines and previous specialist opinions.", "icon": "folder"},
        {"title": "Prioritise questions", "body": "Write your top three questions. Ask about next steps, alternatives and warning signs.", "icon": "help"},
        {"title": "Use the PDF summary", "body": "Generate the Consultation Report in EchoCare and share it with your clinician.", "icon": "file"}]},
    {"id": "deck-diabetes", "title": "Blood Sugar Awareness", "tag": "General Medicine", "slides": [
        {"title": "What the numbers mean", "body": "Fasting 70–99 mg/dL is the usual target; 100–125 is above target; 126+ is followed up clinically.", "icon": "droplet"},
        {"title": "Food & rhythm", "body": "Regular meals, fibre-rich carbohydrates and a short walk after eating help many people.", "icon": "apple"},
        {"title": "Monitor consistently", "body": "Record fasting and post-meal readings on the same schedule so trends are meaningful.", "icon": "chart"},
        {"title": "Talk to your clinician", "body": "Any reading in the alert range, or recurring symptoms such as excessive thirst, should be discussed.", "icon": "stethoscope"}]},
]

WELLNESS_PROGRAMS = [
    {"id": "w-breath", "title": "Box Breathing", "minutes": 3, "category": "Mindfulness", "steps": ["Inhale through the nose for 4 seconds", "Hold for 4 seconds", "Exhale slowly for 4 seconds", "Hold empty for 4 seconds", "Repeat for 3 minutes"]},
    {"id": "w-desk", "title": "Desk Stretch Break", "minutes": 5, "category": "Movement", "steps": ["Roll shoulders back 10 times", "Neck tilts, 20 seconds each side", "Seated spinal twist, 20 seconds each side", "Wrist circles and finger stretches", "Stand and reach overhead for 30 seconds"]},
    {"id": "w-walk", "title": "10-Minute Walk", "minutes": 10, "category": "Movement", "steps": ["Pick an easy route near you", "Walk at a pace where you can talk but not sing", "Relax shoulders and swing arms", "Finish with 5 slow breaths"]},
    {"id": "w-ground", "title": "5-4-3-2-1 Grounding", "minutes": 4, "category": "Mindfulness", "steps": ["Name 5 things you can see", "Name 4 things you can feel", "Name 3 things you can hear", "Name 2 things you can smell", "Name 1 thing you can taste"]},
    {"id": "w-wind", "title": "Evening Wind-down", "minutes": 15, "category": "Sleep", "steps": ["Dim the lights and silence notifications", "Gentle stretching for 5 minutes", "Write down tomorrow's top 3 tasks", "4-7-8 breathing, 4 rounds"]},
    {"id": "w-hydrate", "title": "Hydration Reset", "minutes": 2, "category": "Nutrition", "steps": ["Drink a glass of water now", "Keep a bottle within reach", "Add a glass with each meal"]},
]

QUIZ = [
    {"id": "q1", "q": "A blood pressure of 150/95 mmHg falls in which range?", "options": ["In target range", "Elevated", "Stage 2 range", "Below usual"], "answer": 2, "why": "150/95 is at or above 140/90, the Stage 2 range. This is a discussion point for a clinician, not a diagnosis."},
    {"id": "q2", "q": "Which is the best first step if you notice a persistent symptom for weeks?", "options": ["Ignore it", "Log it and discuss it with a clinician", "Self-medicate", "Search forums"], "answer": 1, "why": "Recording a timeline helps clinicians; self-medicating can mask problems."},
    {"id": "q3", "q": "What does EchoCare's evidence-sufficiency gate require before showing an insight?", "options": ["One mention", "Two mentions from two different sources", "A doctor's approval", "A lab report"], "answer": 1, "why": "At least 2 occurrences across at least 2 distinct source types, so one-off notes never produce an insight."},
    {"id": "q4", "q": "Which is an emergency warning sign?", "options": ["Mild tiredness", "Chest pain with trouble breathing", "Dry skin", "A runny nose"], "answer": 1, "why": "Chest pain with breathlessness needs emergency care. Call 112 in India."},
    {"id": "q5", "q": "What BMI range is the usual adult target?", "options": ["15–18", "18.5–24.9", "25–30", "30–35"], "answer": 1, "why": "18.5–24.9 kg/m² is the WHO adult target range."},
]
