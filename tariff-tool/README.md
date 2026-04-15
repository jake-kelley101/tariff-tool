# STG NA Tariff Simulator

**Created by Jake Kelley — SE TI STG MF SST SAM P**

A browser-based import duty estimator for Siemens Energy STG North America. Works entirely offline on restricted corporate networks — no plugins, no installation required.

---

## For Users: How to Access the Tool

Once set up, the tool lives at a web address like:
```
https://YOUR-USERNAME.github.io/tariff-tool/
```

Open that URL in any browser on your corporate computer. No downloading, no installation.

**The tool updates itself automatically every week** — just refresh the page to get the latest HTS base duty rates.

---

## For Administrators: Initial Setup (One-Time, ~45 Minutes)

Do this on your **personal PC** (not corporate). You only need to do this once.

### Step 1 — Create a GitHub Account

1. Go to **github.com** and click **Sign up**
2. Choose a username (e.g. `jkelley-se`) — this will be part of your tool's URL
3. Select the **Free** plan
4. Verify your email address

### Step 2 — Create the Repository

1. Click the **+** button (top right) → **New repository**
2. Repository name: `tariff-tool`
3. Set visibility to **Private** (so your parts data isn't publicly visible)
4. Click **Create repository**
5. Note your repository URL: `https://github.com/YOUR-USERNAME/tariff-tool`

### Step 3 — Install Git on Your Personal PC

**Windows:**
1. Download from **git-scm.com/download/win**
2. Run the installer — accept all defaults
3. Open **Git Bash** from the Start menu

**Mac:**
1. Open Terminal
2. Type `git --version` — if not installed, it will prompt you to install

### Step 4 — Upload the Files

Open Git Bash (Windows) or Terminal (Mac) and run these commands one at a time:

```bash
# Navigate to your Downloads folder (adjust path if needed)
cd ~/Downloads

# Clone your empty repository
git clone https://github.com/YOUR-USERNAME/tariff-tool.git

# Move into the folder
cd tariff-tool

# Copy all the files from this zip into this folder
# (see "What's in this package" below)

# Upload everything to GitHub
git add .
git commit -m "Initial upload"
git push origin main
```

When prompted, enter your GitHub username and password.
*(Note: GitHub may ask you to create a Personal Access Token instead of a password — see github.com/settings/tokens, create one with "repo" scope)*

### Step 5 — Enable GitHub Pages

1. Go to your repository on github.com
2. Click **Settings** → **Pages** (left sidebar)
3. Under **Source**, select **Deploy from a branch**
4. Branch: **main**, Folder: **/ (root)**
5. Click **Save**
6. Wait 2–3 minutes, then your tool is live at:
   `https://YOUR-USERNAME.github.io/tariff-tool/`

### Step 6 — Enable GitHub Actions

The weekly rate update runs automatically, but you need to confirm it's enabled:

1. Click the **Actions** tab in your repository
2. If you see a yellow banner saying "Workflows aren't running", click **Enable**
3. Click **Update HTS Base Duty Rates** in the left panel
4. Click **Run workflow** → **Run workflow** to test it manually right now
5. Watch the run complete (should take about 60 seconds)

That's it — the tool is live and self-updating.

---

## Updating Rates Manually

### When §122 or §301 rates change (e.g. §122 expires or is extended)

1. Go to the **Actions** tab on GitHub
2. Click **Update HTS Base Duty Rates**
3. Click **Run workflow**
4. In the popup, enter the new rate in the appropriate field:
   - `Section 122 additional tariff rate` — e.g. `10`
   - `Section 301 China surcharge rate` — e.g. `25`
5. Click **Run workflow**
6. The tool updates within 60 seconds

### When §232 scope changes (new proclamation)

When the §232 covered HTS codes or rates change, you'll need to update the scope file:

1. Update your Section 232 scope Excel file to match the new annexes
2. Run this command on your personal PC (from inside the `tariff-tool` folder):
   ```bash
   python scripts/rebuild_232.py path/to/new_Section_232_Scope.xlsx
   ```
3. Push the changes:
   ```bash
   git add data/sec232.b64 index.html
   git commit -m "Update Section 232 scope - [date of proclamation]"
   git push
   ```

### When the parts reference list changes

1. Export the updated parts list as an Excel file
2. Run:
   ```bash
   python scripts/rebuild_parts.py path/to/new_parts_list.xlsx
   ```
3. Push the changes as above

---

## Repository Structure

```
tariff-tool/
├── index.html                  ← The tool itself (auto-updated weekly)
├── _config.yml                 ← GitHub Pages config
├── README.md                   ← This file
├── data/
│   ├── base_rates.b64          ← HTS base duty rates (auto-updated weekly)
│   ├── parts_data.b64          ← Parts reference database (manual update)
│   ├── mat_lookup.b64          ← Material type lookup (manual update)
│   └── sec232.b64              ← Section 232 scope & rates (manual update)
├── scripts/
│   ├── update_rates.py         ← Weekly automation script (run by GitHub)
│   ├── rebuild_232.py          ← Manual: rebuild 232 scope from new Excel
│   └── rebuild_parts.py        ← Manual: rebuild parts DB from new Excel
└── .github/
    └── workflows/
        └── update-rates.yml    ← GitHub Actions schedule definition
```

---

## Data Sources

| Data | Source | Update frequency |
|---|---|---|
| HTS base duty rates | USITC (hts.usitc.gov) | Automatic, weekly |
| §122 / §301 rates | Manual (workflow input) | As needed |
| §232 scope & rates | Manual (Excel upload) | As needed (new proclamation) |
| Parts reference | Manual (Excel upload) | As needed |

---

## Troubleshooting

**Tool isn't loading / shows blank page**
- Check that GitHub Pages is enabled (Settings → Pages)
- Wait 5 minutes after enabling, then try again
- Try opening in a different browser

**"Workflow run failed" in GitHub Actions**
- Click on the failed run to see the error log
- Most common cause: USITC website temporarily unavailable
- The tool will keep using the previous rates — just retry the workflow

**Team members can't access the URL**
- If the repo is Private, GitHub Pages requires GitHub Pro/Team for private repos
- Solution: Make the repository **Public** (the source data in index.html is compressed/encoded, not easily readable, but be aware it is technically public)
- Alternatively, keep it Private and share the downloaded index.html via SharePoint

---

## Privacy Note

The `data/` folder contains your company's parts database (compressed and base64-encoded). If you make the repository **Public** for GitHub Pages access, this data becomes technically accessible to anyone with the URL. For most purposes the encoding provides adequate obscurity, but if strict data privacy is required, keep the repo **Private** and distribute via SharePoint instead.
