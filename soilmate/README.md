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
- Bilingual retrieval: Filipino phrasings live in `data/knowledge_base_tl.json` and are indexed together with the English ones. Filipino function words ("paano", "bakit", "ang", "mga") are detected to choose the reply language, so Taglish questions get Filipino answers. No translation API is used.
- Conversation context: the last soil type is remembered per session so follow-up questions work.
- Planting calendar: the current month is computed in Philippine time (UTC+8), and crops are selected from the `crop_planting_months` table. Results can be filtered by soil type.
- Accounts: passwords are hashed with bcrypt; login sessions use Flask's signed cookie. Guest sessions are ephemeral: scans and chats are not saved or shown in history until the user logs in.

 Main Features

- Full-screen login and registration panel, with a "Continue as guest" option
- Soil photo upload and analysis
- Camera/photo button beside the chat input for quick soil scans: opens a live webcam preview on desktop (capture, or upload instead) and the native camera sheet on phones and tablets
- Chat for soil, compost, fertilizer, pest, and crop questions
- English and Filipino (Tagalog) chat, including Taglish; use the header **EN/TL** button to switch the suggested questions and calendar labels, or just type in Filipino and the bot replies in Filipino
- "What can I plant this month?" crop calendar
- Unified history restores saved scans and chats for signed-in users
- Soil scans are added to the open conversation, and reopening it restores the photo and analysis card
- "Clear" action deletes all saved scans, chats, and uploaded scan photos for the account
- 3-dot menu on each history row to delete a conversation and its scan
- Guest mode with a login prompt to start saving history
- Edit profile from the header avatar: change username, email, and a custom avatar photo (center-cropped to 256x256) or remove it
- Formatted chat replies and collapsible crop lists for long results
- Responsive layout with a mobile sidebar drawer
- Light and dark theme toggle that remembers the choice and follows the system preference by default

 Suggested Questions

- What can I plant this month?
- How do I test soil pH? [How do I test pH?]
- How do I make compost? [How to make compost?]
- What organic fertilizer is best for sandy soil in the Philippines? [Best organic fertilizer?]
- How often should I water my plants? [Watering schedule]

- Greeting — What can I plant this month? / How do I test soil pH? / How do I make compost?
- Capabilities — What can I plant this month? / How much compost should I mix in? / How often should I water?
- Thanks — What can I plant this month? / How do I improve my soil?
- Soil pH basics — How do I test soil pH? / How do I fix acidic soil? / What is the pH of red soil?
- Testing soil pH — How do I fix acidic soil? / What is the ideal pH for pechay? / How do I make compost?
- Correcting soil pH — How do I test soil pH? / What is the pH of red soil? / How do I improve red soil?
- Making compost — How much compost should I mix with my soil? / How do I make organic fertilizer? / How do I improve yellow soil?
- How much compost to mix — How do I make compost? / How do I improve yellow soil? / What is the pH of my soil?
- Organic fertilizers — How much compost should I mix in? / How do I improve yellow soil? / How often should I fertilize?
- Fertilizer application timing — What organic fertilizer is best? / How often should I water? / Why are my leaves turning yellow?
- Yellowing leaves — How often should I water? / How do I test soil pH? / What organic fertilizer is best?
- Ampalaya (bitter gourd) care — What organic fertilizer is best? / How do I control pests organically? / What can I plant this month?
- Specific crop care — What can I plant this month? / Why are my leaves turning yellow? / How often should I water?
- Black soil — What can I plant this month? / How much compost should I mix in? / How often should I water? q
- Red soil — How do I fix acidic soil? / How much compost should I mix in? / What can I plant this month?
- Yellow / sandy soil — What organic fertilizer is best for sandy soil? / How much compost should I mix in? / What can I plant this month?
- Drainage and waterlogging — How often should I water? / How do I improve red soil? / What can I plant during rainy season?
- Watering schedule — How do I improve drainage? / How do I make compost? / Why are my leaves turning yellow?
- Mulching — How often should I water? / How do I make compost? / How do I improve yellow soil?
- Organic pest control — Why are my ampalaya leaves turning yellow? / How do I prevent plant disease? / What can I plant this month?
- Plant diseases — How do I improve drainage? / How often should I water? / How do I control pests organically?
- Philippine planting seasons — What can I plant this month? / How do I improve drainage? / What can I plant during rainy season?
- What to plant now — no follow-up chips, because the reply already contains the month's crop list.
- Seeds and germination — What can I plant this month? / How long until harvest? / How do I make compost?
- Days to harvest — What can I plant this month? / How do I store my harvest? / How do I control pests organically?
- Container and urban gardening — How often should I water? / What organic fertilizer is best? / What can I plant this month?
- Crop rotation and soil fertility — How do I make compost? / What can I plant this month? / How do I test soil pH?
- Soil types overview — What can I plant this month? / How do I improve red soil? / How do I improve yellow soil?
- Typhoon and heavy rain protection — How do I improve drainage? / What can I plant during rainy season? / How do I prevent plant disease?

Straight up questions:

1. Best organic fertilizer?
2. How do I control pests organically?
3. How do I fix acidic soil?
4. How do I improve drainage?
5. How do I improve my soil?
6. How do I improve red soil?
7. How do I improve yellow soil?
8. How do I make compost?
9. How do I make organic fertilizer?
10. How do I prevent plant disease?
11. How do I store my harvest?
12. How do I test pH?
13. How do I test soil pH?
14. How long until harvest?
15. How much compost should I mix in?
16. How much compost should I mix with my soil?
17. How often should I fertilize?
18. How often should I water my plants?
19. How often should I water?
20. How to make compost?
21. Watering schedule
22. What can I plant during rainy season?
23. What can I plant now?
24. What can I plant this month?
25. What is the ideal pH for pechay?
26. What is the pH of my soil?
27. What is the pH of red soil?
28. What is the right soil pH for vegetables?
29. What organic fertilizer is best for sandy soil in the Philippines?
30. What organic fertilizer is best for sandy soil?
31. What organic fertilizer is best?
32. Why are my ampalaya leaves turning yellow?
33. Why are my leaves turning yellow?

 Filipino (Tagalog) Support

Click the **EN/TL** button in the header to switch the suggested questions, welcome message, chat input placeholder, and planting-calendar labels. You can also type in Filipino or Taglish at any time — the bot detects Filipino question words and answers in Filipino even when the interface is in English.

Sample Filipino questions:

- Kumusta?
- Ano ang tamang pH ng lupa para sa gulay?
- Paano ko susuriin ang pH ng lupa?
- Paano gumawa ng compost?
- Gaano karaming compost ang ihahalo ko sa lupa?
- Ano ang pinakamagandang organic fertilizer?
- Bakit naninilaw ang dahon ng ampalaya ko?
- Paano ko mapapabuti ang pulang lupa?
- Gaano kadalas akong magdidilig?
- Ano ang puwedeng itanim ngayong buwan?
- Paano ko kokontrolin ang peste nang organic?
- Paano protektahan ang halaman sa bagyo?

 Filipino content lives in `data/knowledge_base_tl.json`; it is merged with the English intents when the app starts.

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
| `users` | Account details, avatar, and password hashes |

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

For a fresh laptop, follow `HOW_TO_SET_UP.md` in the repository root: it covers the `.env` file, creating the database by hand in pgAdmin, and starting the app. The summary below is the same flow.

1. Create the database (in pgAdmin: Databases → Create → Database…, name it `soilmate_db`):

2. Load the schema, soil profiles, and crop catalog (in pgAdmin: open `database.sql` in the Query Tool and press F5, then run the seeder):
   powershell
   .venv\Scripts\python.exe seed.py
   

   For a database created before the planting calendar, scan/chat history, and
   user accounts existed, apply `migration.sql` first, then run `seed.py`.
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

 Setup Questions and Answers

- **How do I set up and run this on another laptop?**
  Follow `HOW_TO_SET_UP.md`. Create `soilmate\.env` first because it is the only file missing from a clone. Then create a virtual environment, `pip install -r requirements.txt`, create the database, run `database.sql`, run `seed.py`, and run `app.py`.

- **Is the database set up manually in pgAdmin, or with terminal commands?**
  Manually in pgAdmin. Right-click **Databases → Create → Database…**, name it `soilmate_db`, open `database.sql` in the Query Tool with the folder icon, and press F5.

- **Do I have to install Python and pgAdmin as part of the setup?**
  No. `HOW_TO_SET_UP.md` assumes Python 3.10+ and PostgreSQL with pgAdmin are already installed.

- **Is `database.sql` up to date and ready to execute as-is?**
  Yes. It was tested on an empty database: it creates all seven tables, `seed.py` then loads 10 soils and 35 crops, and `/api/chat`, `/api/plant-now`, and `/api/history` all respond. Run it once only; the starter crop and compatibility inserts have no `ON CONFLICT`, so a second run stops with duplicate key errors.

- **Is `migration.sql` still needed?**
  No. A fresh install only needs `database.sql`, and the current development database already has every table and canonical soil name. `migration.sql` is only for databases created before the planting calendar, scan/chat history, and user accounts existed.

 Tests

powershell
.venv\Scripts\python.exe tests\test_chatbot.py
.venv\Scripts\python.exe tests\test_soil_catalog.py
.venv\Scripts\python.exe tests\test_history.py




