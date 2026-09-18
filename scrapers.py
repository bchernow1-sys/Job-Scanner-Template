"""
Each function here knows how to read job postings from one *type* of career
site. Many companies use the same underlying career-page platform, so one
scraper function often works for several different companies' sites.

Every scraper takes a URL and returns a list of dicts, each shaped like:
    {"id": "262176", "title": "Proposal Specialist - Onsite", "url": "https://..."}

The "id" must be something stable that won't change between scans, so we can
reliably tell whether a posting is new or one we've already seen.
"""

import json
import re
import urllib.parse
import urllib.request
from playwright.sync_api import sync_playwright


def scrape_phenom(url):
    """Scrape a 'Phenom People' career site. These sites build their job
    list with JavaScript after the page loads, so we use Playwright (an
    invisible browser) to load the page fully before reading it."""
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_selector('a[href*="/job/"]', timeout=30000)

        links = page.query_selector_all('a[href*="/job/"]')
        seen_ids = set()
        for link in links:
            href = link.get_attribute("href") or ""
            match = re.search(r"/job/(\d+)/", href)
            title = (link.inner_text() or "").strip()
            if not match or not title or "Apply" in title:
                continue
            job_id = match.group(1)
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)
            jobs.append({"id": job_id, "title": title, "url": href})

        browser.close()
    return jobs


def scrape_icims(url):
    """Scrape an 'iCIMS' career site. These sites load the real job list
    inside an embedded frame on the page (not the page itself), so we have
    to look inside that frame rather than the main page."""
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)

        # Find the embedded frame that actually holds the job listings.
        job_frame = next((f for f in page.frames if f != page.main_frame), None)
        if job_frame is None:
            raise RuntimeError("Could not find the embedded job-listing frame on this iCIMS page")

        job_frame.wait_for_selector('a[href*="/job?in_iframe"]', timeout=30000)
        links = job_frame.query_selector_all('a[href*="/job?in_iframe"]')

        seen_ids = set()
        for link in links:
            href = link.get_attribute("href") or ""
            match = re.search(r"/jobs/(\d+)/", href)
            if not match:
                continue
            job_id = match.group(1)
            if job_id in seen_ids:
                continue
            raw_text = (link.inner_text() or "").strip()
            title = raw_text.split("\n")[-1].strip()
            if not title:
                continue
            seen_ids.add(job_id)
            jobs.append({"id": job_id, "title": title, "url": href})

        browser.close()
    return jobs


def scrape_genius_sports(url):
    """Scrape Genius Sports' custom-built careers page. Instead of normal
    pagination, it reveals more postings only after repeatedly clicking a
    'Load more' button, so we click it in a loop until it disappears."""
    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_selector('a[href*="/careers/job/"]', timeout=30000)

        page.evaluate("""
            async () => {
                for (let i = 0; i < 20; i++) {
                    const btn = [...document.querySelectorAll('button')]
                        .find(b => b.textContent.includes('Load more'));
                    if (!btn) break;
                    btn.click();
                    await new Promise(r => setTimeout(r, 1200));
                }
            }
        """)

        links = page.query_selector_all('a[href*="/careers/job/"]')
        seen_ids = set()
        for link in links:
            href = link.get_attribute("href") or ""
            match = re.search(r"/job/(\d+)/", href)
            if not match:
                continue
            job_id = match.group(1)
            if job_id in seen_ids:
                continue
            # The title sits in different tags depending on which section
            # of the page the card came from (featured vs. full board).
            title_el = link.query_selector("h4") or link.query_selector("p")
            title = (title_el.inner_text() if title_el else link.inner_text()).strip()
            if not title:
                continue
            seen_ids.add(job_id)
            full_url = href if href.startswith("http") else f"https://www.geniussports.com{href}"
            jobs.append({"id": job_id, "title": title, "url": full_url})

        browser.close()
    return jobs


def scrape_adp_workforce_now(url):
    """Scrape an ADP Workforce Now career site. Unlike the other platforms,
    this one exposes a plain public JSON API directly, so no browser is
    needed at all here -- just a normal web request."""
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    cid = params["cid"][0]
    cc_id = params["ccId"][0]

    api_url = (
        "https://workforcenow.adp.com/mascsr/default/careercenter/public"
        "/events/staffing/v1/job-requisitions"
        f"?cid={cid}&ccId={cc_id}&lang=en_US&locale=en_US&$top=500"
    )
    req = urllib.request.Request(
        api_url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read())

    jobs = []
    for item in data.get("jobRequisitions", []):
        job_id = item.get("itemID")
        title = (item.get("requisitionTitle") or "").strip()
        if not job_id or not title:
            continue
        jobs.append({"id": job_id, "title": title, "url": url})
    return jobs


def scrape_greenhouse(url):
    """Scrape a Greenhouse career site. Greenhouse exposes a plain public
    JSON API keyed by a short 'board token' (the last part of the URL,
    e.g. 'cargomatic' in job-boards.greenhouse.io/cargomatic), so again no
    browser is needed -- just a normal web request."""
    board_token = urllib.parse.urlparse(url).path.strip("/").split("/")[0]
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"

    req = urllib.request.Request(
        api_url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read())

    jobs = []
    for item in data.get("jobs", []):
        job_id = str(item.get("id"))
        title = (item.get("title") or "").strip()
        if not job_id or not title:
            continue
        jobs.append({"id": job_id, "title": title, "url": item.get("absolute_url", url)})
    return jobs


def scrape_paylocity_widget(url):
    """Scrape a company site that embeds a Paylocity recruiting widget.
    Unlike most JavaScript-driven sites, the job data here is baked
    directly into the page's initial HTML (just wrapped in escaped text),
    so a plain web request is enough -- no browser needed."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")

    # The page embeds a JSON blob with its quotes backslash-escaped;
    # unescape once, then pull out each job's id and title.
    unescaped = html.replace('\\"', '"')
    matches = re.findall(r'"jobId":(\d+),"title":"([^"]*)"', unescaped)

    jobs = []
    seen_ids = set()
    for job_id, title in matches:
        title = title.strip()
        if not title or job_id in seen_ids:
            continue
        seen_ids.add(job_id)
        jobs.append({"id": job_id, "title": title, "url": url})
    return jobs


def scrape_paylocity_hosted(url):
    """Scrape a company's Paylocity-hosted careers page (a URL under
    recruiting.paylocity.com). Unlike the embedded-widget version above,
    this one exposes its full job list as clean, valid JSON directly in
    the page (a `window.pageData = {...}` block) -- no unescaping or
    browser needed."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")

    match = re.search(r"window\.pageData\s*=\s*(\{.*?\});\s*\n", html, re.S)
    if not match:
        raise RuntimeError("Could not find the embedded job data on this Paylocity page")
    data = json.loads(match.group(1))

    jobs = []
    for item in data.get("Jobs", []):
        job_id = str(item.get("JobId"))
        title = (item.get("JobTitle") or "").strip()
        if not job_id or not title:
            continue
        jobs.append({"id": job_id, "title": title, "url": url})
    return jobs


def scrape_lever(url):
    """Scrape a Lever career site. Lever exposes a plain public JSON API
    keyed by a short company token (e.g. 'isee' in jobs.lever.co/isee),
    so no browser is needed -- just a normal web request."""
    company_token = urllib.parse.urlparse(url).path.strip("/").split("/")[0]
    api_url = f"https://api.lever.co/v0/postings/{company_token}?mode=json"

    req = urllib.request.Request(
        api_url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read())

    jobs = []
    for item in data:
        job_id = item.get("id")
        title = (item.get("text") or "").strip()
        if not job_id or not title:
            continue
        jobs.append({"id": job_id, "title": title, "url": item.get("hostedUrl", url)})
    return jobs


def scrape_bamboohr(url):
    """Scrape a BambooHR career site. BambooHR exposes a plain public JSON
    API at a predictable address built from the company's subdomain (e.g.
    'thayermahan' in thayermahan.bamboohr.com), so no browser is needed --
    just a normal web request."""
    subdomain = urllib.parse.urlparse(url).hostname.split(".")[0]
    api_url = f"https://{subdomain}.bamboohr.com/careers/list"

    req = urllib.request.Request(
        api_url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read())

    jobs = []
    for item in data.get("result", []):
        job_id = item.get("id")
        title = (item.get("jobOpeningName") or "").strip()
        if not job_id or not title:
            continue
        jobs.append({"id": job_id, "title": title, "url": f"https://{subdomain}.bamboohr.com/careers/{job_id}"})
    return jobs


def scrape_ultipro(url):
    """Scrape a UKG/Ultipro career site. This one exposes a public JSON
    search endpoint, but (unlike the others) it requires a specific POST
    request body rather than being a simple GET -- no browser needed
    though, just a normal web request with that body attached."""
    api_url = url.split("?")[0].rstrip("/") + "/JobBoardView/LoadSearchResults"
    body = {
        "opportunitySearch": {
            "Top": 500,
            "Skip": 0,
            "QueryString": "",
            "OrderBy": [{"Value": "postedDateDesc", "PropertyName": "PostedDate", "Ascending": False}],
            "Filters": [],
        },
        "matchCriteria": {
            "PreferredJobs": [], "Educations": [], "LicenseAndCertifications": [],
            "Skills": [], "hasNoLicenses": False, "SkippedSkills": [],
        },
    }
    req = urllib.request.Request(
        api_url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read())

    jobs = []
    for item in data.get("opportunities", []):
        job_id = item.get("Id")
        title = (item.get("Title") or "").strip()
        if not job_id or not title:
            continue
        jobs.append({"id": job_id, "title": title, "url": url})
    return jobs


def scrape_paycom(url):
    """Scrape a Paycom career site. The real job-search API lives on a
    different subdomain and requires a short-lived security token that's
    minted behind the scenes -- rather than reverse-engineering that
    handshake, we let a real (invisible) browser load the page normally,
    capture the token it uses along the way, then make one direct request
    for every posting at once (the page itself only asks for 10 at a
    time)."""
    captured = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def handle_request(request):
            if "job-posting-previews/search" in request.url and "authorization" not in captured:
                captured["authorization"] = request.headers.get("authorization")
                captured["endpoint"] = request.url

        page.on("request", handle_request)
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)

        if "authorization" not in captured:
            browser.close()
            raise RuntimeError("Could not capture the Paycom search authorization token")

        response = page.request.post(
            captured["endpoint"],
            headers={"Authorization": captured["authorization"], "Content-Type": "application/json"},
            data=json.dumps({
                "skip": 0,
                "take": 500,
                "filtersForQuery": {
                    "distanceFrom": 0, "workEnvironments": [], "positionTypes": [],
                    "educationLevels": [], "categories": [], "travelTypes": [],
                    "shiftTypes": [], "otherFilters": [], "keywordSearchText": "",
                    "location": "", "sortOption": "",
                },
            }),
        )
        data = response.json()
        browser.close()

    jobs = []
    for item in data.get("jobPostingPreviews", []):
        job_id = str(item.get("jobId"))
        title = (item.get("jobTitle") or "").strip()
        if not job_id or not title:
            continue
        jobs.append({"id": job_id, "title": title, "url": url})
    return jobs


# Maps the "type" field in sites.json to the function that knows how to
# scrape it. To support a new kind of career site later, write a new
# function above and add one line here.
SCRAPERS = {
    "phenom": scrape_phenom,
    "icims": scrape_icims,
    "genius_sports": scrape_genius_sports,
    "adp_workforce_now": scrape_adp_workforce_now,
    "greenhouse": scrape_greenhouse,
    "paylocity_widget": scrape_paylocity_widget,
    "paylocity_hosted": scrape_paylocity_hosted,
    "lever": scrape_lever,
    "bamboohr": scrape_bamboohr,
    "ultipro": scrape_ultipro,
    "paycom": scrape_paycom,
}
