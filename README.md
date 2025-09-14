# CivitAI Auto Liker

**Русская версия:** [ru-RU_README.md](ru-RU_README.md)

## Table of Contents
- [Features](#features)
- [Getting Started](#getting-started)
  - [First Run](#first-run)
  - [Subsequent Runs](#subsequent-runs)
- [Important Notes](#important-notes)
- [Compatibility](#compatibility)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [Contributing](#contributing)
- [Disclaimer](#disclaimer)

---

## Features
- Automatically like images to boost activity.
- Lightweight and simple to use.
- Safe: session and email data stay local.
- Detects invalid sessions and handles manual login.
- Auto-updater for stable releases.
- Waits for user input if reactions panel is not visible.

---

## Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/showyxxx/civitai-auto-liker.git
   cd civitai-auto-liker
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

3. Configure settings in [config.py](config.py).
   For detailed IMAP setup instructions (Gmail, Apple, Yandex, Outlook, ProtonMail, Zoho, etc.), see [EMAIL_SETUP_GUIDE.md](EMAIL_SETUP_GUIDE.md).

4. Run the script:
   ```bash
   py civitai_auto_like.py   # Windows
   python3 civitai_auto_like.py  # Linux / UserLand
   ```

### First Run
- Obtain the login link from your email before running the script.
- Complete the login manually if required.
- This is required only for the first session.

### Subsequent Runs
- Email access is no longer required.
- Script uses the saved session.

---

## Important Notes

- **Data Safety:** All email and session data remain local and are never sent externally.
- **TOS Compliance:** Use responsibly; frequent automated actions may violate CivitAI terms.
- **Headless Mode on Windows/Linux:** May cause detection issues. Recommended: `HEADLESS_MODE = False`.
- **Headless Mode on UserLand:** Must be set to `True` due to display limitations.

---

## Compatibility

- **Windows:** Fully supported.
- **Linux:** Fully supported.
- **Termux:** Playwright is **not supported**. Use [UserLand](https://userland.tech/) as an alternative.
- **MacOS:** Supported.
- **Mobile devices:** Only via UserLand or similar Linux emulation; native mobile Python is not supported.

---

## Troubleshooting & FAQ

**Q:** Script cannot detect reactions panel?
- **A:** Script will wait for user; make sure likes are visible manually and press Enter.

**Q:** Magic link not received?
- **A:** Check spam folder. Script retries email fetch several times.

**Q:** Auto-login fails or CAPTCHA appears?
- **A:** Auto-login is disabled due to Cloudflare detection. Use manual login as described.

**Q:** How can I support the developer?
- **A:** Contributions via GitHub issues, forks, or pull requests are welcome. No monetary support is required.

---

## Contributing

- Found a bug? Open an issue with the "Bug" tag.
- Got an idea? Open an issue with the "Idea" tag.
- Questions? Open an issue with the "Question" tag.
- Want to fork? Go ahead!

---

## Disclaimer

This script is for **educational purposes** only.
Use responsibly. We are not responsible for any account issues. Regular manual interaction is recommended.

