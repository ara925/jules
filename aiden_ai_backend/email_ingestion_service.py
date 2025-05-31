import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone # Ensure timezone is imported
from sqlmodel import Session, select
from sqlalchemy.orm import sessionmaker # For creating a session if engine is passed directly

# Assuming models.inbox.InboxEmail and database.engine are accessible
# Adjust imports based on your project structure if this service is moved
from .models.inbox import InboxEmail
from .database import engine # Direct import of engine for session creation

# IMAP Configuration (FOR TEST PURPOSES ONLY - USE ENV VARS IN REAL APP)
# Replace with your actual test Gmail account and App Password if using Gmail
IMAP_HOST = "imap.gmail.com"
IMAP_USER = "your_test_email@gmail.com"  # Needs to be replaced by user
IMAP_PASS = "your_gmail_app_password"    # Needs to be replaced by user

def decode_mime_header(header_string: str) -> str:
    decoded_parts = decode_header(header_string)
    parts = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            parts.append(part.decode(charset or 'utf-8', errors='replace'))
        else:
            parts.append(str(part)) # Ensure it's a string
    return "".join(parts)

def get_email_body(msg: email.message.Message) -> tuple[str, str]:
    body_text = ""
    body_html = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            try:
                charset = part.get_content_charset() or 'utf-8'
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    body_text += part.get_payload(decode=True).decode(charset, errors='replace')
                elif content_type == "text/html" and "attachment" not in content_disposition:
                    body_html += part.get_payload(decode=True).decode(charset, errors='replace')
            except Exception: # Broad except for decoding issues
                pass # Ignore decoding errors for simplicity
    else:
        content_type = msg.get_content_type()
        charset = msg.get_content_charset() or 'utf-8'
        try:
            if content_type == "text/plain":
                body_text = msg.get_payload(decode=True).decode(charset, errors='replace')
            elif content_type == "text/html":
                body_html = msg.get_payload(decode=True).decode(charset, errors='replace')
        except Exception: # Broad except
            pass
    return body_text.strip(), body_html.strip()

def parse_email_date(date_str: str) -> datetime:
    dt = parsedate_to_datetime(date_str)
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None: # Naive datetime
         return dt.replace(tzinfo=timezone.utc) # Assume UTC if no timezone info
    return dt.astimezone(timezone.utc) # Convert to UTC if timezone-aware

def ingest_emails_from_mailbox():
    results = {"new_emails_ingested": 0, "errors": []}

    if IMAP_USER == "your_test_email@gmail.com" or IMAP_PASS == "your_gmail_app_password":
        results["errors"].append("IMAP credentials are placeholders. Please configure them.")
        return results

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(IMAP_USER, IMAP_PASS)
        status, _ = mail.select("inbox") # Connect to inbox.
        if status != 'OK':
            results["errors"].append("Failed to select inbox.")
            mail.logout()
            return results

        # Search for all unseen emails
        search_criteria = "(UNSEEN)"
        # search_criteria = "ALL" # To fetch all emails for testing
        status, messages = mail.search(None, search_criteria)

        if status != "OK":
            results["errors"].append(f"Failed to search emails with criteria '{search_criteria}'.")
            mail.logout()
            return results

        email_ids = messages[0].split()
        if not email_ids:
            results["message"] = "No new emails to ingest." # Add a message field to results
            mail.logout()
            return results

        # Create a new session for this ingestion task
        # SQLModel recommends Session(engine) for specific tasks.
        with Session(engine) as db_session:
            for email_id_bytes in email_ids:
                try:
                    status, msg_data = mail.fetch(email_id_bytes, "(RFC822)")
                    if status == "OK":
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                msg = email.message_from_bytes(response_part[1])

                                msg_id_header = msg.get("Message-ID", "").strip("<>")
                                if not msg_id_header:
                                    # Attempt to create a more unique ID if Message-ID is missing
                                    # This is a fallback, real emails should always have a Message-ID
                                    uid_str = email_id_bytes.decode()
                                    date_hdr = msg.get("Date", "")
                                    from_hdr = msg.get("From", "")
                                    subject_hdr = msg.get("Subject", "")
                                    msg_id_header = f"generated_{uid_str}_{hash(date_hdr+from_hdr+subject_hdr)}@aiden.ai"

                                existing = db_session.exec(select(InboxEmail).where(InboxEmail.message_id == msg_id_header)).first()
                                if existing:
                                    print(f"Skipping already processed email: {msg_id_header}")
                                    continue

                                subject = decode_mime_header(msg.get("Subject", "No Subject"))
                                sender = decode_mime_header(msg.get("From", "Unknown Sender"))
                                recipient = decode_mime_header(msg.get("To", "Unknown Recipient"))
                                date_str = msg.get("Date")

                                received_dt = datetime.now(timezone.utc) # Default if Date header is missing/unparseable
                                if date_str:
                                    try:
                                        received_dt = parse_email_date(date_str)
                                    except Exception as e_parse:
                                        print(f"Could not parse date string '{date_str}': {e_parse}. Using current UTC time.")

                                body_text, body_html = get_email_body(msg)

                                new_email_entry = InboxEmail(
                                    message_id=msg_id_header,
                                    subject=subject,
                                    sender_address=sender,
                                    recipient_address=recipient,
                                    body_text=body_text,
                                    body_html=body_html,
                                    received_at=received_dt,
                                    # status default is "unread"
                                )
                                db_session.add(new_email_entry)
                                results["new_emails_ingested"] += 1

                                # Optionally mark as seen on server:
                                # mail.store(email_id_bytes, '+FLAGS', '\\Seen')

                except Exception as e_fetch:
                    error_detail = f"Error processing email ID {email_id_bytes.decode()}: {str(e_fetch)}"
                    print(error_detail)
                    results["errors"].append(error_detail)
                    # Decide if one error should stop the whole batch or continue

            if results["new_emails_ingested"] > 0: # Only commit if there's something new
                db_session.commit()

        mail.logout()
    except imaplib.IMAP4.error as e_imap: # More specific IMAP errors
        error_detail = f"IMAP Error: {str(e_imap)}"
        print(error_detail)
        results["errors"].append(error_detail)
    except Exception as e_global: # Catch-all for other issues like network problems
        error_detail = f"Global error during email ingestion: {str(e_global)}"
        print(error_detail)
        results["errors"].append(error_detail)

    return results
