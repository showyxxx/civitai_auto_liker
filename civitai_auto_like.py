# head fucking script
import time
import random
import os
from playwright.sync_api import sync_playwright
from config import YOUR_EMAIL, HEADLESS_MODE
from email_processor import get_civitai_login_link

def auto_like_images():
    print("🚀 Auto-Like has begun")
    print(f"👤 Using email: {YOUR_EMAIL}")
    
    with sync_playwright() as p:
        # config browser
        browser = p.chromium.launch(headless=HEADLESS_MODE)
        context = browser.new_context()
        page = context.new_page()
        
        # step namba 1: autorization
        if os.path.exists("civitai_session.json"):
            print("🔁 Using saved session...")
            context = browser.new_context(storage_state="civitai_session.json")
            page = context.new_page()
            page.goto("https://civitai.com/images")
            
            # checking for brain... i mean checking for autorization
            if "login" in page.url:
                print("⚠️ Session is outdated and a new authorization is required")
                context.close()
                context = browser.new_context()
                page = context.new_page()
            else:
                print("✅ Session successfully restored")
        
        if "login" in page.url or not os.path.exists("civitai_session.json"):
            print("🔒 Autorization required...")
            login_link = get_civitai_login_link()
            page.goto(login_link)
            
            # waiting for fart from autorization
            try:
                page.wait_for_url("**/images", timeout=30000)
                print("✅ Autorization successful")
            except:
                print("❌ Authorization could not be confirmed")
                return
            
            # saveng autorization
            context.storage_state(path="civitai_session.json")
            print("💾 Session saved!")
        
        # step namba 2: goto images
        print("🔍 Moving to new images...")
        page.goto("https://civitai.com/images?sort=newest&period=allTime")
        
        # step namba 3: likes! likes! likes! likes! likes!
        print("❤️ Likes starting...")
        for i in range(1, 51):
            # wait for load
            page.wait_for_selector('div[data-testid="image-card"]', timeout=10000)
            
            # get imgs
            images = page.query_selector_all('div[data-testid="image-card"]')
            if not images:
                print("❌ Images not found, stopping!")
                break
            
            # get first shit
            image = images[0]
            image.scroll_into_view_if_needed()
            
            # searching for toilet... FASTER PLEASE
            like_button = image.query_selector('button[aria-label="Like"]')
            
            if like_button:
                # check for shit in toilet
                is_liked = like_button.get_attribute("data-liked")
                
                if is_liked == "true":
                    print(f"❤️ [{i}/50] Already liked, skipping")
                else:
                    like_button.click()
                    print(f"❤️ [{i}/50] Like!!!")
                
                # removing from DOM... I don't give a fuck what it's called
                image.evaluate("element => element.remove()")
                
                # FAKE PING YO!! protect from "prove you are not a big asshole" or whatever it's called
                delay = random.uniform(1.5, 3.5)
                time.sleep(delay)
            else:
                print(f"⚠️ [{i}/50] Button not found, skipping")
                image.evaluate("element => element.remove()")
        
        print("🏁 Task complete, lazy man!")
        browser.close()

if __name__ == "__main__":
    auto_like_images()