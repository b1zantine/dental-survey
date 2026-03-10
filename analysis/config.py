"""Static configuration for the periodontal survey analysis."""

from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent

THEME = {
    "navy": "#16324F",
    "teal": "#2A9D8F",
    "gold": "#E9C46A",
    "coral": "#E76F51",
    "slate": "#5B6770",
    "ivory": "#F7F4EA",
    "mist": "#DDE7EE",
    "ink": "#10212F",
}

RAW_TO_SNAKE = {
    "Timestamp": "timestamp",
    "Time Taken to complete the survey (minutes)": "duration_minutes",
    "Age Range": "age_range",
    "Gender": "gender",
    "Professional Experience": "professional_experience",
    "Locality / Area": "locality",
    "Work Mode": "work_mode",
    "Designation": "designation",
    "Previous Treatment?": "previous_treatment",
    "Treatments": "treatments",
    "Treatments_other": "treatments_other",
    "Knowledge Score": "knowledge_score_raw",
    "Knowledge Total": "knowledge_total_raw",
    "K1": "k1",
    "K2": "k2",
    "K3": "k3",
    "K4": "k4",
    "K5": "k5",
    "K6": "k6",
    "K7": "k7",
    "K8": "k8",
    "K9": "k9",
    "K10": "k10",
    "A1": "a1",
    "A2": "a2",
    "A3": "a3",
    "A4": "a4",
    "A5": "a5",
    "A6": "a6",
    "A7": "a7",
    "A8": "a8",
    "A9": "a9",
    "A10": "a10",
    "P1": "p1",
    "P2": "p2",
    "P3": "p3",
    "P4": "p4",
    "P5": "p5",
    "P6": "p6",
    "P7": "p7",
    "P8": "p8",
    "P9": "p9",
    "P10": "p10",
}

AGE_ORDER = ["20-30 years", "30-40 years", "40-50 years", "50-60 years"]
GENDER_ORDER = ["Male", "Female", "Prefer not to say", "Other"]
EXPERIENCE_ORDER = ["0-3 years", "3-6 years", "6-10 years", "10-15 years", "15+ years"]
WORK_MODE_ORDER = ["Full time", "Hybrid", "Work from home (Remote)"]
PREVIOUS_TREATMENT_ORDER = ["No", "Yes"]
SAMPLE_SOURCE_ORDER = ["observed", "generated"]
ATTITUDE_RESPONSE_ORDER = ["Strongly Disagree", "Disagree", "Agree", "Strongly Agree"]
ATTITUDE_VALUE_MAP = {
    "Strongly Disagree": 1,
    "Disagree": 2,
    "Agree": 3,
    "Strongly Agree": 4,
}
ATTITUDE_REVERSE_ITEMS = {"a5", "a8"}

LOCALITY_NORMALIZATION = {
    "bangalore": "Bangalore",
    "bengaluru": "Bangalore",
    "banglore": "Bangalore",
    "bangalore urban": "Bangalore",
    "bangalore rural": "Bangalore",
    "jp nagar": "JP Nagar",
    "jp nagara": "JP Nagar",
    "j p nagar": "JP Nagar",
    "jpnagar": "JP Nagar",
    "white field": "Whitefield",
}
MAJOR_LOCALITY_MIN_COUNT = 5

STANDARD_TREATMENT_ORDER = [
    "Cleaning (Scaling)",
    "Deep cleaning (Root planing)",
    "Flap surgeries",
]

KNOWLEDGE_ITEMS = [
    {
        "id": "k1",
        "short": "Plaque",
        "question": "What is dental plaque?",
        "options": [
            "Hard mineral deposit on the teeth",
            "A soft film of bacteria and food debris on the teeth",
            "Stains caused by coffee or tea",
            "Protective layer on the enamel",
        ],
        "correct_code": "1",
    },
    {
        "id": "k2",
        "short": "Calculus",
        "question": "What is dental calculus (tartar)?",
        "options": [
            "Hard mineral deposit on the teeth",
            "Stains caused by coffee or tea",
            "A soft film of bacteria and food debris",
            "Protective layer on the enamel",
        ],
        "correct_code": "0",
    },
    {
        "id": "k3",
        "short": "Early sign",
        "question": "Which of the following is an early sign of gum infection?",
        "options": [
            "White spots on the teeth",
            "Dry mouth",
            "Bleeding gums while brushing",
            "Jaw pain",
        ],
        "correct_code": "2",
    },
    {
        "id": "k4",
        "short": "Cause",
        "question": "What is the primary cause of early gum disease?",
        "options": [
            "Dental plaque accumulation",
            "Poor brushing technique",
            "Tooth decay",
            "Lack of calcium",
        ],
        "correct_code": "0",
    },
    {
        "id": "k5",
        "short": "Bad breath",
        "question": "What is one of the main causes of bad breath?",
        "options": [
            "Frequent brushing",
            "Chewing gum",
            "Cold beverages",
            "Gum disease",
        ],
        "correct_code": "3",
    },
    {
        "id": "k6",
        "short": "Diet",
        "question": "Which dietary choice contributes most to poor gum health?",
        "options": [
            "Processed sugary foods and drinks",
            "Leafy greens",
            "Dairy products",
            "Whole grains",
        ],
        "correct_code": "0",
    },
    {
        "id": "k7",
        "short": "Vitamin",
        "question": "Which vitamin helps to keep your gums healthy?",
        "options": ["Vitamin A", "Vitamin B", "Vitamin C", "Vitamin D"],
        "correct_code": "2",
    },
    {
        "id": "k8",
        "short": "General health",
        "question": "How is gum disease linked to general health?",
        "options": [
            "It boosts immunity",
            "It can contribute to heart disease and diabetes",
            "It lowers blood sugar levels",
            "It only affects the mouth and teeth",
        ],
        "correct_code": "1",
    },
    {
        "id": "k9",
        "short": "Stress",
        "question": "What is a common oral health consequence of prolonged stress?",
        "options": [
            "Increased salivary flow",
            "Improved oral hygiene habits",
            "Strengthening of tooth enamel",
            "Development of gum disease due to inflammation",
        ],
        "correct_code": "3",
    },
    {
        "id": "k10",
        "short": "Specialty",
        "question": "Which dental specialty focuses on prevention and treatment of gum disease?",
        "options": ["Orthodontics", "Prosthodontics", "Periodontics", "Endodontics"],
        "correct_code": "2",
    },
]

ATTITUDE_ITEMS = [
    {"id": "a1", "statement": "Neglecting oral hygiene develops gum disease."},
    {"id": "a2", "statement": "Bleeding gums should not be ignored."},
    {"id": "a3", "statement": "Attending workplace awareness programs will improve gum health."},
    {"id": "a4", "statement": "Maintaining oral hygiene is equally important as maintaining physical fitness."},
    {"id": "a5", "statement": "Visiting a dentist is necessary only when I have pain or discomfort."},
    {"id": "a6", "statement": "Poor gum health can negatively affect my confidence or social interactions."},
    {"id": "a7", "statement": "Oral hygiene aids like floss or mouthwash can be used if recommended by a dentist."},
    {"id": "a8", "statement": "Oral hygiene maintenance is time consuming and difficult to follow."},
    {"id": "a9", "statement": "Workplace stress can have an impact on my gum and oral health."},
    {"id": "a10", "statement": "Investing in preventive dental care is better than spending on treatment later."},
]

PRACTICE_ITEMS = [
    {
        "id": "p1",
        "short": "Brushing frequency",
        "question": "How many times do you brush your teeth in a day?",
        "options": ["Twice a day", "Thrice a day", "Once a day", "Occasionally"],
        "score_map": {"0": 3, "1": 2, "2": 1, "3": 0},
    },
    {
        "id": "p2",
        "short": "Brushing direction",
        "question": "In what direction do you brush your teeth?",
        "options": ["Circular", "Vertical", "Horizontal", "Mixed"],
        "score_map": {"0": 3, "1": 2, "2": 0, "3": 1},
    },
    {
        "id": "p3",
        "short": "Brush softness",
        "question": "What type of toothbrush do you use?",
        "options": ["Soft", "Ultrasoft", "Medium", "Hard"],
        "score_map": {"0": 3, "1": 2, "2": 1, "3": 0},
    },
    {
        "id": "p4",
        "short": "Brushing timing",
        "question": "When do you brush your teeth?",
        "options": ["Only morning", "Only night", "Both morning and night", "After lunch and breakfast"],
        "score_map": {"0": 1, "1": 1, "2": 3, "3": 2},
    },
    {
        "id": "p5",
        "short": "Brushing duration",
        "question": "For how long do you brush your teeth?",
        "options": ["Less than 1 minute", "1-3 minutes", "3-5 minutes", "More than 5 minutes"],
        "score_map": {"0": 0, "1": 3, "2": 2, "3": 1},
    },
    {
        "id": "p6",
        "short": "Post-meal rinse",
        "question": "Do you rinse your mouth with water after each meal?",
        "options": ["Yes, everytime", "Occasionally", "Never", "Only after dinner"],
        "score_map": {"0": 3, "1": 2, "2": 0, "3": 1},
    },
    {
        "id": "p7",
        "short": "Cleaning aids",
        "question": "Do you use any aids for cleaning your teeth, other than toothbrush and toothpaste?",
        "options": ["Tongue scraper", "Dental floss", "Toothpick", "Both scraper and floss"],
        "score_map": {"0": 1, "1": 2, "2": 0, "3": 3},
    },
    {
        "id": "p8",
        "short": "Brush replacement",
        "question": "How often do you change your toothbrush?",
        "options": ["Once in 3 months", "Once in 6 months", "Once in a year", "When bristles wear out"],
        "score_map": {"0": 3, "1": 1, "2": 0, "3": 2},
    },
    {
        "id": "p9",
        "short": "Dental visit",
        "question": "When did you last visit your dentist?",
        "options": ["Never", "0-6 months ago", "7-12 months ago", "More than a year"],
        "score_map": {"0": 0, "1": 3, "2": 2, "3": 1},
    },
    {
        "id": "p10",
        "short": "Risk habits",
        "question": "Do you consume gutka/pan/alcohol/cigarettes?",
        "options": ["Yes", "No", "Sometimes", "Have quit"],
        "score_map": {"0": 0, "1": 3, "2": 1, "3": 2},
    },
]

PRACTICE_SCORE_LABELS = {
    0: "Least healthy",
    1: "Needs work",
    2: "Reasonable",
    3: "Best practice",
}

GROUP_VARS = [
    {"column": "age_range", "label": "Age range", "order": AGE_ORDER},
    {"column": "gender", "label": "Gender", "order": GENDER_ORDER},
    {"column": "professional_experience", "label": "Professional experience", "order": EXPERIENCE_ORDER},
    {"column": "work_mode", "label": "Work mode", "order": WORK_MODE_ORDER},
    {"column": "previous_treatment", "label": "Previous treatment", "order": PREVIOUS_TREATMENT_ORDER},
    {"column": "sample_source", "label": "Sample source", "order": SAMPLE_SOURCE_ORDER},
]

KAP_SCORE_COLUMNS = ["knowledge_score", "attitude_score", "practice_index"]
