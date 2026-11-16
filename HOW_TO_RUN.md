# How to run - step by step (Windows)

There are two parts. **Part A is the new Bangladesh 64-district flood-risk model - it does not need MySQL.**
Part B is the original city dashboard (needs MySQL/XAMPP).

---

## Part A - Bangladesh district model (NASA POWER + IMERG)

### A1. Install Python (once)
1. Download Python from https://www.python.org/downloads/ (3.14 was used; 3.12 or 3.13 also work).
2. **Tick "Add Python to PATH"** on the first installer screen, then Install.

### A2. Unzip the project
Unzip `smart_flood_system.zip` anywhere (for example `C:\Users\YOU\Downloads\`). Open the folder: you must see
`run_ml.bat`, `floodml`, `data` and `frontend` directly inside it.

### A3. First run (20-40 minutes, needs internet)
1. Double-click **`run_ml.bat`**. On the first start it creates the Python environment and installs the packages (2-3 min).
2. In the menu press **`5`** to check your setup. You should see `[ok]` lines and the NASA parameters that were found.
3. Press **`1`**. It will:
   - download NASA POWER daily data for 64 districts + 6 upstream stations (progress lines `[ 12/70] ...`),
   - build the flood labels from `data\flood_labels\bd_flood_events.csv`,
   - build the dataset **`data\bd_district_training_dataset.csv`** (open it in Excel if you like),
   - train and validate the model,
   - score all districts.
4. When it finishes, open **`outputs\report.md`**. Look at the table *"Does it beat a simple rule?"*:
   if the model's PR-AUC is not clearly higher than the rule's, do not trust the model.

If the download is interrupted (internet loss), just run option 1 again - it continues where it stopped.

### A4. See the results
Press **`3`** in the menu. The browser opens **http://127.0.0.1:8000/bangladesh**: a map and table of all 64 districts with
risk levels, a button *Refresh from NASA*, a CSV download and the model's validation numbers. Keep the black window open.

The same 64 districts are also in the **main dashboard** (`run_ml.bat` option 3, then open http://127.0.0.1:8000/):
open the *Location* menu, scroll to **Bangladesh districts (64)**, pick any district and press **Run prediction**.
The table at the bottom of that page lists all 64 districts with their latest risk; click a row to open it.

### A4b. Put the daily data into MySQL (optional)
1. Start **MySQL** in the XAMPP Control Panel.
2. In `run_ml.bat` press **`6`**. It creates the tables `bd_locations`, `bd_daily_data`, `bd_flood_events`, `bd_flood_days`,
   `bd_predictions` and the view `bd_latest_risk` inside your `smart_flood_system` database and fills them (about a minute).
3. Open http://localhost/phpmyadmin -> `smart_flood_system` to browse them. Ready-made queries: `sql\bd_example_queries.sql`.

Options **1** and **2** export automatically if MySQL is running (if it is not, they just print a note and carry on).
Your existing tables and data are not touched.

### A4c. See what conditions came before the floods
In `run_ml.bat` press **`7`** (needs step A3 done once). It writes `outputs\flood_drivers.md` and opens it: how much rain fell
before the documented floods, how unusual it was, soil wetness, timing, and upstream rain in India. The per-event numbers are in
`data\bd_flood_event_conditions.csv` (open in Excel).

### A5. Every day after that
Run `run_ml.bat` and press **`2`** (about a minute) or press *Refresh from NASA* on the map page.

### A6. Teach the model more floods
Edit `data\flood_labels\bd_flood_events.csv` (one row per event, with source URLs), then in the menu press **`4`**.
See `data\flood_labels\README_district_labels.md`.

---

## Part B - City dashboard (MySQL)

1. Install **XAMPP** and click **Start** next to **MySQL** (it turns green).
2. In `.env` the default database line works with a fresh XAMPP (`root` with empty password). If you set a password, write it after
   the colon: `mysql+pymysql://root:YOURPASSWORD@localhost:3306/smart_flood_system`.
3. Double-click **`setup.bat`** once (creates the database, loads weather and flood history).
4. Double-click **`run.bat`**. The dashboard opens at http://127.0.0.1:8000/ - keep the black window open.
   Its header has a link to the Bangladesh page.

Back up an existing database first (phpMyAdmin -> your database -> Export). Next time just start MySQL and run `run.bat`.

---

## Problems?
| Message / symptom | Fix |
|---|---|
| `python` is not recognized | reinstall Python with **Add Python to PATH**, reopen the window |
| `NASA POWER problem ...` | internet issue; run the same option again (downloads resume) |
| Option 5 shows `[FAIL]` for NASA | check the internet/firewall; try again later (NASA servers can be busy) |
| `/bangladesh` says "No predictions yet" | run option **1** first |
| `ERROR: Too few flood examples ...` | add events to `bd_flood_events.csv` |
| Browser says "refused to connect" | the server is not running or still starting: wait 10 s and refresh; keep the black window open |
| Port 8000 already in use | close the other black window |
| The map is grey or empty | the map pictures come from tile.openstreetmap.org: check the internet connection or firewall. A message under the map says when they cannot load |
| I want dark (or light) mode | press **Switch to dark mode** / **Switch to light mode** in the left panel; the choice is remembered. Without a choice the page follows your computer's setting |
| Could not connect to MySQL (Part B) | start MySQL in XAMPP; check the password in `.env` |

To run something by hand: open Command Prompt in the project folder, type `.venv\Scripts\activate`, then e.g.
`python -m floodml doctor`.
