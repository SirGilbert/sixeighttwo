📄 SixEightTwo — Version 1 Documentation

(Lock Date: 04 May 2026)

⸻

🧠 1. System Overview

SixEightTwo V1 is a web-based SLA monitoring dashboard designed to track repair jobs, evaluate performance, and highlight risks in real time.

It transforms raw CSV exports into:
	•	Visual insights
	•	SLA intelligence
	•	Technician accountability

Accessible across:
	•	Desktop
	•	Mobile (same WiFi network)

⸻

⚙️ 2. Core Capabilities

📊 Job Dashboard
	•	Displays all jobs from database
	•	Live SLA classification:
	•	OK
	•	AT RISK
	•	SLA BREACH
	•	PARTS DELAY
	•	LONG WAIT
	•	CRITICAL BACKLOG

⸻

🚦 Live Warning System (Badges)

Each job includes a visual indicator:

State			Meaning
🟢 SAFE		Plenty of time left
🟠 WARNING		Approaching SLA
🔴 IMMINENT		About to breach
🔥 BREACHED	Already exceeded

Includes:
	•	Tooltip (days remaining)
	•	Color-coded row highlighting

⸻

📈 KPI Summary Cards

Top dashboard shows:
	•	Total OK jobs
	•	SLA breaches
	•	Delays
	•	At-risk jobs

⸻

⚠️ At-Risk Panel
	•	Dedicated section for early-warning jobs
	•	Sorted by highest urgency

⸻

📊 Data Visualisation
	•	Doughnut chart (SLA distribution)
	•	Scatter chart (risk mapping vs days)

⸻

👨‍🔧 Technician Performance
	•	Jobs handled
	•	Breaches
	•	Delays
	•	Risk count
	•	Performance score (auto-calculated)

⸻

🔍 Search System
	•	Live filtering of jobs
	•	Searches:
	•	Job ID
	•	Device
	•	Customer

⸻

📂 CSV Upload Engine
	•	Upload SIS export directly
	•	Automatically:
	•	Parses data
	•	Inserts/updates MySQL
	•	Refreshes dashboard
	•	Includes success feedback + auto refresh

⸻

📄 PDF Report Generator
	•	Generates downloadable job report
	•	Includes:
	•	Job details
	•	SLA status

⸻

📧 Email Report (Manual Trigger)
	•	Sends summary report to management
	•	Includes:
	•	totals
	•	performance insights

⸻

🧱 3. System Architecture

Backend
	•	Python (Flask)
	•	SLA engine (custom logic)

Database
	•	MySQL (jobs table)

Frontend
	•	HTML + CSS (custom UI)
	•	Chart.js (visualisation)

⸻

🔁 4. Data Flow
	1.	CSV uploaded
	2.	Parsed via Pandas
	3.	Stored in MySQL
	4.	Pulled into Flask
	5.	Processed via apply_sla()
	6.	Rendered in dashboard

⸻

🌐 5. Access
*******


⸻

▶️ 6. How to Run

From terminal:

********


Ensure:
	•	MySQL running
	•	Database sis_system exists
	•	Table jobs exists

⸻

⚠️ 7. Limitations (V1)
	•	Not publicly hosted (LAN only)
	•	No authentication/login
	•	Single-user optimized
	•	No historical tracking (snapshot only)
	•	Email is manual trigger only
	•	No push notifications

⸻

🏁 8. Version Status

✅ Stable
✅ Fully functional
✅ Mobile accessible
✅ Production usable (internal)
