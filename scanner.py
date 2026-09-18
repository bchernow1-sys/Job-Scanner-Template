"""
The main script. Visits every site in sites.json, compares what it finds
against what it saw last time (stored in seen_jobs.json), and reports only
the postings that are genuinely new.
"""

import json
import os
from scrapers import SCRAPERS
from notifier import build_outline, send_notification

STATE_FILE = "seen_jobs.json"


def load_sites(path="sites.json"):
    with open(path) as f:
        return json.load(f)


def load_state(path=STATE_FILE):
    """Returns {site_name: [job_id, job_id, ...]} from last run, or an
    empty dict if this is the very first run."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def save_state(state, path=STATE_FILE):
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def main():
    sites = load_sites()
    state = load_state()
    new_state = {}
    new_jobs_by_group = {}

    for site in sites:
        scraper = SCRAPERS[site["type"]]
        print(f"Scanning {site['name']} ({site['url']}) ...")
        jobs = scraper(site["url"])
        current_ids = {job["id"] for job in jobs}

        previously_seen_ids = set(state.get(site["name"], []))
        new_jobs = [job for job in jobs if job["id"] not in previously_seen_ids]

        print(f"  Found {len(new_jobs)} new posting(s) since last scan:")
        for job in new_jobs:
            print(f"   - [{job['id']}] {job['title']}")

        if new_jobs:
            group = site.get("group")  # None if this site has no parent group
            new_jobs_by_group.setdefault(group, {})[site["name"]] = new_jobs

        new_state[site["name"]] = list(current_ids)

    save_state(new_state)
    print("\nSaved current results as the baseline for next time.")

    if new_jobs_by_group:
        outline = build_outline(new_jobs_by_group)
        total_new = sum(
            len(jobs) for sites in new_jobs_by_group.values() for jobs in sites.values()
        )
        title = f"{total_new} new job posting(s)"
        send_notification(title, outline)
        print(f"\nSent notification:\n{title}\n{outline}")
    else:
        print("\nNo new postings — no notification sent.")


if __name__ == "__main__":
    main()
