import datetime

# Simple rule-based intents and responses
# Using a dictionary where keys are keywords (lowercase) and values are responses or functions
RULES = {
    "hello": "Hello there! I am Aiden. How can I assist you today?",
    "hi": "Hi! I'm Aiden. What can I do for you?",
    "help": "I can respond to simple greetings, tell you my name, or give you the current time. Try 'hello', 'what is your name?', or 'time'.",
    "what is your name?": "My name is Aiden.",
    "who are you?": "I am Aiden, a simple rule-based bot.",
    "time": lambda: f"The current time is {datetime.datetime.now().strftime('%H:%M:%S')}.",
    "date": lambda: f"Today's date is {datetime.datetime.now().strftime('%Y-%m-%d')}."
}

BOT_USER_EMAIL = "aiden@bot.ai" # For attributing messages from the bot
BOT_CONVERSATION_ID_TRIGGER = "aiden_bot_chat" # Special conversation ID to trigger bot

def get_bot_response(user_message: str) -> str | None:
    user_message_lower = user_message.lower().strip().rstrip('?').rstrip('.') # Basic normalization

    # Direct keyword match
    if user_message_lower in RULES:
        response = RULES[user_message_lower]
        if callable(response):
            return response()
        return response

    # Simple partial match for some keywords (can be expanded)
    if "name" in user_message_lower and ("your" in user_message_lower or "who" in user_message_lower):
        return RULES["what is your name?"]
    if "hello" in user_message_lower or "hi" in user_message_lower:
            return RULES["hello"] # Fallback to hello if more specific hi/hello not caught by direct match

    # Default if no rule matched
    return "I'm not sure how to respond to that. Try asking for 'help'."
