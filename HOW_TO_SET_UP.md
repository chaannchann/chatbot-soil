

## 1. Get the project

 powershell
cd C:\projs
git clone https://github.com/chaannchann/chatbot-soil.git
cd chatbot-soil
 


- `soilmate\data\` → the whole folder, into `C:\projs\chatbot-soil\soilmate\data\`
  It must contain `knowledge_base.json`, `crops.json`, `soils.json`.
- Do not copy `.env` or `.venv`.

## 2. Install the Python packages

 powershell
cd C:\projs\chatbot-soil\soilmate
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
 

If activation is blocked, run `Set-ExecutionPolicy -Scope Process Bypass` first.

## 3. Create the database in pgAdmin

1. Open  pgAdmin  from the Start menu.
2. In the left sidebar open  Servers → PostgreSQL 17 . Type the `postgres` password if asked.
3. Right-click  Databases → Create → Database… 
4. Name it `soilmate_db`, click  Save .
5. Click `soilmate_db` once to select it, then open  Tools → Query Tool .
6. Click the  folder icon  (Open File), choose `C:\projs\chatbot-soil\soilmate\database.sql`, then press  F5  (Execute). Wait for "Query executed successfully". (Do not run `migration.sql`; that one is only for upgrading an old database.)
7. Right-click `soilmate_db` →  Refresh . Under  Schemas → public → Tables  you should see 7 tables.

## 4. Create the `.env` file

Create `C:\projs\chatbot-soil\soilmate\.env` with this content:

 ini
SECRET_KEY=change-this-to-any-long-random-text
FLASK_DEBUG=True

DB_HOST=localhost
DB_PORT=5432
DB_NAME=soilmate_db
DB_USER=postgres
DB_PASSWORD=your-postgres-password

UPLOAD_FOLDER=static/uploads
MODEL_PATH=soil_model.pth
CLASSES_PATH=classes.json
CONFIDENCE_THRESHOLD=0.75
 

## 5. Load the soil and crop data

 powershell
cd C:\projs\chatbot-soil\soilmate
.\.venv\Scripts\python.exe seed.py
 

You should see `Seeded 10 soil profiles` and `Seeded 35 crops`.

## 6. Run it

 powershell
.\.venv\Scripts\python.exe app.py
 

Open `http://127.0.0.1:5000`. Always start the app from the `soilmate` folder.

Next time you only repeat step 6.
