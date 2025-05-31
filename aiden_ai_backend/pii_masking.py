import re

# Basic regex for email addresses
EMAIL_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
# Basic regex for simple US phone numbers (does not cover all formats)
# Covers XXX-XXX-XXXX, (XXX) XXX-XXXX, XXXXXXXXXX, XXX.XXX.XXXX etc.
PHONE_REGEX = r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"

MASKING_REPLACEMENT = "[PII_MASKED]"

def mask_pii_in_text(text: str) -> str:
    if not text:
        return text

    # Mask emails
    text = re.sub(EMAIL_REGEX, MASKING_REPLACEMENT, text)
    # Mask phone numbers
    text = re.sub(PHONE_REGEX, MASKING_REPLACEMENT, text)

    return text

# Example Usage (for testing this file directly):
if __name__ == "__main__":
    test_text_email = "My email is test@example.com, please use it."
    test_text_phone = "Call me at (123) 456-7890 or 987.654.3210."
    test_text_mixed = "Contact test@example.com or (123) 555-0101 for info."
    test_text_none = "This is a safe message."

    print(f"Original: {test_text_email} -> Masked: {mask_pii_in_text(test_text_email)}")
    print(f"Original: {test_text_phone} -> Masked: {mask_pii_in_text(test_text_phone)}")
    print(f"Original: {test_text_mixed} -> Masked: {mask_pii_in_text(test_text_mixed)}")
    print(f"Original: {test_text_none} -> Masked: {mask_pii_in_text(test_text_none)}")
