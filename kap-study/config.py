"""Self-contained configuration for the periodontal KAP survey analysis."""

AGE_ORDER = ["20-30 years", "30-40 years", "40-50 years", "50-60 years"]
GENDER_ORDER = ["Male", "Female", "Prefer not to say", "Other"]
EXPERIENCE_ORDER = ["0-3 years", "3-6 years", "6-10 years", "10-15 years", "15+ years"]
WORK_MODE_ORDER = ["Full time", "Hybrid", "Work from home (Remote)"]
PREVIOUS_TREATMENT_ORDER = ["No", "Yes"]

ATTITUDE_VALUE_MAP = {
    "Strongly Disagree": 1,
    "Disagree": 2,
    "Agree": 3,
    "Strongly Agree": 4,
}
ATTITUDE_REVERSE_ITEMS = {"A5", "A8"}

KNOWLEDGE_ITEMS = [
    {
        "id": "K1",
        "short": "Plaque",
        "question": "What is dental plaque?",
        "options": [
            "Hard mineral deposit on the teeth",
            "A soft film of bacteria and food debris on the teeth",
            "Stains caused by coffee or tea",
            "Protective layer on the enamel",
        ],
        "correct_code": 1,
    },
    {
        "id": "K2",
        "short": "Calculus",
        "question": "What is dental calculus (tartar)?",
        "options": [
            "Hard mineral deposit on the teeth",
            "Stains caused by coffee or tea",
            "A soft film of bacteria and food debris",
            "Protective layer on the enamel",
        ],
        "correct_code": 0,
    },
    {
        "id": "K3",
        "short": "Early sign",
        "question": "Which of the following is an early sign of gum infection?",
        "options": [
            "White spots on the teeth",
            "Dry mouth",
            "Bleeding gums while brushing",
            "Jaw pain",
        ],
        "correct_code": 2,
    },
    {
        "id": "K4",
        "short": "Cause",
        "question": "What is the primary cause of early gum disease?",
        "options": [
            "Dental plaque accumulation",
            "Poor brushing technique",
            "Tooth decay",
            "Lack of calcium",
        ],
        "correct_code": 0,
    },
    {
        "id": "K5",
        "short": "Bad breath",
        "question": "What is one of the main causes of bad breath?",
        "options": [
            "Frequent brushing",
            "Chewing gum",
            "Cold beverages",
            "Gum disease",
        ],
        "correct_code": 3,
    },
    {
        "id": "K6",
        "short": "Diet",
        "question": "Which dietary choice contributes most to poor gum health?",
        "options": [
            "Processed sugary foods and drinks",
            "Leafy greens",
            "Dairy products",
            "Whole grains",
        ],
        "correct_code": 0,
    },
    {
        "id": "K7",
        "short": "Vitamin",
        "question": "Which vitamin helps to keep your gums healthy?",
        "options": ["Vitamin A", "Vitamin B", "Vitamin C", "Vitamin D"],
        "correct_code": 2,
    },
    {
        "id": "K8",
        "short": "General health",
        "question": "How is gum disease linked to general health?",
        "options": [
            "It boosts immunity",
            "It can contribute to heart disease and diabetes",
            "It lowers blood sugar levels",
            "It only affects the mouth and teeth",
        ],
        "correct_code": 1,
    },
    {
        "id": "K9",
        "short": "Stress",
        "question": "What is a common oral health consequence of prolonged stress?",
        "options": [
            "Increased salivary flow",
            "Improved oral hygiene habits",
            "Strengthening of tooth enamel",
            "Development of gum disease due to inflammation",
        ],
        "correct_code": 3,
    },
    {
        "id": "K10",
        "short": "Specialty",
        "question": "Which dental specialty focuses on prevention and treatment of gum disease?",
        "options": ["Orthodontics", "Prosthodontics", "Periodontics", "Endodontics"],
        "correct_code": 2,
    },
]

ATTITUDE_ITEMS = [
    {"id": "A1", "statement": "Neglecting oral hygiene develops gum disease."},
    {"id": "A2", "statement": "Bleeding gums should not be ignored."},
    {"id": "A3", "statement": "Attending workplace awareness programs will improve gum health."},
    {"id": "A4", "statement": "Maintaining oral hygiene is equally important as maintaining physical fitness."},
    {"id": "A5", "statement": "Visiting a dentist is necessary only when I have pain or discomfort.*"},
    {"id": "A6", "statement": "Poor gum health can negatively affect my confidence or social interactions."},
    {"id": "A7", "statement": "Oral hygiene aids like floss or mouthwash can be used if recommended by a dentist."},
    {"id": "A8", "statement": "Oral hygiene maintenance is time consuming and difficult to follow.*"},
    {"id": "A9", "statement": "Workplace stress can have an impact on my gum and oral health."},
    {"id": "A10", "statement": "Investing in preventive dental care is better than spending on treatment later."},
]

PRACTICE_ITEMS = [
    {
        "id": "P1",
        "short": "Brushing frequency",
        "question": "How many times do you brush your teeth in a day?",
        "options": ["Twice a day", "Thrice a day", "Once a day", "Occasionally"],
        "score_map": {0: 3, 1: 2, 2: 1, 3: 0},
    },
    {
        "id": "P2",
        "short": "Brushing direction",
        "question": "In what direction do you brush your teeth?",
        "options": ["Circular", "Vertical", "Horizontal", "Mixed"],
        "score_map": {0: 3, 1: 2, 2: 0, 3: 1},
    },
    {
        "id": "P3",
        "short": "Brush softness",
        "question": "What type of toothbrush do you use?",
        "options": ["Soft", "Ultrasoft", "Medium", "Hard"],
        "score_map": {0: 3, 1: 2, 2: 1, 3: 0},
    },
    {
        "id": "P4",
        "short": "Brushing timing",
        "question": "When do you brush your teeth?",
        "options": ["Only morning", "Only night", "Both morning and night", "After lunch and breakfast"],
        "score_map": {0: 1, 1: 1, 2: 3, 3: 2},
    },
    {
        "id": "P5",
        "short": "Brushing duration",
        "question": "For how long do you brush your teeth?",
        "options": ["Less than 1 minute", "1-3 minutes", "3-5 minutes", "More than 5 minutes"],
        "score_map": {0: 0, 1: 3, 2: 2, 3: 1},
    },
    {
        "id": "P6",
        "short": "Post-meal rinse",
        "question": "Do you rinse your mouth with water after each meal?",
        "options": ["Yes, everytime", "Occasionally", "Never", "Only after dinner"],
        "score_map": {0: 3, 1: 2, 2: 0, 3: 1},
    },
    {
        "id": "P7",
        "short": "Cleaning aids",
        "question": "Do you use any aids for cleaning your teeth, other than toothbrush and toothpaste?",
        "options": ["Tongue scraper", "Dental floss", "Toothpick", "Both scraper and floss"],
        "score_map": {0: 1, 1: 2, 2: 0, 3: 3},
    },
    {
        "id": "P8",
        "short": "Brush replacement",
        "question": "How often do you change your toothbrush?",
        "options": ["Once in 3 months", "Once in 6 months", "Once in a year", "When bristles wear out"],
        "score_map": {0: 3, 1: 1, 2: 0, 3: 2},
    },
    {
        "id": "P9",
        "short": "Dental visit",
        "question": "When did you last visit your dentist?",
        "options": ["Never", "0-6 months ago", "7-12 months ago", "More than a year"],
        "score_map": {0: 0, 1: 3, 2: 2, 3: 1},
    },
    {
        "id": "P10",
        "short": "Risk habits",
        "question": "Do you consume gutka/pan/alcohol/cigarettes?",
        "options": ["Yes", "No", "Sometimes", "Have quit"],
        "score_map": {0: 0, 1: 3, 2: 1, 3: 2},
    },
]

DEMOGRAPHIC_VARS = [
    {"column": "Age Range", "label": "Age Range", "order": AGE_ORDER},
    {"column": "Gender", "label": "Gender", "order": GENDER_ORDER},
    {"column": "Professional Experience", "label": "Professional Experience", "order": EXPERIENCE_ORDER},
    {"column": "Work Mode", "label": "Work Mode", "order": WORK_MODE_ORDER},
    {"column": "Previous Treatment?", "label": "Previous Treatment", "order": PREVIOUS_TREATMENT_ORDER},
]
