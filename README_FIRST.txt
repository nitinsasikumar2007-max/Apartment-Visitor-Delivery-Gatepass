APARTMENT VISITOR & DELIVERY GATEPASS — WORKING MODEL

This is a runnable local demo application with a React website, FastAPI backend and SQLite database. No Supabase account or API key is required for this local demo.

REQUIREMENTS
- Windows 10/11
- Python 3.10+
- Node.js 18+ (includes npm)
- Internet for first-time package installation

START
1. Extract this ZIP.
2. Double-click START_PROJECT.bat.
3. Wait for package installation and both servers to start.
4. Website: http://localhost:5173
   API documentation: http://127.0.0.1:8000/docs
5. Keep the two terminal windows open while using the website.

DEMO
- Security Desk: create visitor/delivery requests, verify OTP, record exit.
- Resident Panel: approve or reject pending requests.
- Entry Records: view entry and exit audit records.

WORKFLOW
Register visitor -> resident approval -> six-digit OTP generated -> security verifies OTP -> entry logged -> security records exit -> exit logged.

This local model uses SQLite for zero-credential setup and refreshes dashboards automatically every 2 seconds to simulate realtime updates. The original production architecture can use Supabase Realtime; this local model is intended to run immediately for college demonstration.

Data persists in backend/gatepass.db. To reset, stop the servers and delete that database file; it will be recreated with demo flats/residents.

For real deployment, add authentication, role-based authorization, HTTPS, secure OTP delivery, rate limiting and backups.
