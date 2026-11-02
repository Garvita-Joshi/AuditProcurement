"""Utility script to verify and test SMTP email delivery using current .env settings."""
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.agentic_ai.messaging import get_smtp_config, test_smtp_connection

def main():
    cfg = get_smtp_config()
    print("=" * 60)
    print("       AuditAI Sourcing Agent — SMTP Verification Test")
    print("=" * 60)
    print(f"Host              : {cfg.get('host') or '(Not set)'}")
    print(f"Port              : {cfg.get('port')}")
    print(f"Username          : {cfg.get('username') or '(Not set)'}")
    print(f"Password          : {'*' * len(cfg.get('password')) if cfg.get('password') else '(Not set)'}")
    print(f"From Sender Email : {cfg.get('from_email') or '(Not set)'}")
    print(f"Test Redirect Mail: {cfg.get('redirect_email') or '(Not set)'}")
    print(f"Use SSL/TLS       : {cfg.get('use_ssl')}")
    print(f"Configured        : {cfg.get('configured')}")
    print("=" * 60)

    if not cfg.get('configured'):
        print("\n[!] SMTP is NOT configured yet.")
        print("Please edit your .env file and set:")
        print("  SOURCING_SMTP_HOST=smtp.gmail.com")
        print("  SOURCING_SMTP_PORT=587")
        print("  SOURCING_SMTP_USERNAME=your_email@gmail.com")
        print("  SOURCING_SMTP_PASSWORD=your_16_char_google_app_password")
        print("  SOURCING_MAIL_FROM=your_email@gmail.com")
        print("  SOURCING_TEST_REDIRECT_EMAIL=your_email@gmail.com")
        return

    target = sys.argv[1] if len(sys.argv) > 1 else cfg.get('redirect_email') or cfg.get('username')
    print(f"\nAttempting to send verification email to: {target} ...")
    res = test_smtp_connection(target)
    if res['success']:
        print(f"\n[SUCCESS] {res['message']}")
        print("Check your inbox (and spam folder) for the test email!")
    else:
        print(f"\n[FAILED] {res['message']}")

if __name__ == '__main__':
    main()

