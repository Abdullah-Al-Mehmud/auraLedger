# AuraLedger: Voice-Powered Expense Tracker (Django)
**Version:** 1.0.0
**Architecture Type:** Monolithic Django App with Clean Service Layers.

## 1. Core Tech Stack
* **Backend:** Python 3.12, Django 5.x
* **Database:** SQLite3 (Local)
* **Frontend:** Django Templates, Vanilla JS (MediaRecorder API for Audio), Tailwind CSS (via CDN for clean minimal UI).
* **AI Integration:** Google Gemini 2.5 Flash API (google-genai SDK).
* **Design System:** Base: Pure White/Off-White (#F8F9FA). Accent: Indigo/Slate Blue (#4F46E5).

## 2. Directory Structure (Separation of Concerns)
* `core_config/`: Django settings, URLs, WSGI/ASGI.
* `tracker/`: Main Django app.
  * `models.py`: Database schemas only.
  * `services.py`: All business logic and external API calls (Gemini AI parsing). Views must not contain AI logic.
  * `views.py`: Request/Response controllers only.
  * `urls.py`: App routing.
* `templates/`: HTML files.
* `static/`: CSS, JS, Images, Audio temp files.

## 3. Database Schema (Model: Expense)
* `id`: Auto-increment (Primary Key)
* `amount`: Decimal (10, 2)
* `category`: String (Choices: Food, Transport, Bills, Shopping, Other)
* `description`: String (Max 255)
* `date`: DateTime (Auto-add)

## 4. API & Routing Contract
* `GET /` -> Dashboard View (Renders UI, Table, and Record Button).
* `POST /api/record-expense/` -> Receives raw audio blob from frontend JS, sends to `services.py` for Gemini AI parsing, saves to DB, returns JSON response.
* `DELETE /api/expense/<id>/` -> Deletes an expense.

## 5. AI Pipeline Flow
1. User clicks and holds the "Record" button on the web UI.
2. JS MediaRecorder captures audio -> sends as multipart/form-data to Django.
3. Django View receives the file -> passes it to services.parse_audio_to_expense(audio_file).
4. Gemini API parses audio -> returns strict JSON (Amount, Category, Description).
5. Django saves the instance -> Returns success to UI -> UI updates the table dynamically.
