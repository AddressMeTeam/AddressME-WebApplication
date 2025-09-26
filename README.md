# 🏠 AddressMe-WebApp

**AddressMe** is a civic technology web application that provides **digital, verifiable addresses** for residents of informal settlements. By combining mapping tools, community-led verification workflows, and secure data handling, AddressMe helps unlock access to emergency services, deliveries, and formal documentation for underserved communities.

---

## 🌍 Features

- **Resident Registration**: Simple onboarding flow for residents to request an address.
- **Geolocation Mapping**: Interactive map widget to tag precise locations.
- **Community Verification**: Local leaders and police validate address requests through structured workflows.
- **Status Tracking**: Real-time updates on address verification status.
- **Secure Architecture**: Built with Flask/Django, PostgreSQL, and AWS services for scalability and resilience.

---

## 🛠️ Tech Stack

| Layer        | Technology                      |
|--------------|----------------------------------|
| Frontend     | HTML, Tailwind CSS, JavaScript   |
| Backend      | Python (Flask or Django)         |
| Mapping      | Leaflet.js + OpenStreetMap       |
| Database     | PostgreSQL (via AWS RDS)         |
| Cloud        | AWS EC2, S3, Secrets Manager     |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL
- AWS CLI (configured)
- Git

### Installation

```bash
git clone https://github.com/AddressMeTeam/AddressME-WebApplication.git
cd AddressME-WebApplication
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
