"""Run with: python scripts/test_auth.py
Validates Garmin Connect SSO before building anything on top of it."""
import os
from dotenv import load_dotenv
from garminconnect import Garmin, GarminConnectAuthenticationError

load_dotenv()

email = os.getenv("GARMIN_EMAIL")
password = os.getenv("GARMIN_PASSWORD")

if not email or not password:
    print("ERROR: GARMIN_EMAIL or GARMIN_PASSWORD not set in .env")
    raise SystemExit(1)

print(f"Authenticating as {email}...")
try:
    client = Garmin(email, password)
    client.login()
    profile = client.get_full_name()
    print(f"SUCCESS: Logged in as '{profile}'")
    activities = client.get_activities(0, 1)
    if activities:
        last = activities[0]
        print(f"Last activity: {last.get('activityName')} — {last.get('startTimeLocal')}")
    else:
        print("No activities found.")
except GarminConnectAuthenticationError as e:
    print(f"AUTH FAILED: {e}")
    raise SystemExit(1)
