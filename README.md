# CivitAI Auto Liker

## Table of Contents
- [Features](#features)
- [Getting Started](#getting-started)
  - [First Run](#first-run)
  - [Subsequent Runs](#subsequent-runs)
- [Important Notes](#important-notes)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [Contributing](#contributing)
- [Disclaimer](#disclaimer)

---

## Features
- Automatically like images to boost activity.
- Simple and lightweight.
- Safe: session data stays local.

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
   playwright install chromium
   ```

3. Configure settings in [config.py](config.py).

4. Run the script:
   ```bash
   python civitai_auto_like.py
   ```

### First Run
- Obtain the login link from your email before running the script.
- This is required only for the first session.

### Subsequent Runs
- Email access is no longer required.
- The script will use the saved session.

---

## Important Notes

- **Data Safety:** Your email and session data stay local and are never sent externally.
- **TOS:** Use responsibly; frequent automated actions might violate CivitAI's terms.
- **Headless Mode:** Running in headless mode may cause issues. Recommended: `HEADLESS_MODE = False`.

---

## Troubleshooting & FAQ

**Q:** Script doesn't work?
- **A:** Try pressing the "+" button (Add Emote) manually first.

**Q:** Script clicks already liked images?
- **A:** This should be minimized with the latest version, but some edge cases may occur.

**Q:** How can I support the developer?
- **A:** Contribution via GitHub issues, forks, and PRs is welcome. No monetary support needed.

---

## Contributing

- Found a bug? Open an issue with the "Bug" tag.
- Got an idea? Open an issue with the "Idea" tag.
- Questions? Open an issue with the "Question" tag.
- Want to fork? Go ahead!

---

## Disclaimer

This script is for **educational purposes**. Use responsibly. We are not responsible for any account issues. Regular manual interaction is recommended.