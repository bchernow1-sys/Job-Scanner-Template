"""
Turns newly-found job postings into a single outline-formatted push
notification (sent via ntfy.sh) grouped as:

    Parent Group
      Company Name
        - New job title
        - New job title

No account or password is needed for ntfy.sh — the "topic" name below is
effectively a private address. Keep it out of anywhere public.
"""

import os
import urllib.request

# Read from an environment variable instead of hard-coding it, so the
# private topic name never sits directly in the code (or on GitHub).
# Locally: set it with `export NTFY_TOPIC=...` before running the script.
# In the cloud: it will come from a GitHub Actions "secret" (Step 10).
NTFY_TOPIC = os.environ["NTFY_TOPIC"]


def build_outline(new_jobs_by_group):
    """new_jobs_by_group looks like:
        {"I-Squared Capital": {"Summit School Services": [job_dict, ...]},
         None: {"Standalone Co": [job_dict, ...]}}
    A group of None means that company has no parent group — it gets its
    own top-level heading instead of being nested under one.
    Returns a plain-text outline, or "" if there's nothing new."""
    lines = []
    for group, sites in new_jobs_by_group.items():
        if group is None:
            for site_name, jobs in sites.items():
                lines.append(site_name)
                for job in jobs:
                    lines.append(f"  - {job['title']}")
        else:
            lines.append(group)
            for site_name, jobs in sites.items():
                lines.append(f"  {site_name}")
                for job in jobs:
                    lines.append(f"    - {job['title']}")
    return "\n".join(lines)


def send_notification(title, message):
    url = f"https://ntfy.sh/{NTFY_TOPIC}"
    req = urllib.request.Request(
        url,
        data=message.encode("utf-8"),
        headers={"Title": title},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.status
