"""
Given a career-page URL, tries to figure out which scraper "type" (a key
in scrapers.SCRAPERS) it needs -- first by checking the site's hostname
against known platforms, then, if that's not conclusive, by fetching the
page and looking for a platform's signature embedded in it (the way a
company site can quietly embed a Paylocity widget, for example).

Returns the type name, or None if no known platform was recognized. A
None result means this site needs someone to investigate and add a new
scraper for it by hand -- it does not mean the site is broken.
"""

import re
import urllib.request
from urllib.parse import urlparse

# Checked first, since the hostname alone is enough to be sure for these.
HOSTNAME_RULES = [
    (lambda host: host.endswith("icims.com"), "icims"),
    (lambda host: host == "workforcenow.adp.com", "adp_workforce_now"),
    (lambda host: host.endswith("greenhouse.io"), "greenhouse"),
    (lambda host: host == "jobs.lever.co", "lever"),
    (lambda host: host.endswith("bamboohr.com"), "bamboohr"),
    (lambda host: host == "recruiting.ultipro.com", "ultipro"),
    (lambda host: host.endswith("paycomonline.net"), "paycom"),
    (lambda host: host == "recruiting.paylocity.com", "paylocity_hosted"),
]


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def detect_type(url):
    host = urlparse(url).hostname or ""

    for matches, type_name in HOSTNAME_RULES:
        if matches(host):
            return type_name

    # Not a platform's own domain -- check whether a company's own site
    # embeds a recognizable platform inside it.
    try:
        html = _fetch(url)
    except Exception:
        return None

    if "cdn.phenompeople.com" in html:
        return "phenom"
    if "lever.co" in html:
        return "lever"
    if "greenhouse.io" in html:
        return "greenhouse"
    if "paylocity" in html.lower():
        unescaped = html.replace('\\"', '"')
        if re.search(r'"jobId":\d+,"title":"', unescaped):
            return "paylocity_widget"

    return None
