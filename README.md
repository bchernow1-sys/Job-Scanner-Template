# Job Scanner

Watches a list of company career pages and sends you a single push
notification whenever a genuinely new job posting appears — no account
required, and nothing runs on your own computer once it's set up (it runs
automatically in the cloud, for free).

## What you'll need

- A Mac (these instructions assume macOS)
- A free [GitHub](https://github.com) account (you'll make one if you
  don't have one — this is where the scanning actually runs)
- The free **ntfy** app on your phone (iOS/Android) — this is how you'll
  receive alerts

No coding experience needed. Python (the language this is written in) is
already built into macOS, so there's nothing to install just to run the
setup wizard below.

## Step 1: Run the setup wizard

Open **Terminal** (press `Cmd + Space`, type `Terminal`, press Enter),
then move into this folder and run the wizard:

```bash
cd path/to/this/folder
python3 setup_wizard.py
```

It will ask you a series of plain questions:

- **Notification channel name** — press Enter to auto-generate a private
  one, or make up your own
- **How often to scan** — daily at a time you choose, or every 5 hours
- **Your career pages** — for each one, you'll enter:
  1. A contact or parent group (optional — e.g. an investor name a few
     companies share). Leave blank if this company stands on its own.
  2. The company's name
  3. Its career page URL

For each URL, the wizard automatically checks which job-board platform it
uses (Greenhouse, Lever, iCIMS, and several others are supported out of
the box). If it doesn't recognize a site, it'll say so and skip it — that
site just needs someone familiar with the code to add support for it by
hand; everything else you added still works fine.

When you're done, it writes your `sites.json` (the list of what to watch)
and sets the schedule in `.github/workflows/scan.yml`.

## Step 2: Put it on GitHub

The wizard prints these steps at the end too, but in short:

1. Create a new **private** repository on [github.com](https://github.com/new)
   (leave "Add a README," ".gitignore," and "license" all unchecked)
2. On your new repo's page, click **Add file → Upload files**, and drag in
   every file from this folder *except* the `venv` folder (if you have one)
3. In your repo, go to **Settings → Secrets and variables → Actions →
   New repository secret**, and add:
   - Name: `NTFY_TOPIC`
   - Value: (the channel name the wizard gave you)
4. Install the **ntfy** app and subscribe to that same channel name

## Step 3: Test it

In your repo's **Actions** tab, click **Daily Job Scan**, then **Run
workflow**. This runs it once immediately instead of waiting for the
schedule, so you can confirm everything works. Since this is a first run,
every currently-posted job will count as "new" — that's expected; it
establishes the starting point for future comparisons.

After that, it runs automatically on the schedule you chose, forever,
with no further action needed.

## Adding more sites later

Run `python3 setup_wizard.py` again — **note that it rewrites
`sites.json` from scratch**, so you'll need to re-enter every site you
want to keep, not just the new one. For a single quick addition, it's
often easier to open `sites.json` directly and copy the pattern of an
existing entry.

## What each file does

| File | What it's for |
|---|---|
| `setup_wizard.py` | The interactive setup you just ran |
| `detect.py` | Automatically figures out which platform a career page uses |
| `sites.json` | Your list of career pages to watch |
| `seen_jobs.json` | The scanner's "memory" of what it's already seen |
| `scrapers.py` | The actual logic for reading each supported platform |
| `scanner.py` | Ties it together: scan, compare, notify |
| `notifier.py` | Sends the push notification |
| `.github/workflows/scan.yml` | Tells GitHub when and how to run it |

You shouldn't need to open most of these — the wizard handles the parts
that matter.
