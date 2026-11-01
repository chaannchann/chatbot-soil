 SoilMate

SoilMate is a local web app for Philippine gardeners. It identifies soil type from a photo, answers soil and crop questions in a chat, recommends crops for the current month, and saves scan and chat history per user.

Everything runs on the machine. No external AI, weather, or geocoding APIs are used.

 Technologies Used

| Part | Technology | Purpose |
| Frontend | HTML, Tailwind CSS, vanilla JavaScript | Single-page chat interface |
| Backend | Python, Flask | Web server and JSON API |
| Database | PostgreSQL, psycopg2 | Crops, soil data, accounts, history |
| Image model | PyTorch, torchvision, MobileNetV2 | Soil photo classification |
| Chatbot | Python, TF-IDF, cosine similarity | Local answer retrieval |
| Authentication | Flask-Login, Flask-Bcrypt | Sessions and password hashing |
| Image handling | Pillow, NumPy | Photo loading, resizing, validation |

 Algorithms and Methods

- Soil classification: MobileNetV2 convolutional neural network with transfer learning, fine-tuned on 10 soil and surface classes (Alluvial, Black, Cinder, Clay, Laterite, Peat, Red, Yellow, concrete, and algae/biocrust). Images are resized to 224x224 and passed through softmax.
- Prediction safety: results below 0.75 confidence or above 0.92 entropy are rejected instead of guessed.
- Photo validation: images are checked for size, brightness, contrast, and how much of the frame looks like soil before prediction.
- Chatbot: retrieval-based. Text is normalized, tokenized, and lightly stemmed; TF-IDF vectors are compared with cosine similarity. A small keyword bonus helps short questions, and a 0.16 threshold triggers a fallback when nothing matches.
- Conversation context: the last soil type is remembered per session so follow-up questions work.
- Planting calendar: the current month is computed in Philippine time (UTC+8), and crops are selected from the `crop_planting_months` table. Results can be filtered by soil type.
- Accounts: passwords are hashed with bcrypt; login sessions use Flask's signed cookie. Guest sessions are ephemeral: scans and chats are not saved or shown in history until the user logs in.

 Main Features

- Full-screen login and registration panel, with a "Continue as guest" option
- Soil photo upload and analysis
- Camera/photo button beside the chat input for quick soil scans
- Chat for soil, compost, fertilizer, pest, and crop questions
- "What can I plant this month?" crop calendar
- Recent scans and chat history restore for signed-in users
- "Clear" action deletes all saved scans, chats, and uploaded scan photos for the account
- 3-dot menu on each history row to delete a single scan
- Guest mode with a login prompt to start saving history
- Formatted chat replies and collapsible crop lists for long results
- Responsive layout with a mobile sidebar drawer
- Light and dark theme toggle that remembers the choice and follows the system preference by default

 Database

Seven tables:

| Table | Stores |
|---|---|
| `soil_types` | The 10 soil/surface profiles, descriptions, and improvement tips |
| `crops` | 35-crop catalog with pH, harvest, and season details |
| `crop_soil_compatibility` | Which crops suit which soils |
| `crop_planting_months` | Which months suit each crop |
| `scans` | Uploaded photo results |
| `chat_logs` | Chat messages and matched intents |
| `users` | Account details and password hashes |

 Project Structure


soilmate/
  app.py                Flask routes and image inference
  chatbot.py            TF-IDF chatbot engine
  planting.py           Month and season logic
  quality.py            Photo quality checks
  history.py            Scan and chat storage
  users.py              Accounts and validation
  db.py                 PostgreSQL helper
  config.py             Environment settings
  soil_catalog.py       Canonical soil class/name mapping
  seed.py               Soil profile and crop catalog seeder
  train.py              Model training script
  database.sql          Fresh-install schema
  migration.sql         Upgrade script for existing databases
  data/
    knowledge_base.json Chatbot intents and answers
    crops.json          Crop catalog
    soils.json          Soil profiles, aliases, and compatible crops
  static/js/app.js      Frontend behavior
  templates/index.html  Page layout
  tests/test_chatbot.py Chatbot tests
  tests/test_soil_catalog.py Soil name normalization tests
  tests/test_history.py History ownership scoping tests


 How to Run

1. Create the database:
   sql
   CREATE DATABASE soilmate_db;
   

2. Load the schema, soil profiles, and crop catalog:
   powershell
   psql -U postgres -d soilmate_db -f database.sql
   .venv\Scripts\python.exe seed.py
   

   For an existing database, apply `migration.sql` first, then run `seed.py`.
   The seeder also renames legacy rows such as `concrete_surface` to their
   canonical names without losing crop compatibility links.

3. Create a `.env` file with your database settings:
   ini
   SECRET_KEY=your-secret-key
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=soilmate_db
   DB_USER=postgres
   DB_PASSWORD=your-password
   

4. Install dependencies and start the app:
   powershell
   .venv\Scripts\pip install -r requirements.txt
   .venv\Scripts\python.exe app.py
   

5. Open `http://127.0.0.1:5000`.

 Tests

powershell
.venv\Scripts\python.exe tests\test_chatbot.py
.venv\Scripts\python.exe tests\test_soil_catalog.py
.venv\Scripts\python.exe tests\test_history.py


Covers 39 chatbot intent cases, soil detection, conversation context, out-of-domain questions, every soil class/name variant, and history privacy scoping.

 Notes

- The only external resource is the Tailwind CSS CDN. All data and processing stay local.
- The classifier recognizes 10 soil and surface classes.
- Guest sessions are ephemeral: no scans or chats are written to the database until the user logs in. Account history is owner-scoped by `user_id` only.
- Signed-in users can delete their own history: the sidebar's "Clear" button removes all scans, chats, and uploaded photos, while the 3-dot menu on a history row deletes just that scan and its photo. Guests cannot delete anything.
- The app uses the Flask development server; use a production server for deployment.
- Uploaded photos are stored in `static/uploads/`.
