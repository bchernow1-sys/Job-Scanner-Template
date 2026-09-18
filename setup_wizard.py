"""
Interactive setup for a new copy of this job scanner. Run this once after
you've gotten your own copy of the code (`python3 setup_wizard.py`) -- it
asks a few plain-English questions and generates your own sites.json and
daily run schedule. No coding experience needed; just Python itself,
which is already built into macOS.
"""

import json
import re
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

from detect import detect_type

SITES_FILE = "sites.json"
STATE_FILE = "seen_jobs.json"
WORKFLOW_FILE = ".github/workflows/scan.yml"

TIMEZONES = {
    "1": ("Eastern", "America/New_York"),
    "2": ("Central", "America/Chicago"),
    "3": ("Mountain", "America/Denver"),
    "4": ("Pacific", "America/Los_Angeles"),
}


def ask(prompt, default=None):
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def ask_yes_no(prompt, default=True):
    suffix = "Y/n" if default else "y/N"
    answer = input(f"{prompt} ({suffix}): ").strip().lower()
    if not answer:
        return default
    return answer.startswith("y")


def pick_timezone():
    print("\nWhat US timezone are you in?")
    for key, (name, _) in TIMEZONES.items():
        print(f"  {key}) {name}")
    choice = ask("Enter a number", default="1")
    return TIMEZONES.get(choice, TIMEZONES["1"])[1]


def compute_utc_cron(local_hour, local_minute, tz_name):
    """Converts a local time to today's equivalent UTC time. Note: GitHub's
    scheduler runs on a fixed UTC time and won't auto-adjust when Daylight
    Saving changes later in the year -- the run will drift by an hour until
    this is recalculated."""
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz).replace(
        hour=local_hour, minute=local_minute, second=0, microsecond=0
    )
    now_utc = now_local.astimezone(ZoneInfo("UTC"))
    return now_utc.hour, now_utc.minute


def pick_frequency():
    print("\nHow often should the scan run?")
    print("  1) Daily, at a time you choose")
    print("  2) Every 5 hours")
    choice = ask("Enter a number", default="1")

    if choice == "2":
        return "0 */5 * * *", "every 5 hours (00:00, 05:00, 10:00, ... UTC)"

    tz_name = pick_timezone()
    hour = int(ask("What hour (1-12) should the daily scan run at?", default="7"))
    minute = int(ask("What minute?", default="30"))
    am_pm = ask("AM or PM?", default="AM").upper()
    hour_24 = (hour % 12) + (12 if am_pm == "PM" else 0)

    utc_hour, utc_minute = compute_utc_cron(hour_24, minute, tz_name)
    cron = f"{utc_minute} {utc_hour} * * *"
    description = f"daily at {hour}:{minute:02d} {am_pm} your local time"
    return cron, description


def collect_sites():
    sites = []
    skipped = []
    print(
        "\nNow let's add your career pages, one at a time. For each one,\n"
        "you'll enter: (1) a contact/parent group it should be organized\n"
        "under in notifications, (2) the company name, (3) its career page URL."
    )
    while True:
        contact = ask(
            "\nContact or parent group for this company (optional -- leave "
            "blank if it stands on its own, or to finish adding sites)"
        )
        company = ask("Company name (leave blank to finish adding sites)")
        if not contact and not company:
            break
        url = ask("Career page URL")

        print(f"Checking {url} ...")
        detected = detect_type(url)
        if detected:
            print(f"  Recognized platform: {detected}")
            site = {"name": company, "url": url, "type": detected}
            if contact:
                site["group"] = contact
            sites.append(site)
        else:
            print(
                "  Could not automatically recognize this site's platform.\n"
                "  This one can't be set up automatically -- it needs someone\n"
                "  familiar with the code to add it by hand. Skipping it for now."
            )
            skipped.append((company, url))

        if not ask_yes_no("Add another site?"):
            break
    return sites, skipped


def main():
    print("=" * 60)
    print("Job Scanner Setup")
    print("=" * 60)
    print(
        "\nThis sets up your own copy of the job scanner: which career\n"
        "pages to watch, and when to check them each day."
    )

    topic = ask(
        "\nNotification channel name (leave blank to auto-generate a private one)"
    )
    if not topic:
        topic = "job-alerts-" + secrets.token_hex(6)
    print(f"Your notification channel: {topic}")
    print(
        "Install the free 'ntfy' app (iOS/Android) and subscribe to that\n"
        "exact channel name to receive alerts -- no account needed."
    )

    cron, frequency_description = pick_frequency()

    sites, skipped = collect_sites()

    with open(SITES_FILE, "w") as f:
        json.dump(sites, f, indent=2)
    print(f"\nSaved {len(sites)} site(s) to {SITES_FILE}")

    with open(STATE_FILE, "w") as f:
        json.dump({}, f)
    print(f"Reset {STATE_FILE} -- your first scan will treat every current posting as the starting point.")

    with open(WORKFLOW_FILE) as f:
        workflow = f.read()
    new_cron_line = f'    - cron: "{cron}"   # {frequency_description}\n'
    workflow = re.sub(r'    - cron: ".*?"[^\n]*\n', new_cron_line, workflow, count=1)
    with open(WORKFLOW_FILE, "w") as f:
        f.write(workflow)
    print(f"Updated {WORKFLOW_FILE} to run {frequency_description}")

    print("\n" + "=" * 60)
    print("A few manual steps left")
    print("=" * 60)
    print(f"""
1. Create a free GitHub account if you don't have one: https://github.com/signup
2. Create a new repository on github.com (Private, and leave README /
   .gitignore / license all UNCHECKED)
3. Upload every file in this folder to that repository EXCEPT the 'venv'
   folder (use the repo's "Add file > Upload files" button)
4. In your new repo: Settings > Secrets and variables > Actions >
   New repository secret
     Name:  NTFY_TOPIC
     Value: {topic}
5. Install the ntfy app and subscribe to the channel: {topic}
6. In your repo's Actions tab, run the "Daily Job Scan" workflow once by
   hand to confirm everything works.

It will then run automatically {frequency_description}.
""")

    if skipped:
        print("Sites that need manual setup (skipped above):")
        for name, url in skipped:
            print(f"  - {name}: {url}")
        print()


if __name__ == "__main__":
    main()
