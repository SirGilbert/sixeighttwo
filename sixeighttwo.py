from flask import Flask, render_template, request, make_response
from flask import redirect, url_for
from psycopg2.extras import RealDictCursor
from datetime import datetime
import pandas as pd
import mysql.connector
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from io import BytesIO

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

# =========================
# 🧠 SLA RULES
# =========================
SLA_RULES = {
    "booked in": {"max_days": 1, "type": "active"},
    "being diagnosed": {"max_days": 2, "type": "active"},
    "awaiting customer": {"type": "waiting"},
    "awaiting replacement part": {"max_days": 12, "type": "parts"},
    "part received": {"max_days": 2, "type": "active"},
    "ready for collection": {"type": "done"},
    "completed": {"type": "done"},
    "delivered": {"type": "done"}
}

# =========================
# 🗄️ DB CONNECTION
# =========================
import os

import psycopg2

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

print("DB PASSWORD:", "Victoria_123.")

# =========================
# 🔧 SAFE CONVERSION HELPERS
# =========================
def to_int(v, default=0):
    try:
        return int(v)
    except:
        return default

def to_float(v, default=0.0):
    try:
        return float(v)
    except:
        return default

# =========================
# 🧠 SLA ENGINE
# =========================
def apply_sla(job):
    status = (job.get("status") or "").strip().lower()
    days = to_int(job.get("days_open"))

    rule = SLA_RULES.get(status, {"type": "unknown"})

    job["status_label"] = status.title()
    job["sla_flag"] = "OK"

    # =========================
    # ⏱ DAYS TO BREACH (NEW)
    # =========================
    job["days_to_breach"] = None
    job["warning_badge"] = None

    # =========================
    # CRITICAL BACKLOG
    # =========================
    if days > 90:
        job["sla_flag"] = "CRITICAL BACKLOG"

    # =========================
    # ACTIVE SLA LOGIC
    # =========================
    elif rule.get("type") == "active":
        max_days = rule.get("max_days", 0)

        # =========================
        # LIVE WARNING BADGES
        # =========================
        if max_days > 0:
            remaining = max_days - days
            job["days_to_breach"] = remaining

            if remaining < 0:
                job["warning_badge"] = "🔥 BREACHED"

            elif remaining == 0:
                job["warning_badge"] = "🔴 IMMINENT"

            elif remaining <= max(1, round(max_days * 0.25)):
                job["warning_badge"] = "🟠 WARNING"

            else:
                job["warning_badge"] = "🟢 SAFE"

        # =========================
        # ⏱ DAYS TO BREACH (CALC)
        # =========================
        

        # =========================
        # SLA BREACH (FINAL STATE FIRST)
        # =========================
        if max_days > 0 and days > max_days:
            job["sla_flag"] = "SLA BREACH"

        # =========================
        # AT RISK (75% WINDOW)
        # =========================
        elif max_days > 0 and days >= (max_days * 0.75):
            job["sla_flag"] = "AT RISK"
            
    # =========================
    # PARTS DELAY
    # =========================
    elif rule.get("type") == "parts":
        if days > rule.get("max_days", 12):
            job["sla_flag"] = "PARTS DELAY"

    # =========================
    # WAITING
    # =========================
    elif rule.get("type") == "waiting":
        if days > 30:
            job["sla_flag"] = "LONG WAIT"

    # =========================
    # COLOUR MAPPING
    # =========================
    if job["sla_flag"] == "SLA BREACH":
        job["color"] = "#7f1d1d"

    elif job["sla_flag"] in ["PARTS DELAY", "LONG WAIT"]:
        job["color"] = "#78350f"

    elif job["sla_flag"] == "CRITICAL BACKLOG":
        job["color"] = "#450a0a"

    elif job["sla_flag"] == "AT RISK":
        job["color"] = "#1e3a8a"

    else:
        job["color"] = "#14532d"

    return job

def send_email_report(subject, body):
    sender_email = "sibekominy@gmail.com"
    password = os.getenv("EMAIL_PASS")

    if not password:
        raise ValueError("EMAIL_PASS environment variable not set")

    recipients = [
        "janine@digicape.co.za",
        "markc@digicape.co.za"
    ]

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
        server.starttls()
        server.login(sender_email, password)
        print("Sending email to:", recipients)
        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()
        print("Email sent successfully")

    except Exception as e:
        print("Email failed:", e)

@app.route("/send-report")
def send_report():
    conn = get_db_connection()
    from psycopg2.extras import RealDictCursor
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT * FROM jobs")
    jobs = cursor.fetchall()

    cursor.close()
    conn.close()

    jobs = [apply_sla(job) for job in jobs]

    total = len(jobs)
    breaches = sum(1 for j in jobs if j["sla_flag"] == "SLA BREACH")
    delays = sum(1 for j in jobs if j["sla_flag"] in ["PARTS DELAY", "LONG WAIT"])
    healthy = sum(1 for j in jobs if j["sla_flag"] == "OK")

    avg_days = sum(to_int(j.get("days_open")) for j in jobs) / total if total else 0

    # Technician summary
    from collections import defaultdict

    tech_summary = defaultdict(lambda: {"total": 0, "breach": 0})

    for job in jobs:
        tech = job.get("technician") or "Unassigned"
        tech_summary[tech]["total"] += 1

        if job["sla_flag"] == "SLA BREACH":
            tech_summary[tech]["breach"] += 1

        # 🚨 TOP CRITICAL JOBS (limit 5)
        critical_jobs = [
            j for j in jobs if j["sla_flag"] in ["SLA BREACH", "CRITICAL BACKLOG"]
        ]

        critical_jobs = sorted(
            critical_jobs,
            key=lambda x: to_int(x.get("days_open")),
            reverse=True
        )[:5]

        critical_text = ""
        for job in critical_jobs:
            critical_text += f"- Job {job['job_id']} | {job.get('device')} | {job.get('technician')} | {job.get('days_open')} days\n"

    tech_text = ""
    for tech, data in tech_summary.items():
        tech_text += f"- {tech}: {data['total']} jobs, {data['breach']} breaches\n"

    # FINAL EMAIL BODY
    body = f"""
SixEightTwo Weekly Technician Report
Date: {datetime.now().strftime('%Y-%m-%d')}

----------------------------------------
SUMMARY
----------------------------------------
Total Jobs: {total}
Healthy: {healthy}
SLA Breaches: {breaches}
Delays: {delays}
Average Days Open: {round(avg_days, 2)}

----------------------------------------
TECHNICIAN PERFORMANCE
----------------------------------------
{tech_text}

----------------------------------------
KEY INSIGHTS
----------------------------------------
- High SLA breaches indicate workflow pressure
- Delays largely tied to parts / waiting states
- Focus required on backlog reduction

----------------------------------------
SYSTEM NOTE
----------------------------------------
Auto-generated by SixEightTwo
"""

    send_email_report("SixEightTwo Weekly Report", body)

    return "Report sent successfully!"

# =========================
# 🏠 DASHBOARD
# =========================
@app.route("/")
def dashboard():
    conn = get_db_connection()
    from psycopg2.extras import RealDictCursor
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("SELECT * FROM jobs")
        jobs = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    jobs = [apply_sla(job) for job in jobs]

    from collections import defaultdict

    tech_stats = defaultdict(lambda: {
        "total": 0,
        "breach": 0,
        "delays": 0,
        "risk": 0,
        "days_total": 0
    })

    for job in jobs:
        tech = job.get("technician") or "Unassigned"
        days = to_int(job.get("days_open"))
        flag = job.get("sla_flag")

        tech_stats[tech]["total"] += 1
        tech_stats[tech]["days_total"] += days

        if flag == "AT RISK":
            tech_stats[tech]["risk"] += 1

        if flag == "SLA BREACH":
            tech_stats[tech]["breach"] += 1

        if flag in ["PARTS DELAY", "LONG WAIT"]:
            tech_stats[tech]["delays"] += 1

    tech_report = []

    for tech, data in tech_stats.items():
        total = data["total"]
        avg_days = data["days_total"] / total if total else 0

        score = 100
        score -= data["breach"] * 25
        score -= data["risk"] * 10
        score -= data["delays"] * 8
        score -= avg_days * 0.5
        score = max(score, 0)

        tech_report.append({
            "technician": tech,
            "total": total,
            "breach": data["breach"],
            "risk": data["risk"],
            "delays": data["delays"],
            "avg_days": round(avg_days, 1),
            "score": round(score, 1)
        })

    tech_report.sort(key=lambda x: x["score"], reverse=True)

    urgent_jobs = []
    attention_jobs = []
    normal_jobs = []

    at_risk_jobs = [j for j in jobs if j["sla_flag"] == "AT RISK"]

    for job in jobs:
        days = to_int(job.get("days_open"))
        sla = job.get("sla_flag")

        if sla in ["SLA BREACH", "CRITICAL BACKLOG"]:
            urgent_jobs.append(job)
        elif sla in ["PARTS DELAY", "LONG WAIT"] or days >= 2:
            attention_jobs.append(job)
        else:
            normal_jobs.append(job)

    chart_data = {
        "ok": sum(1 for j in jobs if j["sla_flag"] == "OK"),
        "risk": sum(1 for j in jobs if j["sla_flag"] == "AT RISK"),
        "breach": sum(1 for j in jobs if j["sla_flag"] == "SLA BREACH"),
        "delay": sum(1 for j in jobs if j["sla_flag"] in ["PARTS DELAY", "LONG WAIT"])
    }

    # Technician chart data
    tech_names = [t["technician"] for t in tech_report] if tech_report else []
    tech_scores = [t["score"] for t in tech_report] if tech_report else []

    # =========================
    # ⚠️ AT RISK JOBS PANEL DATA
    # =========================
    at_risk_jobs = sorted(
        [j for j in jobs if j["sla_flag"] == "AT RISK"],
        key=lambda x: to_int(x.get("days_open")),
        reverse=True
    )

    filter_type = request.args.get("filter", "all")

    if filter_type == "breach":
        jobs = [j for j in jobs if j["sla_flag"] == "SLA BREACH"]
    elif filter_type == "delay":
        jobs = [j for j in jobs if j["sla_flag"] in ["PARTS DELAY", "LONG WAIT"]]
    elif filter_type == "ok":
        jobs = [j for j in jobs if j["sla_flag"] == "OK"]

    return render_template(
        "dashboard.html",
        jobs=jobs,
        tech_report=tech_report,
        chart_data=chart_data,
        urgent_jobs=urgent_jobs,
        attention_jobs=attention_jobs,
        normal_jobs=normal_jobs,
        at_risk_jobs=at_risk_jobs,
        tech_names=tech_names,
        tech_scores=tech_scores
    )

# =========================
# 📤 CSV UPLOAD
# =========================
@app.route("/upload-csv", methods=["POST"])
def upload_csv():
    file = request.files.get("file")

    if not file:
        return "No file uploaded", 400

    df = pd.read_csv(file)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        for _, row in df.iterrows():
            job_id = to_int(row.get("Order"))
            device = row.get("Device")
            serial_number = row.get("Serial number")
            customer = row.get("Customer")
            status = (row.get("Status") or "").strip().lower()

            sub_status = row.get("Sub status") if pd.notna(row.get("Sub status")) else None
            days_open = to_int(row.get("In service"))
            location = row.get("Internal location") if pd.notna(row.get("Internal location")) else None
            amount_due = to_float(row.get("Still to be paid"))
            technician = row.get("Handler") if pd.notna(row.get("Handler")) else None

            cursor.execute("""
                INSERT INTO jobs (
                    job_id, device, serial_number, customer,
                    status, sub_status, days_open,
                    location, amount_due, technician
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    device = VALUES(device),
                    serial_number = VALUES(serial_number),
                    customer = VALUES(customer),
                    status = VALUES(status),
                    sub_status = VALUES(sub_status),
                    days_open = VALUES(days_open),
                    location = VALUES(location),
                    amount_due = VALUES(amount_due),
                    technician = VALUES(technician)
            """, (
                job_id, device, serial_number, customer,
                status, sub_status, days_open,
                location, amount_due, technician
            ))

        conn.commit()
    finally:
        cursor.close()
        conn.close()

    from flask import redirect, url_for

    return redirect(url_for("dashboard", uploaded="true"))

# =========================
# 📊 WEEKLY REPORT
# =========================
@app.route("/weekly-report")
def weekly_report():
    conn = get_db_connection()
    from psycopg2.extras import RealDictCursor
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute("SELECT * FROM jobs")
        jobs = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    jobs = [apply_sla(job) for job in jobs]

    total = len(jobs)
    breaches = sum(1 for j in jobs if j["sla_flag"] == "SLA BREACH")
    delays = sum(1 for j in jobs if j["sla_flag"] in ["PARTS DELAY", "LONG WAIT"])
    healthy = total - breaches - delays
    avg_days = round(sum(to_int(j.get("days_open")) for j in jobs) / total, 2) if total else 0

    from collections import defaultdict

    tech_summary = defaultdict(lambda: {"total": 0, "breach": 0, "delay": 0})

    for job in jobs:
        tech = job.get("technician") or "Unassigned"
        flag = job.get("sla_flag")

        tech_summary[tech]["total"] += 1
        if flag == "SLA BREACH":
            tech_summary[tech]["breach"] += 1
        if flag in ["PARTS DELAY", "LONG WAIT"]:
            tech_summary[tech]["delay"] += 1

    return render_template(
        "weekly_report.html",
        jobs=jobs,
        total=total,
        breaches=breaches,
        delays=delays,
        healthy=healthy,
        avg_days=avg_days,
        today=datetime.now(),
        tech_summary=tech_summary
    )

# =========================
# 📄 PDF REPORT
# =========================
@app.route("/weekly-report/pdf")
def weekly_report_pdf():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM jobs")
        jobs = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    jobs = [apply_sla(job) for job in jobs]

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    elements = []
    elements.append(Paragraph("SixEightTwo Weekly Report", styles["Title"]))
    elements.append(Spacer(1, 12))

    for job in jobs:
        text = f"""
        Job ID: {job['job_id']}<br/>
        Client: {job.get('customer', 'N/A')}<br/>
        Device: {job.get('device', 'N/A')}<br/>
        Technician: {job.get('technician', 'N/A')}<br/>
        Status: {job.get('status', 'N/A')}<br/>
        Days Open: {job.get('days_open', 0)}<br/>
        SLA: {job.get('sla_flag', 'OK')}
        """
        elements.append(Paragraph(text, styles["Normal"]))
        elements.append(Spacer(1, 10))

    doc.build(elements)

    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=report.pdf"

    return response

# =========================
# 🚀 RUN APP
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
