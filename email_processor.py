# email_processor and blah blah blah
import imaplib
import email
import re
from bs4 import BeautifulSoup
from config import YOUR_EMAIL, EMAIL_PASSWORD, IMAP_SERVER, IMAP_PORT

def get_civitai_login_link():
    """Extract login link from CivitAI email"""
    print(f"Checking email: {YOUR_EMAIL}")
    
    try:
        # connect to fucking servers
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(YOUR_EMAIL, EMAIL_PASSWORD)
        print("Connected to mail server")
        
        # check your mothe...
        mail.select("inbox")
        
        # civitai and uhm
        status, messages = mail.search(None, '(FROM "noreply@civitai.com")')
        if status != "OK" or not messages[0]:
            # count
            status, all_messages = mail.search(None, "ALL")
            if status == "OK" and all_messages[0]:
                email_count = len(all_messages[0].split())
                print(f"Found {email_count} emails, but none from CivitAI")
            raise Exception("No emails found from CivitAI")
        
        # email id
        email_ids = messages[0].split()
        latest_email_id = email_ids[-1]
        print(f"Found CivitAI email (ID: {latest_email_id.decode()})")
        
        # fetch
        status, msg_data = mail.fetch(latest_email_id, "(RFC822)")
        if status != "OK":
            raise Exception("Failed to fetch email content")
        
        # parse
        msg = email.message_from_bytes(msg_data[0][1])
        login_link = None
        
        # search
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html_content = part.get_payload(decode=True).decode()
                
                # save
                with open("civitai_email.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                
                # parse 2
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # search 2
                patterns = [
                    lambda t: t and "log in" in t.lower(),
                    lambda t: t and "sign in" in t.lower(),
                    lambda t: t and "access your account" in t.lower(),
                    lambda t: t and "click here" in t.lower(),
                ]
                
                # txt patterns
                for pattern in patterns:
                    link = soup.find('a', string=pattern)
                    if link and link.get('href'):
                        login_link = link['href']
                        break
                
                # search url
                if not login_link:
                    all_links = soup.find_all('a', href=True)
                    for link in all_links:
                        if 'civitai.com/api/auth/callback/email' in link['href']:
                            login_link = link['href']
                            break
        
        # cleanup
        mail.close()
        mail.logout()
        
        if not login_link:
            print("Saved email content to civitai_email.html for inspection")
            raise Exception("Login link not found in email")
        
        print(f"Found login link: {login_link[:70]}...")
        return login_link
    
    except Exception as e:
        print(f"Email processing error: {str(e)}")
        # AAAAAAA ERRORS AAAAAA BHASBHJSAHBJSAJHB
        print(f"IMAP Server: {IMAP_SERVER}:{IMAP_PORT}")
        print(f"Email: {YOUR_EMAIL}")
        raise
