"""Compiled from morning.fpp — DO NOT EDIT. Edit the .fpp instead."""

import schedule
import time
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


# -- my-clients --

def get_clients():
    creds = Credentials.from_authorized_user_file("token.json")
    service = build("people", "v1", credentials=creds)
    results = service.people().connections().list(
        resourceName="people/me",
        pageSize=1000,
        personFields="names,emailAddresses,memberships",
    ).execute()
    connections = results.get("connections", [])
    return [
        email["value"]
        for person in connections
        for email in person.get("emailAddresses", [])
        if any(
            g.get("contactGroupMembership", {}).get("contactGroupId") == "client"
            for g in person.get("memberships", [])
        )
    ]


# -- urgent-emails --

def get_urgent_emails():
    client_emails = get_clients()
    creds = Credentials.from_authorized_user_file("token.json")
    service = build("gmail", "v1", credentials=creds)

    cutoff = datetime.now() - timedelta(hours=48)
    query = f"is:unread after:{cutoff.strftime('%Y/%m/%d')}"

    results = service.users().messages().list(
        userId="me", q=query, maxResults=100
    ).execute()
    messages = results.get("messages", [])

    urgent = []
    for msg in messages:
        detail = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        sender = headers.get("From", "")
        if any(client in sender for client in client_emails):
            urgent.append({
                "from": sender,
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "summary": f"{sender.split('<')[0].strip()} — {headers.get('Subject', '')}",
            })

    return urgent


# -- morning-tasks --

def get_morning_tasks():
    import requests

    NOTION_DB = "abc123"
    headers = {
        "Authorization": "Bearer secret_xxx",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    cutoff = (datetime.now() + timedelta(hours=48)).isoformat()
    response = requests.post(
        f"https://api.notion.com/v1/databases/{NOTION_DB}/query",
        headers=headers,
        json={
            "filter": {
                "or": [
                    {"property": "Due", "date": {"on_or_before": cutoff}},
                    {"property": "Starred", "checkbox": {"equals": True}},
                ]
            },
            "sorts": [
                {"property": "Starred", "direction": "descending"},
                {"property": "Due", "direction": "ascending"},
            ],
        },
    )
    tasks = response.json().get("results", [])
    return [
        {
            "title": t["properties"]["Name"]["title"][0]["plain_text"],
            "due": t["properties"]["Due"]["date"]["start"] if t["properties"]["Due"]["date"] else "no date",
            "starred": t["properties"]["Starred"]["checkbox"],
        }
        for t in tasks
    ]


# -- morning-report --

def send_morning_report():
    emails = get_urgent_emails()
    tasks = get_morning_tasks()

    lines = ["*Morning Report*", ""]

    if emails:
        lines.append(f"*Urgent emails ({len(emails)}):*")
        for e in emails:
            lines.append(f"  • {e['summary']}")
        lines.append("")

    if tasks:
        lines.append(f"*Tasks ({len(tasks)}):*")
        for t in tasks:
            star = "⭐ " if t["starred"] else ""
            lines.append(f"  • {star}{t['title']} (due: {t['due']})")
        lines.append("")

    if not emails and not tasks:
        lines.append("Nothing urgent. Clear morning.")

    message = "\n".join(lines)

    import pywhatkit
    pywhatkit.sendwhatmsg_instantly("+51987654321", message, wait_time=10)


schedule.every().day.at("09:00").do(send_morning_report)

while True:
    schedule.run_pending()
    time.sleep(60)
