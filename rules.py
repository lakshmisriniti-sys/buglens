"""Demo mode: turn a messy bug report into a ticket using simple keyword rules.

Used when no API key is set, so anyone can try BugLens for free. It's much
less clever than the real AI: it only spots known words, it doesn't understand meaning.
"""
import re

from schemas import AITicket

# ---------- Environment: words we recognise, and how to write them nicely ----------
BROWSERS = {"chrome": "Chrome", "firefox": "Firefox", "safari": "Safari", "edge": "Edge", "opera": "Opera"}
SYSTEMS = {
    "windows": "Windows", "mac": "macOS", "macos": "macOS", "linux": "Linux",
    "android": "Android", "ios": "iOS", "iphone": "iPhone", "ipad": "iPad",
}

# ---------- Priority: checked in this order, first match wins ----------
PRIORITY_RULES = [
    ("critical", [
        r"payments?", r"\bpay\b", r"checkout", r"charged", r"billing", r"refund",
        r"security", r"\bhack", r"leak", r"data loss", r"lost (all|my)", r"deleted",
        r"(site|app|server) is down", r"nothing works", r"can'?t use (the|this) (app|site)",
    ]),
    ("high", [
        r"log ?in", r"sign ?in", r"logged out", r"kicked out", r"crash", r"freez",
        r"can'?t", r"cannot", r"doesn'?t work", r"not working", r"broken", r"\bfail", r"\berror",
    ]),
    ("low", [
        r"typo", r"spelling", r"colou?r", r"\bfont", r"align", r"looks (weird|odd|off|bad)",
        r"ugly", r"\bicon", r"dark mode", r"cosmetic", r"padding", r"spacing",
    ]),
]

# ---------- Feature areas ----------
# label: (name used in the title, a reproduction step, the expected result, trigger words)
AREAS = {
    "authentication": ("login", "Sign in to the app", "The user can sign in and stays signed in",
                       [r"log ?in", r"sign ?in", r"password", r"logged out", r"kicked out", r"session", r"\bauth"]),
    "payments": ("payment", "Go through checkout and pay", "The payment goes through once, for the correct amount",
                 [r"payments?", r"\bpay\b", r"checkout", r"\bcard\b", r"charged", r"billing", r"refund"]),
    "performance": ("slow performance", "Open the page or feature the user mentioned", "It loads and responds quickly",
                    [r"slow", r"\blag", r"loading", r"freez", r"\bhang", r"\bspin", r"timeout", r"takes forever"]),
    "crash": ("crash", "Use the feature the user mentioned", "The app keeps running without crashing",
              [r"crash", r"closes (itself|by itself)", r"shuts down"]),
    "content": ("typo / text", "Open the page the user mentioned", "The text is spelled and worded correctly",
                [r"typo", r"spelling", r"misspel", r"wording", r"grammar"]),
    "ui": ("display", "Look at the screen the user mentioned", "Everything displays correctly",
           [r"button", r"layout", r"align", r"colou?r", r"\bfont", r"dark mode", r"screen", r"\bicon", r"looks"]),
    "search": ("search", "Search for something", "Relevant results appear",
               [r"\bsearch"]),
    "notifications": ("notification", "Trigger the notification or email", "The notification arrives correctly",
                      [r"notification", r"\bemails?\b", r"alert"]),
    "uploads": ("file upload", "Upload a file", "The file uploads successfully",
                [r"upload", r"attach", r"\bfiles?\b"]),
    "data": ("saving data", "Save something, then reload the page", "Saved information is kept",
             [r"\bsav(e|ed|ing)\b", r"missing", r"disappear", r"\blost\b", r"deleted"]),
}

INTERMITTENT = [r"sometimes", r"randomly", r"occasionally", r"once in a while", r"now and then", r"intermittent"]


def _has(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text) for p in patterns)


def _first_sentence(text: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s+", text.strip())[0]
    sentence = " ".join(sentence.split())  # collapse extra spaces and line breaks
    if len(sentence) > 200:
        sentence = sentence[:197] + "…"
    return sentence[:1].upper() + sentence[1:]


def structure_with_rules(raw_report: str) -> AITicket:
    text = raw_report.lower()

    # Environment, e.g. "Chrome, Windows"
    found = [name for word, name in {**BROWSERS, **SYSTEMS}.items() if re.search(rf"\b{word}\b", text)]
    environment = ", ".join(dict.fromkeys(found))  # dict.fromkeys removes duplicates, keeps order

    # Priority: first matching rule, otherwise medium
    priority = next((level for level, patterns in PRIORITY_RULES if _has(text, patterns)), "medium")

    # Labels: feature areas, plus the browser if one was mentioned
    areas = [label for label, (*_, patterns) in AREAS.items() if _has(text, patterns)]
    browsers = [name.lower() for word, name in BROWSERS.items() if re.search(rf"\b{word}\b", text)]
    labels = (areas + browsers)[:5] or ["needs-triage"]

    # The main area is the first one found; it shapes the title, steps and expected result.
    main_area = AREAS[areas[0]] if areas else None

    # Title, e.g. "Intermittent login problem on Chrome"
    if main_area:
        title = f"{'Intermittent ' if _has(text, INTERMITTENT) else ''}{main_area[0]} problem"
        title = title[:1].upper() + title[1:]
        if environment:
            title += f" on {environment}"
    else:
        title = _first_sentence(raw_report)[:80]

    # Rules can't truly work out the steps, so these stay general on purpose.
    steps = [f"Open the app{f' on {environment}' if environment else ''}"]
    if main_area:
        steps.append(main_area[1])
    steps.append("Repeat what the user described in the original report")

    return AITicket(
        title=title,
        priority=priority,
        environment=environment,
        steps=steps,
        expected=main_area[2] if main_area else "The app works as expected",
        actual=_first_sentence(raw_report),
        labels=labels,
    )
