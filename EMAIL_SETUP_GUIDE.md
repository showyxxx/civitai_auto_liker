# Email Setup Guide (IMAP + App Passwords)

Русская версия: [Email Setup Guide](EMAIL_SETUP_GUIDE.ru-RU.md)

This guide explains how to configure IMAP and application-specific passwords for different email providers.

---

## Gmail
1. Enable **IMAP** in [Gmail settings](https://mail.google.com/mail/u/0/#settings/fwdandpop).
2. Enable **2FA** on your Google account.
3. Generate an **App Password** at [Google App Passwords](https://myaccount.google.com/apppasswords).
4. Use this password in `config.py` instead of your normal password.

**IMAP settings:**
- Server: `imap.gmail.com`
- Port: `993`

---

## Apple (iCloud)
1. Enable **2FA** on your Apple ID.
2. Generate an **App Password** at [Apple ID settings](https://appleid.apple.com/account/manage).
3. Use this password in `config.py`.

**IMAP settings:**
- Server: `imap.mail.me.com`
- Port: `993`

---

## Yandex
1. Enable IMAP in [Yandex.Mail settings](https://mail.yandex.com).
2. Enable 2FA in Yandex.Passport.
3. Generate a **Password for External Apps** in account settings.
4. Use it in `config.py`.

**IMAP settings:**
- Server: `imap.yandex.com`
- Port: `993`

---

## Outlook / Hotmail
1. Enable 2FA in your Microsoft account.
2. Generate an **App Password** under "Security → App passwords".
3. Use it in `config.py`.

**IMAP settings:**
- Server: `outlook.office365.com`
- Port: `993`

---

## ProtonMail
⚠️ Requires **ProtonMail Bridge** (for paid accounts only).  
Without Bridge, IMAP is not supported.

**IMAP settings (via Bridge):**
- Server: `127.0.0.1`
- Port: `1143`

---

## Zoho Mail
1. Enable 2FA in Zoho account.
2. Generate an **App Password** under "Security → App Passwords".
3. Use it in `config.py`.

**IMAP settings:**
- Server: `imap.zoho.com`
- Port: `993`

---
