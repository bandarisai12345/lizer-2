🧰 Core Components
🔹 IntentAgent

Uses Gemini LLM for intent extraction and response generation.

Determines next conversational actions.

Handles structured JSON output for logic decisions.

🔹 AgentTools

get_available_slots(): Fetches open time slots from mock_schedule.json.

recommend_appointment_type(): Suggests appointment type based on reason.

book_appointment(): Generates unique booking IDs and stores confirmation.

🔹 In-Memory Storage

Stores user sessions and confirmed bookings during runtime.

Easily replaceable with a persistent database (e.g., PostgreSQL, Redis).

🧠 LLM Integration (Gemini)

Gemini is used to:

Extract intents, entities, and structured data.

Generate natural, empathetic responses.

Recommend appointment types based on conversation context.

If the Gemini API key is not provided, the system gracefully defaults to mock responses.

https://github.com/user-attachments/assets/ac8cedeb-e987-4cc7-af7d-98f9582ac3d9

