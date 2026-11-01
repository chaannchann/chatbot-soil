1. Upgrade the Chatbot "Brain" (Agricultural Q&A)
Currently, app.py only has basic keyword checks for ph and fertilizer. follow-up questions like:
"How much compost should I mix with this yellow soil?"
"Why are my ampalaya leaves turning yellow?"
"What organic fertilizer is best for sandy soil in the Philippines?"
2. Dynamic "What Can I Plant Right Now?" Feature
Add a query that checks the current month in the Philippines against your database's ideal_planting_season (Wet Season vs. Dry Season).
When a user clicks a button or asks "What can I plant now?", the bot queries PostgreSQL for crops suitable for the current month.
3. Save Scans & Chat History in PostgreSQL
Add a user_scans or chat_logs table in PostgreSQL.
Keep a history of previously uploaded soil images and their predictions so users don't lose their records on page refresh.
4. Quick Suggestion Chips (UI Enhancement)
Add clickable prompt buttons above the chat input (e.g., 🌱 What can I plant this month?, 🧪 How do I test pH?, 🍂 How to make compost?) so users can interact with one click without typing everything manually.
5. Add more plants suggestion base on the soil and weather in the philippines. 
6. Add proper response if the AI cannot identify the soil the user sent.
7. Add user account, like any AI software/tool. make sure it has history.


IMPORTANT:
this system must not be using any APIs.
It must be self trained responses.
