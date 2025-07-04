# email_processor and blah blah blah
import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
from config import YOUR_EMAIL, EMAIL_PASSWORD, IMAP_SERVER, IMAP_PORT

def get_civitai_login_link():
    """get link from civitai mail and fuck it"""
    print(f"🔍 Checking your mail {YOUR_EMAIL}...")
    
    try:
        # connect to mail server
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(YOUR_EMAIL, EMAIL_PASSWORD)
        mail.select("inbox")
        
        # keep searching, we need to find who asking... oh...
        status, messages = mail.search(None, '(FROM "noreply@civitai.com")')
        if status != "OK" or not messages[0]:
            raise Exception("✉️ Mail from CivitAi not found")
        
        # taking last mail and fuck it again
        email_ids = messages[0].split()
        latest_email_id = email_ids[-1]
        
        status, msg_data = mail.fetch(latest_email_id, "(RFC822)")
        if status != "OK":
            raise Exception("❌ Error when receiving an email!")
        
        # parsing... brain not found
        msg = email.message_from_bytes(msg_data[0][1])
        login_link = None
        
        # searching for brain in HTML-code
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html_content = part.get_payload(decode=True).decode()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # searching brain in "Log in button"
                login_button = soup.find('a', string=lambda t: t and "Log in" in t)
                
                if login_button and login_button.has_attr('href'):
                    login_link = login_button['href']
                    break
        
        mail.close()
        mail.logout()
        
        if not login_link:
            raise Exception("❌ There is no login link found in email")
        
        print(f"✅ Successfully get login link")
        return login_link
    
    except Exception as e:
        print(f"❌ Error during processing email: {e}")
        raise