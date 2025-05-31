import datetime
import spacy

# Load a small English spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("spaCy model 'en_core_web_sm' not found. Please download it by running: python -m spacy download en_core_web_sm")
    nlp = None

# Import the knowledge base
from .knowledge_base_data import KNOWLEDGE_BASE

# Simple rule-based intents and responses
RULES = {
    "hello": "Hello there! I am Aiden. How can I assist you today?",
    "hi": "Hi! I'm Aiden. What can I do for you?",
    "help": "I can respond to simple greetings, tell you my name, or give you the current time. Try 'hello', 'what is your name?', or 'time'.",
    "what is your name?": "My name is Aiden.",
    "who are you?": "I am Aiden, a simple rule-based bot.",
    "time": lambda: f"The current time is {datetime.datetime.now().strftime('%H:%M:%S')}.",
    "date": lambda: f"Today's date is {datetime.datetime.now().strftime('%Y-%m-%d')}."
}

BOT_USER_EMAIL = "aiden@bot.ai"
BOT_CONVERSATION_ID_TRIGGER = "aiden_bot_chat"

def get_bot_response(user_message: str) -> str | None:
    user_message_cleaned = user_message.lower().strip().rstrip('?').rstrip('.')

    # Direct keyword match (priority)
    if user_message_cleaned in RULES:
        response = RULES[user_message_cleaned]
        return response() if callable(response) else response

    # spaCy NLP processing if model loaded
    if nlp:
        doc = nlp(user_message_cleaned) # Process the already cleaned message

        # Enhanced Name Query Example
        asked_for_name = False
        for token in doc:
            # Looking for "name" as a noun, often possessed by "your" or asked with "what/who"
            if token.lemma_ == "name" and token.pos_ == "NOUN":
                if any(child.dep_ == "poss" and child.lemma_ == "your" for child in token.children): # "your name"
                    asked_for_name = True
                    break
                if any(ancestor.lemma_ in ["what", "who"] for ancestor in token.ancestors): # "what is [your] name"
                    asked_for_name = True
                    break
            # "who are you", "what are you called"
            if token.lemma_ == "you" and token.head.lemma_ in ["be", "call"]:
                 if any(t.lemma_ == "who" or t.lemma_ == "what" for t in token.head.ancestors):
                    asked_for_name = True # Broader, could be "who are you"
                    # Check if "name" is involved to be more specific
                    if "what is your name?" in RULES and any(n_tok.lemma_ == "name" for n_tok in doc):
                         asked_for_name = True
                    else: # For "who are you"
                         return RULES["who are you?"]
                    break


        if asked_for_name:
            return RULES["what is your name?"]

        # Enhanced Time Query Example
        asked_for_time = False
        for token in doc:
            if token.lemma_ == "time" and token.pos_ == "NOUN":
                # More robust: check for question words or "current" related to time
                is_question_about_time = False
                if doc[0].lemma_ in ["what", "current"] or \
                   any(child.lemma_ == "current" for child in token.children) or \
                   any(ancestor.lemma_ in ["what", "tell"] and token in ancestor.subtree for ancestor in token.ancestors if ancestor.pos_ == "VERB"):
                   is_question_about_time = True

                if is_question_about_time :
                    asked_for_time = True
                    break
        if asked_for_time:
            response = RULES["time"]
            return response() if callable(response) else response

        # Fallback for simple greetings if NLP didn't catch more complex phrasing
        for token in doc:
            if token.lemma_ in ["hello", "hi", "hey"]:
                return RULES["hello"]

        # Knowledge Base Check (after specific NLP intents, before general fallback)
        # Using user_message_cleaned which is lowercased and stripped
        # No separate nlp doc needed here if just doing keyword and exact pattern match for now

        relevant_articles_by_keyword = []
        for article in KNOWLEDGE_BASE:
            if any(keyword in user_message_cleaned for keyword in article["keywords"]):
                relevant_articles_by_keyword.append(article)

        if relevant_articles_by_keyword:
            for article in relevant_articles_by_keyword:
                for pattern in article["question_patterns"]:
                    if user_message_cleaned == pattern.lower().strip().rstrip('?').rstrip('.'):
                        return article["answer"]
            # Optional: If keywords matched but no exact pattern, maybe suggest topics or return first relevant answer
            # For now, we'll let it fall through if no exact pattern matches.

        # Fallback for simple greetings if NLP didn't catch more complex phrasing (already present)
        # (This was moved up in the example, ensure it's logically placed, e.g., after KB)
        for token_doc in doc: # Assuming doc is from earlier NLP processing of user_message_cleaned
            if token_doc.lemma_ in ["hello", "hi", "hey"]: # Check against doc tokens
                return RULES["hello"]

        return "I've processed your message, but I'm still not sure how to respond to that specific query. Try asking for 'help' for my capabilities."

    # Fallback to original simple partial match if NLP model failed to load
    # This part is reached if nlp is None
    if "name" in user_message_cleaned and ("your" in user_message_cleaned or "who" in user_message_cleaned):
        return RULES["what is your name?"]
    if "hello" in user_message_cleaned or "hi" in user_message_cleaned: # Simple check if no NLP
        return RULES["hello"]

    # Final fallback if NLP is None and simple partial matches also fail
    return "I'm not sure how to respond to that. Try asking for 'help'."
