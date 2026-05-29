"""
app/ai/analyzer.py  –  Email intelligence via Groq GPT-OSS-120B
"""
import json
import logging
from groq import Groq
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_groq = Groq(api_key=settings.groq_api_key)

SYSTEM_PROMPT = """You are an intelligent email classifier for a personal AI assistant.

Analyze incoming emails and determine their importance and urgency.

ALWAYS return a valid JSON object only. No explanation. No markdown. Raw JSON only.

IMPORTANT (score 60-100):
- Interview invitations, recruiter messages, job offers, internship opportunities
- College/university announcements, placement notifications, exam results
- Security alerts, OTP emails, password reset emails
- Client communications, invoices, payment confirmations, banking alerts
- Urgent requests, deadline reminders, government/legal notices

NOT IMPORTANT (score 0-30):
- Promotions, shopping offers, discount codes, newsletters
- Marketing campaigns, advertisements, social media updates
- Spam, mass marketing, subscription confirmations

Return exactly this JSON:
{
  "importance_score": <0-100>,
  "urgency": "<LOW|MEDIUM|HIGH|CRITICAL>",
  "category": "<Interview|OTP|Payment|Placement|Security|Academic|Recruiter|Banking|Deadline|General>",
  "summary": "<2-3 sentence summary>",
  "action_required": <true|false>,
  "reason": "<why important or not>",
  "deadline_detected": <true|false>,
  "deadline": "<deadline string or null>"
}"""


def analyze_email(subject: str, sender: str, sender_name: str, body: str) -> dict:
    body_snippet = body[:3000] if body else "(no body)"

    prompt = f"""Analyze this email:

From: {sender_name} <{sender}>
Subject: {subject}
Body:
{body_snippet}"""

    try:
        resp = _groq.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content.strip()
        result = json.loads(content)
        logger.info(
            f"AI: score={result.get('importance_score')} "
            f"urgency={result.get('urgency')} "
            f"subject='{subject[:60]}'"
        )
        return result
    except json.JSONDecodeError as e:
        logger.error(f"AI JSON parse error: {e}")
        return _default()
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        return _default()


def _default() -> dict:
    return {
        "importance_score": 0,
        "urgency": "LOW",
        "category": "Unknown",
        "summary": "Could not analyze email.",
        "action_required": False,
        "reason": "AI analysis failed.",
        "deadline_detected": False,
        "deadline": None,
    }


def is_important(analysis: dict, threshold: int = 55) -> bool:
    score = analysis.get("importance_score", 0)
    urgency = analysis.get("urgency", "LOW")
    return score >= threshold or urgency in {"HIGH", "CRITICAL"}
