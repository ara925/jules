# aiden_ai_backend/knowledge_base_data.py
KNOWLEDGE_BASE = [
    {
        "id": "kb1",
        "keywords": ["services", "offer", "do", "provide", "capabilities"],
        "question_patterns": [
            "what services do you offer?",
            "what can you do?",
            "tell me about your services",
            "what do you provide?",
            "what are your capabilities?"
        ],
        "answer": "As AidenBot, I can chat with you, answer basic questions based on my knowledge base, tell you the time, and remember our conversation context a little. My services are expanding!"
    },
    {
        "id": "kb2",
        "keywords": ["contact", "support", "human", "person", "help from person"],
        "question_patterns": [
            "how can I contact support?",
            "can I talk to a human?",
            "I need help from a person",
            "connect me to a human"
        ],
        "answer": "For further assistance beyond my capabilities, please reach out to our support team via the main company website or support@example.com." # Placeholder email
    },
    {
        "id": "kb3",
        "keywords": ["pricing", "cost", "how much", "plans", "subscribe"],
        "question_patterns": [
            "what is your pricing?",
            "how much do you cost?",
            "tell me about the plans",
            "how much to subscribe?"
        ],
        "answer": "I don't have access to specific pricing information. Please check our website or contact sales."
    },
    {
        "id": "kb4",
        "keywords": ["aiden", "who is aiden"], # For questions about Aiden itself
        "question_patterns": [
            "who is aiden?",
            "what is aiden?"
        ],
        "answer": "Aiden is a project to build a helpful AI assistant. You are currently chatting with AidenBot, a part of this project."
    }
    # Add more Q&A pairs as needed
]
