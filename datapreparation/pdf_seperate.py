import json
import os


PDF_INFO_JSON_PATH = os.path.join("data", "announcements_metadata-last-year.json")
os.makedirs(os.path.join("data", "processed"), exist_ok=True)

GROUP_A = {
    "Acquisition",
    "Action(s) taken or orders passed",
    "Agreements",
    "Buyback",
    "Change in Director(s)",
    "Dividend",
    "Financial Result Updates",
    "Integrated Filing- Financial",
    "News Verification",
    "Outcome of Board Meeting",
    "Pendency of Litigation(s)/dispute(s) or the outcome impacting the Company",
    "Post Buyback Public Announcement",
    "Press Release",
    "Public Announcement - Buyback of Shares",
    "Rumour Verification - Regulation 30(11)"
}

GROUP_C = {
    "Allotment of Securities",
    "Certificate under SEBI (Depositories and Participants) Regulations, 2018",
    "Clarification - Financial Results",
    "Copy of Newspaper Publication",
    "Disclosure under SEBI Takeover Regulations",
    "ESOP/ESOS/ESPS",
    "Loss of Share Certificates",
    "Record Date",
    "Reply to Clarification- Financial results",
    "Trading Window"
}

GOOD = [
    "earnings call transcript",
    "transcript",
    "investor presentation",
    "acquisition",
    "partnership",
    "collaboration",
    "ai",
    "ceo",
    "director",
    "brsr",
    "form 20-f",
    "press release"
]

BAD = [
    "schedule of meet",
    "investor conference",
    "notice of agm",
    "voting results",
    "scrutinizer report",
    "proceedings"
]

with open(PDF_INFO_JSON_PATH, "r") as f:
    filings = json.load(f)

keep = []
reject = []
review = []

for filing in filings:
    desc = filing["desc"]
    text = filing["attchmntText"].lower()

    if desc in GROUP_A:
        keep.append(filing)
        continue

    if desc in GROUP_C:
        reject.append(filing)
        continue

    if desc in {"Updates","General Updates","Shareholders meeting",
                "Analysts/Institutional Investor Meet/Con. Call Updates"}:

        if any(word in text for word in GOOD):
            keep.append(filing)

        elif any(word in text for word in BAD):
            reject.append(filing)

        else:
            review.append(filing)

        continue

    review.append(filing)

print(f"Keep: {len(keep)}")
print(f"Reject: {len(reject)}")
print(f"Review: {len(review)}")

with open(os.path.join("data", "processed", "keep.json"), "w") as f:
    json.dump(keep, f, indent=2)

with open(os.path.join("data", "processed", "reject.json"), "w") as f:
    json.dump(reject, f, indent=2)

with open(os.path.join("data", "processed", "review.json"), "w") as f:
    json.dump(review, f, indent=2)