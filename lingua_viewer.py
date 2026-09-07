"""Lingua가 소유하는 학습 공간. 코어에는 학습 UI 지식을 추가하지 않는다."""
from functools import lru_cache
from pathlib import Path

from lingua_i18n import t

COPY = {
    "eyebrow": "YOUR CONVERSATION SPACE", "title": "A little practice. A wider world.",
    "intro": "Your words become a constellation. Keep a conversation going, then revisit what needs care.",
    "goal": "Learning goal", "empty_goal": "Choose your own goal in Settings",
    "ready": "Ready to practise", "active": "Practice session open", "session": "Session",
    "voice": "Use Cosmos chat or its voice controls to talk. This view does not indicate microphone status.",
    "chat": "Start a conversation", "scene": "Try a role-play", "review": "Practise review items",
    "finish": "Finish this session", "continue": "Continue in Cosmos chat",
    "saved": "Saved expressions", "due": "Ready for review", "graduated": "Review milestones",
    "map": "Your learning constellation", "legend": "Blue: collected · Amber: due · Mint: review milestone. One star per expression, up to 80. Not a fluency score.",
    "quiet": "Pause motion", "motion": "Enable motion", "flat": "2D view",
    "focus": "One expression to revisit", "empty": "Your first expressions will appear here after practice.",
    "answer": "Write or say a sentence before revealing the example.", "draft": "Try your own sentence…",
    "reveal": "Reveal & compare", "remembered": "I recalled it", "again": "I need practice",
    "self": "Self-check, not an automatic assessment. Compare your answer before recording it.",
    "queue_empty": "Nothing is due in this session. Practise to discover new expressions.",
    "recent": "Expressions from your practice", "example": "Example", "showing": "Showing the latest 8. Find more in Review and Report.",
    "saving": "Updating your learning…", "saved_notice": "Learning updated", "error": "Could not update. Your answer is kept. Please try again.",
    "refresh": "Refresh learning", "privacy": "Draft answers stay in this view until you close it. Only your self-check is saved.",
}


def review_token(item):
    return ':'.join(str(item.get(k, 0)) for k in ('hits', 'misses', 'box', 'due'))


@lru_cache(maxsize=1)
def html():
    return (Path(__file__).parent / 'views/learning.html').read_text(encoding='utf-8')


def block(data, due, ui, language_label):
    items = data['items']
    due_ids = {i['id'] for i in due}

    def card(i):
        return {"id": i['id'], "prompt": i.get('said') or i.get('meaning') or i.get('term', ''),
                "answer": i.get('correct') or i.get('term', ''), "note": i.get('note') or i.get('meaning', ''),
                "examples": i.get('examples', [])[:3], "token": review_token(i)}

    return {"type": "html", "key": "lingua-learning-v1", "label": t(ui, 'Your learning constellation'),
            "libraries": ['three'], "height": 1000, "html": html(), "state": {
                "copy": {key: t(ui, value) for key, value in COPY.items()},
                "language": data['language'], "language_label": language_label,
                "goal": data['goal'], "active": bool(data.get('active')), "session": data['session'],
                "total": len(items), "due": len(due),
                "graduated": sum(bool(i.get('graduated')) for i in items),
                "stars": [{"id": i['id'], "kind": 'graduated' if i.get('graduated') else
                           'due' if i['id'] in due_ids else 'saved'} for i in items[-80:]],
                "focus": card(due[0]) if due else None,
                "recent": [card(i) for i in reversed(items[-8:])],
            }}
