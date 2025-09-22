import os
import sys
import time
import random
import json
import tempfile
import shutil
import subprocess
import webbrowser
from pathlib import Path

from playwright.sync_api import sync_playwright

import config
from email_processor import get_civitai_login_link

# ---------------- Configs (with defaults) ----------------
YOUR_EMAIL = getattr(config, "YOUR_EMAIL", "<unknown>")
HEADLESS_MODE = getattr(config, "HEADLESS_MODE", False)
SESSION_SAVE_DELAY = getattr(config, "SESSION_SAVE_DELAY", 5)
ACTION_DELAY = getattr(config, "ACTION_DELAY", 0.5)
TARGET_LIKES = getattr(config, "TARGET_LIKES", 50)
CLICK_RETRY = getattr(config, "CLICK_RETRY", 1)
LIKE_CONFIRM_TIMEOUT = getattr(config, "LIKE_CONFIRM_TIMEOUT", 3.0)
AUTO_WAIT_FOR_USER = getattr(config, "AUTO_WAIT_FOR_USER", True)

# Updater settings
UPDATE_BRANCH = getattr(config, "UPDATE_BRANCH", "main")
AUTO_UPDATE = getattr(config, "AUTO_UPDATE", False)

# Files & URLs
SESSION_FILE = "civitai_session.json"
LIKED_FILE = "liked_images.json"
LOGIN_FIXED_URL = "https://civitai.com/login?returnUrl=%2Fimages&reason=switch-accounts"
IMAGES_URL = "https://civitai.com/images?sort=Newest"

# Selectors
BUTTON_SELECTOR_PRIMARY = 'button[class*="Reactions_reactionBadge"]'
BUTTON_SELECTOR_FALLBACK = 'button:has(p:has-text("👍")), button:has-text("👍")'
REACTIONS_PANEL_SVG = 'button:has(svg.tabler-icon-plus):has(svg.tabler-icon-mood-smile)'
REACTIONS_PANEL_BUTTON = 'button:has(svg.tabler-icon-mood-smile)'

# Send button candidates (kept for potential future usage)
SEND_BUTTON_SELECTORS = [
    'button:has-text("Send login link")',
    'button:has-text("Send login")',
    'button:has-text("Send link")',
    'button:has-text("Send")',
    'button[type="submit"]',
    'button:has-text("Continue")',
]

# ---------------- Utility helpers ----------------
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

# -------- liked ids helpers --------
def load_liked_ids():
    # load previously liked image ids from json
    if os.path.exists(LIKED_FILE):
        try:
            with open(LIKED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(map(str, data))
        except Exception as e:
            print("WARNING: failed to read liked file:", e)
            return set()
    return set()

def save_liked_ids_atomic(liked_ids):
    # atomic write for liked ids file
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

# -------- DOM helpers (image id extraction etc.) --------
def extract_image_id_from_button(btn):
    # JS walk up tree to find nearest /images/<id> link
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

def get_like_count_from_button(btn):
    # parse numeric like count text from button
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

# -------- click + confirm --------
def click_and_confirm_like(btn, timeout=LIKE_CONFIRM_TIMEOUT, retries=CLICK_RETRY):
    # click reaction button and confirm via attributes or count change
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

# -------- session saving helper --------
def save_session_state(context):
    # save Playwright storage state to file
    try:
        context.storage_state(path=SESSION_FILE)
        print("INFO: session saved to", SESSION_FILE)
    except Exception as e:
        print("WARNING: failed to save session:", e)

# -------- session validation and manual-login flow --------
def ensure_valid_session(playwright):
    # Try to restore session. If invalid -> open system browser to login URL and WAIT for user.
    browser = playwright.chromium.launch(headless=HEADLESS_MODE)
    # try to restore saved session
    if os.path.exists(SESSION_FILE):
        try:
            context = browser.new_context(storage_state=SESSION_FILE,
                                          viewport={"width": 1366, "height": 768})
            page = context.new_page()
            try:
                page.goto(IMAGES_URL, wait_until="domcontentloaded", timeout=15000)
            except Exception:
                pass
            # detect sign-in presence
            try:
                signin = page.query_selector('a:has-text("Sign in")') or page.query_selector('a:has-text("Log in")')
            except Exception:
                signin = None
            if signin:
                print("INFO: saved session appears expired or invalid.")
            else:
                print("INFO: loaded session from", SESSION_FILE)
                return browser, context, page
        except Exception as e:
            print("WARNING: failed to load saved session:", e)

    # no valid session -> open system browser and wait for user to complete login
    try:
        print("INFO: no valid session found. Opening system browser for manual login:", LOGIN_FIXED_URL)
        webbrowser.open(LOGIN_FIXED_URL)
        print("INFO: Please complete login (solve CAPTCHA if present) in your system browser.")
        input("After you finished logging in in your browser press Enter here to continue...")
    except KeyboardInterrupt:
        print("\nINFO: interrupted by user during manual login wait.")
        try:
            browser.close()
        except Exception:
            pass
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
    except Exception as e:
        print("WARNING: failed to open system browser:", e)
        try:
            browser.close()
        except Exception:
            pass
        return browser, None, None

    # user signaled ready -> attempt to fetch magic link from email and complete login in Playwright
    # try multiple attempts (small loop) because email delivery may be delayed
    attempts = 6
    wait_between_attempts = 5  # seconds
    login_link = None
    for i in range(attempts):
        try:
            print(f"INFO: attempting to fetch login email (attempt {i+1}/{attempts})...")
            login_link = get_civitai_login_link()
            if login_link:
                print("INFO: login link retrieved from email.")
                break
        except Exception as e:
            print("INFO: login link not found yet:", str(e))
        if i < attempts - 1:
            print(f"INFO: waiting {wait_between_attempts} seconds before next email check...")
            time.sleep(wait_between_attempts)

    if not login_link:
        print("ERROR: could not obtain login link from email after multiple attempts. Aborting manual flow.")
        try:
            browser.close()
        except Exception:
            pass
        # return context None so caller can decide what to do
        return browser, None, None

    # open the magic link inside Playwright context to finalize login and save session
    try:
        context = browser.new_context(viewport={"width": 1366, "height": 768})
        page = context.new_page()
        print("INFO: opening magic login link inside Playwright to finalize session...")
        try:
            page.goto(login_link, wait_until="domcontentloaded", timeout=20000)
        except Exception:
            try:
                page.goto(login_link)
            except Exception as e:
                print("ERROR: failed to open login link inside Playwright:", e)
                try:
                    browser.close()
                except Exception:
                    pass
                return browser, None, None
        # give site a moment to finish login and redirect
        time.sleep(SESSION_SAVE_DELAY)
        # save session state
        try:
            save_session_state(context)
        except Exception:
            pass
        # navigate to images page to continue
        try:
            page.goto(IMAGES_URL, wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pass
        print("INFO: manual login flow complete, session saved.")
        return browser, context, page
    except Exception as e:
        print("ERROR: completing login in Playwright failed:", e)
        try:
            browser.close()
        except Exception:
            pass
        return browser, None, None

# -------- Updater: branch-based (kept) --------
def is_git_repo():
    return os.path.isdir(".git")

def get_remote_origin_url():
    try:
        res = subprocess.run(["git", "config", "--get", "remote.origin.url"], capture_output=True, text=True, check=True)
        url = res.stdout.strip()
        return url if url else None
    except Exception:
        return None

def current_and_remote_branch_commits(branch):
    try:
        subprocess.run(["git", "fetch", "origin"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            r1 = subprocess.run(["git", "rev-parse", branch], check=True, capture_output=True, text=True)
            local = r1.stdout.strip()
        except Exception:
            r1 = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
            local = r1.stdout.strip()
        try:
            r2 = subprocess.run(["git", "rev-parse", f"origin/{branch}"], check=True, capture_output=True, text=True)
            remote = r2.stdout.strip()
        except Exception:
            remote = None
        return local, remote
    except Exception:
        return None, None

def check_for_updates_branch_based():
    if not is_git_repo():
        print("INFO: not a git repository; update check skipped")
        return False
    local, remote = current_and_remote_branch_commits(UPDATE_BRANCH)
    if not local or not remote:
        print("INFO: could not determine branch commits; skipping update check")
        return False
    if local != remote:
        print(f"INFO: update available on branch '{UPDATE_BRANCH}' (local != origin/{UPDATE_BRANCH})")
        return True
    print(f"INFO: no updates found on branch '{UPDATE_BRANCH}'")
    return False

def perform_branch_update_and_restart():
    if not is_git_repo():
        print("WARNING: not a git repository; cannot perform branch update")
        return False
    cfg_path = Path("config.py")
    backup_path = None
    try:
        if cfg_path.exists():
            backup_dir = Path(tempfile.mkdtemp(prefix="cfg_backup_"))
            backup_path = backup_dir / "config.py"
            shutil.copy2(cfg_path, backup_path)
            print("INFO: config.py backed up to", str(backup_path))
        print(f"INFO: fetching origin and switching to branch '{UPDATE_BRANCH}'...")
        subprocess.run(["git", "fetch", "origin"], check=True)
        try:
            subprocess.run(["git", "checkout", UPDATE_BRANCH], check=True)
        except Exception:
            subprocess.run(["git", "checkout", "-b", UPDATE_BRANCH, f"origin/{UPDATE_BRANCH}"], check=True)
        subprocess.run(["git", "pull", "origin", UPDATE_BRANCH], check=True)
        print("INFO: git pull completed")
        if backup_path and backup_path.exists():
            shutil.copy2(backup_path, cfg_path)
            print("INFO: config.py restored from backup")
        print("INFO: restarting script with updated code...")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        print("ERROR: update failed:", e)
        try:
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, cfg_path)
                print("INFO: config.py restored after failure")
        except Exception:
            pass
        return False
    finally:
        try:
            if backup_path:
                shutil.rmtree(backup_path.parent, ignore_errors=True)
        except Exception:
            pass

def check_and_prompt_update_branch_flow():
    try:
        available = check_for_updates_branch_based()
        if not available:
            return False
        if AUTO_UPDATE:
            print("INFO: AUTO_UPDATE enabled; performing update now...")
            return perform_branch_update_and_restart()
        ans = input(f"Update available on branch '{UPDATE_BRANCH}'. Update now? [Y/n]: ").strip().lower()
        if ans in ("", "y", "yes"):
            return perform_branch_update_and_restart()
        print("INFO: update skipped by user.")
        return False
    except Exception as e:
        print("WARNING: update check failed:", e)
        return False

# -------- open reactions panel (keeps previous behavior) --------
def WAIT_FOR_USER_RESPONSE():
    try:
        input("PAUSE: could not auto-show reactions. Please make likes visible manually and press Enter to continue...")
    except KeyboardInterrupt:
        print("\nINFO: execution interrupted by user.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

def open_reactions_panel(page):
    try:
        btn = None
        try:
            btn = page.wait_for_selector(REACTIONS_PANEL_SVG, timeout=3000)
        except Exception:
            btn = None

        if not btn:
            try:
                btn = page.wait_for_selector(REACTIONS_PANEL_BUTTON, timeout=1000)
            except Exception:
                btn = None

        if not btn:
            try:
                btn = page.query_selector(REACTIONS_PANEL_SVG)
            except Exception:
                btn = None

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

        if AUTO_WAIT_FOR_USER:
            print("INFO: reactions panel button not found automatically; waiting for user action...")
            WAIT_FOR_USER_RESPONSE()
            try:
                btn2 = page.query_selector(REACTIONS_PANEL_SVG) or page.query_selector(REACTIONS_PANEL_BUTTON)
                if btn2:
                    try:
                        btn2.scroll_into_view_if_needed()
                        time.sleep(0.12)
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
            print("INFO: reactions panel still not found after user action; proceeding")
            return False
        else:
            print("INFO: reactions panel button not found; proceeding without opening it")
            return False

    except Exception as e:
        print("WARNING: open_reactions_panel error:", e)
        return False

# -------- Main liking routine --------
def auto_like_images():
    print("INFO: Starting CivitAI Auto Liker")
    print(f"INFO: Account: {mask_email(YOUR_EMAIL)}")

    liked_ids = load_liked_ids()
    print(f"INFO: loaded {len(liked_ids)} previously liked image ids")

    with sync_playwright() as p:
        # ensure session; if not present this function will open system browser and WAIT for user,
        # then attempt to fetch magic link and finalize login inside Playwright
        browser, context, page = ensure_valid_session(p)

        if context is None or page is None:
            print("ERROR: no active Playwright context/page after login flow. Exiting.")
            try:
                if browser:
                    browser.close()
            except Exception:
                pass
            return

        try:
            page.goto(IMAGES_URL, wait_until="domcontentloaded")
        except Exception:
            pass

        clicked = open_reactions_panel(page)
        if not clicked and AUTO_WAIT_FOR_USER:
            pass

        liked_count = 0
        attempts_without_progress = 0
        print(f"INFO: target new likes this run: {TARGET_LIKES}")

        while liked_count < TARGET_LIKES:
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

# -------- Entrypoint --------
if __name__ == "__main__":
    # pre-update check (branch-based)
    try:
        check_and_prompt_update_branch_flow()
    except Exception as e:
        print("WARNING: update flow failed:", e)

    # run main logic
    auto_like_images()

