import time
import random
import os
import json
import tempfile
import sys
from playwright.sync_api import sync_playwright
import config
from email_processor import get_civitai_login_link

# config defaults
YOUR_EMAIL = getattr(config, "YOUR_EMAIL", "<unknown>")
HEADLESS_MODE = getattr(config, "HEADLESS_MODE", False)
SESSION_SAVE_DELAY = getattr(config, "SESSION_SAVE_DELAY", 5)
ACTION_DELAY = getattr(config, "ACTION_DELAY", 2.0)
TARGET_LIKES = getattr(config, "TARGET_LIKES", 50)
CLICK_RETRY = getattr(config, "CLICK_RETRY", 1)
LIKE_CONFIRM_TIMEOUT = getattr(config, "LIKE_CONFIRM_TIMEOUT", 3.0)
AUTO_WAIT_FOR_USER = getattr(config, "AUTO_WAIT_FOR_USER", True)

# files
SESSION_FILE = "civitai_session.json"
LIKED_FILE = "liked_images.json"

# selectors
BUTTON_SELECTOR_PRIMARY = 'button[class*="Reactions_reactionBadge"]'
BUTTON_SELECTOR_FALLBACK = 'button:has(p:has-text("👍")), button:has-text("👍")'
REACTIONS_PANEL_SVG = 'button:has(svg.tabler-icon-plus):has(svg.tabler-icon-mood-smile)'
REACTIONS_PANEL_BUTTON = 'button:has(svg.tabler-icon-mood-smile)'

# mask email for logs
def mask_email(email: str) -> str:
    # mask email keeping first and last char of local-part
    try:
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            masked_local = local[0] + "*" * max(0, len(local) - 1)
        else:
            masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
        return masked_local + "@" + domain
    except Exception:
        return "***"

# load liked ids from file
def load_liked_ids():
    if os.path.exists(LIKED_FILE):
        try:
            with open(LIKED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(map(str, data))
        except Exception as e:
            print("WARNING: failed to read liked file:", e)
            return set()
    return set()

# atomic save liked ids
def save_liked_ids_atomic(liked_ids):
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="liked_", suffix=".json", dir=".")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(list(liked_ids), f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, LIKED_FILE)
    except Exception as e:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        print("WARNING: failed to save liked file:", e)

# extract image id from button by searching nearest /images/ link
def extract_image_id_from_button(btn):
    js = r"""
    node => {
      try {
        let el = node;
        for (let i = 0; i < 6 && el; i++) {
          if (el.querySelector) {
            const link = el.querySelector('a[href^="/images/"]');
            if (link) {
              const href = link.getAttribute('href');
              if (!href) return null;
              const parts = href.split('/').filter(Boolean);
              return parts.length ? parts[parts.length - 1] : null;
            }
          }
          el = el.parentElement;
        }
        const fallback = document.querySelector('a[href^="/images/"]');
        if (fallback) {
          const href = fallback.getAttribute('href');
          const parts = href.split('/').filter(Boolean);
          return parts.length ? parts[parts.length - 1] : null;
        }
      } catch(e) { return null; }
      return null;
    }
    """
    try:
        img_id = btn.evaluate(js)
        return str(img_id) if img_id is not None else None
    except Exception:
        return None

# parse like count inside button text
def get_like_count_from_button(btn):
    js = r"""
    node => {
      try {
        const t = node.innerText || "";
        const m = t.match(/(\d+)/);
        return m ? parseInt(m[1], 10) : 0;
      } catch(e) { return 0; }
    }
    """
    try:
        cnt = btn.evaluate(js)
        return int(cnt or 0)
    except Exception:
        return 0

# click and confirm like
def click_and_confirm_like(btn, timeout=LIKE_CONFIRM_TIMEOUT, retries=CLICK_RETRY):
    try:
        initial_count = get_like_count_from_button(btn)
    except Exception:
        initial_count = None

    for attempt in range(retries + 1):
        try:
            btn.scroll_into_view_if_needed()
            time.sleep(0.12)
            btn.click()
        except Exception as e:
            print("WARNING: btn.click() exception:", e)
            if attempt == retries:
                return False
            time.sleep(0.5 * (attempt + 1))
            continue

        start = time.time()
        while time.time() - start < timeout:
            try:
                dl = btn.get_attribute("data-liked")
                if dl and str(dl).lower() == "true":
                    return True
                ap = btn.get_attribute("aria-pressed")
                if ap and str(ap).lower() in ("true", "1"):
                    return True
                al = btn.get_attribute("aria-label")
                if al and "un" in al.lower():
                    return True
                if initial_count is not None:
                    new_count = get_like_count_from_button(btn)
                    if isinstance(new_count, int) and new_count > initial_count:
                        return True
            except Exception:
                pass
            time.sleep(0.25)

        if attempt < retries:
            print("WARNING: confirmation failed, retrying click...")
            time.sleep(0.5 + attempt)
            continue
        return False
    return False

# save session state
def save_session_state(context):
    try:
        context.storage_state(path=SESSION_FILE)
        print("INFO: session saved to", SESSION_FILE)
    except Exception as e:
        print("WARNING: failed to save session:", e)

# ensure session and page available
def ensure_session_and_page(playwright):
    browser = playwright.chromium.launch(headless=HEADLESS_MODE)
    if os.path.exists(SESSION_FILE):
        try:
            context = browser.new_context(storage_state=SESSION_FILE,
                                          viewport={"width": 1366, "height": 768})
            page = context.new_page()
            page.goto("https://civitai.com/images?sort=Newest", wait_until="domcontentloaded")
            try:
                signin = page.query_selector('a:has-text("Sign in")')
            except Exception:
                signin = None
            if signin:
                print("INFO: saved session appears expired — will obtain new magic link")
            else:
                print("INFO: loaded session from", SESSION_FILE)
                return browser, context, page
        except Exception as e:
            print("WARNING: error loading saved session:", e)

    context = browser.new_context(viewport={"width": 1366, "height": 768})
    page = context.new_page()
    print("INFO: obtaining magic link from email...")
    login_link = get_civitai_login_link()
    print("INFO: opening magic link...")
    page.goto(login_link, wait_until="domcontentloaded")
    time.sleep(SESSION_SAVE_DELAY)
    save_session_state(context)
    try:
        page.goto("https://civitai.com/images?sort=Newest", wait_until="domcontentloaded")
    except Exception:
        pass
    return browser, context, page

# required function name: WAIT_FOR_USER_RESPONSE
def WAIT_FOR_USER_RESPONSE():
    # prompt the user to make likes visible manually and press Enter
    try:
        input("PAUSE: could not auto-show reactions. Please make likes visible manually and press Enter to continue...")
    except KeyboardInterrupt:
        print("\nINFO: execution interrupted by user.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

# improved open_reactions_panel with wait + fallback to user prompt
def open_reactions_panel(page):
    # try to wait a short time for a reactions-open button and click it once
    try:
        # wait up to 3 seconds for the SVG-based button
        try:
            btn = page.wait_for_selector(REACTIONS_PANEL_SVG, timeout=3000)
        except Exception:
            btn = None

        # if not found, try the general mood-smile selector (also wait a short time)
        if not btn:
            try:
                btn = page.wait_for_selector(REACTIONS_PANEL_BUTTON, timeout=1000)
            except Exception:
                btn = None

        # if still not found, try a quick query (no wait)
        if not btn:
            try:
                btn = page.query_selector(REACTIONS_PANEL_SVG)
            except Exception:
                btn = None

        # if found — click and return True
        if btn:
            try:
                btn.scroll_into_view_if_needed()
                time.sleep(0.12)
                btn.click()
                print("INFO: reactions panel button clicked")
                time.sleep(ACTION_DELAY)
                return True
            except Exception as e:
                print("WARNING: error clicking reactions panel button:", e)
                return False

        # not found — if configured, wait for user response
        if AUTO_WAIT_FOR_USER:
            print("INFO: reactions panel button not found automatically; waiting for user action...")
            WAIT_FOR_USER_RESPONSE()
            # after user responded, attempt one more short find & no-fail click
            try:
                btn2 = page.query_selector(REACTIONS_PANEL_SVG) or page.query_selector(REACTIONS_PANEL_BUTTON)
                if btn2:
                    try:
                        btn2.scroll_into_view_if_needed()
                        time.sleep(0.12)
                        # do not fail if click throws
                        try:
                            btn2.click()
                            print("INFO: reactions panel button clicked after user action")
                        except Exception:
                            pass
                    except Exception:
                        pass
                    time.sleep(ACTION_DELAY)
                    return True
            except Exception:
                pass
            # if still not found — continue without it
            print("INFO: reactions panel still not found after user action; proceeding")
            return False
        else:
            print("INFO: reactions panel button not found; proceeding without opening it")
            return False

    except Exception as e:
        print("WARNING: open_reactions_panel error:", e)
        return False

# main routine
def auto_like_images():
    print("INFO: Starting CivitAI Auto Liker")
    print(f"INFO: Account: {mask_email(YOUR_EMAIL)}")

    liked_ids = load_liked_ids()
    print(f"INFO: loaded {len(liked_ids)} previously liked image ids")

    with sync_playwright() as p:
        browser, context, page = ensure_session_and_page(p)

        try:
            page.goto("https://civitai.com/images?sort=Newest", wait_until="domcontentloaded")
        except Exception:
            pass

        clicked = open_reactions_panel(page)
        if not clicked and AUTO_WAIT_FOR_USER:
            # open_reactions_panel already waits for user if configured
            pass

        liked_count = 0
        attempts_without_progress = 0
        print(f"INFO: target new likes this run: {TARGET_LIKES}")

        while liked_count < TARGET_LIKES:
            # try primary then fallback selector
            buttons = []
            try:
                buttons = page.query_selector_all(BUTTON_SELECTOR_PRIMARY)
            except Exception:
                buttons = []
            if not buttons:
                try:
                    buttons = page.query_selector_all(BUTTON_SELECTOR_FALLBACK)
                except Exception:
                    buttons = []

            if not buttons:
                print("INFO: no reaction buttons in view — scrolling to load more")
                page.evaluate("window.scrollBy(0, window.innerHeight * 1.3)")
                time.sleep(1.5 + random.random())
                attempts_without_progress += 1
                if attempts_without_progress > 20:
                    print("WARNING: too many empty scrolls — aborting")
                    break
                continue

            progress_this_cycle = False

            for btn in buttons:
                if liked_count >= TARGET_LIKES:
                    break

                try:
                    try:
                        inner = btn.inner_text().strip()
                    except Exception:
                        inner = ""
                    if "👍" not in inner:
                        continue

                    img_id = extract_image_id_from_button(btn)
                    if not img_id:
                        continue

                    if img_id in liked_ids:
                        continue

                    try:
                        if not btn.is_visible():
                            continue
                    except Exception:
                        pass

                    ok = click_and_confirm_like(btn, timeout=LIKE_CONFIRM_TIMEOUT, retries=CLICK_RETRY)
                    if not ok:
                        print(f"INFO: click confirmation failed for img {img_id}; skipping")
                        continue

                    liked_count += 1
                    liked_ids.add(img_id)
                    save_liked_ids_atomic(liked_ids)
                    print(f"INFO: [{liked_count}/{TARGET_LIKES}] liked image id={img_id}")
                    progress_this_cycle = True

                    time.sleep(ACTION_DELAY)

                except Exception as e:
                    print("WARNING: error processing button:", str(e)[:200])
                    continue

            if not progress_this_cycle:
                attempts_without_progress += 1
            else:
                attempts_without_progress = 0

            if liked_count >= TARGET_LIKES:
                break

            page.evaluate("window.scrollBy(0, window.innerHeight * 1.3)")
            time.sleep(1.0 + random.random() * 1.5)

            if attempts_without_progress > 25:
                print("WARNING: no progress for many iterations — exiting")
                break

        print(f"INFO: done — new likes this run: {liked_count}")

        try:
            context.close()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass

if __name__ == "__main__":
    auto_like_images()
