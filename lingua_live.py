"""Lingua Live — 실시간 음성 언어 학습 에이전트 (cosmos 마켓 에이전트).

이 파일은 **교육 철학의 구현체**다. 설정 하나하나가 취향이 아니라 원칙에서 나온다.
철학과 근거는 README.md에, 여기서는 그 규칙을 코드로 고정한다.

  ① 말이 멈추면 학습도 멈춘다 → 기본 교정은 대화를 끊지 않는다(recast/화면 카드)
  ② 한 걸음 위(i+1)        → 레벨은 고정값이 아니라 성공률로 움직인다
  ③ 밀어붙인 산출          → 이해했으면 '다시 말해보기'를 요구한다
  ④ 모두 고치지 않는다      → 반복되는 오류만 승격, 한 세션 최대 3개
  ⑤ 잊기 전에 다시 만난다   → 교정은 그 자리에서 끝나지 않고 복습 큐로 간다(간격 반복)
  ⑥ 시험을 보지 않고 시험한다 → 대화 안에 난이도를 심어(probe) 실시간으로 수준을 재고,
                              그 자리에서 말하는 수준을 맞춘다. 세션이 끝나면 전체를
                              분석해 **무엇을 보충할지** 처방한다(축별 약점 → 다음 모드)
  ⑦ 교정이 대화를 멈추게 하지 않는다 → 교정은 **백그라운드에서** 이뤄지고 화면으로만
                              간다. 말은 끊기지 않는다(v0.2.0)

v0.2.0에서 바뀐 것(실사용 피드백 2026-07-28: "끊어서 듣는다 · 텀이 너무 길다"):
튜터가 교정을 **툴 호출로** 하면 모델이 그 호출을 다 생성할 때까지 침묵한다 —
한 턴에 생성 왕복이 두 번 일어나고, 교정이 꼼꼼할수록 대화가 끊긴다. 자기모순이다.
그래서 교정을 대화 경로에서 들어냈다: 모델은 **그냥 대화만 하고**, 교정은
`observe_turn`(논블로킹 백그라운드 훅)에서 별도 LLM이 처리해 화면에 카드로 쌓는다.

의존성은 cosmos.contracts와 표준 라이브러리뿐이다.
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid

from cosmos.contracts import Plugin, ToolContext

from lingua_i18n import t as _t          # 화면 어휘의 번역(영어 원문 → 사용자 언어)

_LOCK = threading.RLock()          # 백그라운드 분석과 뷰가 같은 파일을 만진다
MIN_ANALYZE_CHARS = 12             # "Hey." 같은 한 마디는 분석하지 않는다(비용·소음)
MAX_CORRECTIONS_PER_TURN = 2       # 한 턴에 두 개까지 — 더 주면 아무것도 안 남는다

# 백그라운드 분석가에게 주는 지시. 튜터(대화하는 모델)와 **다른 역할**이다:
# 이쪽은 말하지 않고 오직 읽고 판단만 한다. 그래서 대화 지연이 0이다.
ANALYST_SYSTEM = """You are the silent analyst behind a live language tutor.
You never speak to the learner. You read one utterance and decide what — if anything —
is worth teaching. Be strict: most utterances need nothing.

Return STRICT JSON only, no prose, no code fence:
{"corrections":[{"wrong":"<what they said>","right":"<full natural corrected sentence>",
                 "note":"<one line in the learner's own language: why>",
                 "kind":"grammar|vocab|pronunciation|register|fluency",
                 "tag":"<2-4 word label of the pattern>"}],
 "words":[{"term":"","reading":"","meaning":"<learner's language>","examples":["",""]}],
 "level_fit":"below|at|above",
 "coach":"<at most ONE short English instruction for the live tutor's NEXT reply, or \"\">"}

Rules:
- At most 2 corrections, and only for errors that a teacher would actually bring up.
  Natural-but-imperfect speech is fine. Do not correct style unless it blocks meaning.
- This is a SPEECH transcript: words may be split ("con ver sation"), merged, or cut off
  mid-word. Those are microphone artifacts, NOT learner errors — ignore them completely.
- "right" must be the whole sentence rewritten naturally at the learner's level,
  not a fragment.
- "words": at most 1, only when the learner clearly lacked a word or used a notable one.
- "level_fit": was this utterance below / at / above the learner's stated level?
- "coach": the tutor is ALREADY talking and must not be interrupted. Give at most one
  short instruction it can fold into its next sentence, e.g.
  "Recast their sentence using 'we rarely have', then ask a follow-up." or
  "They handled a B2 structure — raise your level." Leave it empty most of the time;
  a tutor that is coached every turn stops sounding like a person.
- If nothing is worth teaching, return
  {"corrections":[],"words":[],"level_fit":"at","coach":""}."""

# ── 어휘: 전부 단일 진실원. 새 언어·모드·상황은 여기 한 줄이면 UI까지 자동 반영된다 ──
#
# ★사람이 읽는 값은 **영어가 원문**이다★(v0.5.0) 화면에 나갈 때 `lingua_i18n.t()`가
# 사용자 언어로 옮긴다. v0.4.0까지 이 표들은 한국어로 박혀 있었고, 그래서 한국어를
# 읽지 못하는 사용자는 설치해도 쓸 수 없었다. 새 언어를 더하려면 **코드가 아니라
# 번역 표**만 늘리면 된다(원칙 1).
#
# ★두 언어를 섞지 마라★(함정 28) `LANGUAGES`의 **키**는 배우는 언어이고,
# 사용자가 화면을 읽는 언어는 `ctx.lang`이다. `label`은 배우는 언어의 **이름**이라
# 번역 대상이고(한국어 사용자에게 "Spanish"는 "스페인어"), `native`는 그 언어가
# 자기를 부르는 이름이라 **어느 화면에서도 그대로**다.
LANGUAGES: dict[str, dict] = {
    "en": {"label": "English",    "native": "English",   "locale": "en-US"},
    "es": {"label": "Spanish",    "native": "Español",   "locale": "es-ES"},
    "ja": {"label": "Japanese",   "native": "日本語",     "locale": "ja-JP"},
    "zh": {"label": "Chinese",    "native": "中文",       "locale": "zh-CN"},
    "de": {"label": "German",     "native": "Deutsch",   "locale": "de-DE"},
    "fr": {"label": "French",     "native": "Français",  "locale": "fr-FR"},
    "ko": {"label": "Korean",     "native": "한국어",     "locale": "ko-KR"},
    "ar": {"label": "Arabic",     "native": "العربية",   "locale": "ar-SA", "rtl": True},
    "it": {"label": "Italian",    "native": "Italiano",  "locale": "it-IT"},
    "pt": {"label": "Portuguese", "native": "Português", "locale": "pt-BR"},
    "ru": {"label": "Russian",    "native": "Русский",   "locale": "ru-RU"},
}

LEVELS: dict[str, str] = {
    "A1": "Survival — greetings, ordering, directions",
    "A2": "Everyday talk — say how your day went in short sentences",
    "B1": "Opinions — explain with reasons",
    "B2": "Discussion — handle abstract topics",
    "C1": "Precision — nuance, idiom and register",
}

MODES: dict[str, dict] = {
    "chat":   {"label": "Free talk",
               "desc": "Talk about whatever interests you — how much you say is the point"},
    "scene":  {"label": "Scenes",
               "desc": "Rehearse a real situation as role-play"},
    "drill":  {"label": "Drills",
               "desc": "Only the things you keep getting wrong"},
    "review": {"label": "Review",
               "desc": "Review queue only — meet it again just before you forget"},
    "shadow": {"label": "Shadowing",
               "desc": "Listen and say it back exactly — pronunciation and rhythm"},
}

SCENES: dict[str, str] = {
    "airport":    "Airport — check-in, transfers, baggage",
    "restaurant": "Restaurant — ordering, requests, paying",
    "hotel":      "Hotel — check-in, requests, problems",
    "shopping":   "Shopping — prices, exchanges, refunds",
    "hospital":   "Clinic — describing symptoms, prescriptions",
    "interview":  "Interview — introducing yourself, experience, questions",
    "meeting":    "Meeting — opinions, disagreement, wrapping up",
    "phone":      "Phone — talking to someone you cannot see",
    "smalltalk":  "Small talk — weather, the weekend, catching up",
    "directions": "Directions — asking and understanding the answer",
}

# 교정 정책 — **이 에이전트에서 가장 중요한 설정 하나**.
# 교정을 언제 어떻게 주느냐가 학습 곡선을 바꾼다(README §철학 ①).
#
# ★`instruction`은 번역하지 않는다★ 그것은 **모델이 읽는 글**이고, 모델은 그것을
# 읽은 뒤 **사용자의 언어로 말한다**. 지침까지 옮기면 번역 품질이 곧 교습 품질이
# 되어 언어마다 튜터가 달라진다.
POLICIES: dict[str, dict] = {
    "flow": {
        "label": "Flow first",
        "desc": "Never interrupts you. Corrections appear only as cards on screen — "
                "for when confidence has to come first",
        "instruction": "NEVER interrupt to correct. Do not mention mistakes aloud. "
                       "Log them silently with note_error and keep the conversation moving. "
                       "Praise attempts, not accuracy.",
    },
    "recast": {
        "label": "Recast (default)",
        "desc": "Says your idea back in the correct form — the conversation never stops",
        "instruction": "Do not stop the conversation. When the learner makes a mistake, "
                       "reply naturally but REPEAT their idea back using the correct form "
                       "(a recast), then continue. Log it with note_error. "
                       "Never lecture mid-flow.",
    },
    "focus": {
        "label": "Correct now",
        "desc": "Stops at important errors and has you say it again — "
                "for exams and advanced learners",
        "instruction": "When a mistake blocks meaning or repeats a known error, stop the "
                       "flow: name the error briefly, give the correct form, and ask the "
                       "learner to say the whole sentence again (pushed output). "
                       "Then resume. Max 3 interruptions per session.",
    },
}

ERROR_KINDS: dict[str, str] = {
    "grammar": "Grammar", "vocab": "Vocabulary", "pronunciation": "Pronunciation",
    "register": "Register", "fluency": "Fluency",
}

# 약점 축 → **다음에 무엇을 할지**. 처방이 철학에서 나온다는 것이 여기서 드러난다:
# 유창성이 약하면 교정을 더 하는 게 아니라 **덜 한다**(말이 멈추면 학습도 멈추므로).
PRESCRIPTIONS: dict[str, dict] = {
    "grammar": {"mode": "drill", "policy": None,
                "say": "Grammar errors dominate — the next session drills the same "
                       "structures across different situations."},
    "vocab": {"mode": "scene", "policy": None,
              "say": "Vocabulary is the bottleneck — moving to scenes so you actually "
                     "use the words you need."},
    "pronunciation": {"mode": "shadow", "policy": None,
                      "say": "Pronunciation and rhythm are weak — more shadowing: "
                             "listen, then say it back."},
    "register": {"mode": "scene", "policy": "focus",
                 "say": "Register slips — interviews and meetings with immediate "
                        "correction will fix it."},
    "fluency": {"mode": "chat", "policy": "flow",
                "say": "You stall often — lowering correction to get your speaking "
                       "volume back first."},
}

PROBE_EVERY_TURNS = 6        # 몇 턴마다 난이도를 하나 심을지(대화를 시험처럼 만들지 않는 간격)
PROBE_UP = 0.8               # 이 이상 통과하면 한 단계 위로
PROBE_DOWN = 0.4             # 이 이하면 한 단계 아래로

# 간격 반복(세션 단위). 짧게 시작해 점점 벌린다 — 잊기 직전에 다시 만나는 게 목적이다.
SRS_INTERVALS = (1, 3, 7, 16, 35)
MAX_FOCUS_ITEMS = 3          # 한 세션에 다루는 교정 항목 상한(철학 ④)
PROMOTE_AFTER = 2            # 같은 오류가 이만큼 반복되면 복습 큐로 승격

# ★이 채널이 만든 것은 채널 단위로 걷어낼 수 있다★(모든 자동 산출물의 규칙).
# 이 에이전트를 떼면 남긴 기억도 함께 거둘 수 있어야 *"붙이고 떼기 쉽다"* 가 참이 된다.
CHANNEL = "lingua.v1"


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


# ── ★내밀 것을 정하는 판정 — 순수 함수★ (v0.5.0) ─────────────────────────────
#
# 세상을 안 만지므로 그물이 **모든 갈래를 실제로 지나간다**. 네트워크나 디스크 호출
# 안에 묻어 두면 낱말만 남기고 동작을 뒤집는 뮤테이션이 그대로 빠져나간다.
#
# ⚠️ ★"지금 꺼내도 되는가"는 여기서 묻지 않는다★ 그것은 코스모스가 자세·잡담·침묵·
# 물린 횟수를 보고 정한다(`contracts/collab.may_offer`). 여기는 *"내밀 것이 있는가"* 만.

# 며칠 쉬면 이어가자고 할 만한가. 하루는 짧다(그날 안 했다고 재촉하는 것은 잔소리다).
IDLE_DAYS_BEFORE_OFFER = 3
# 복습이 이만큼 밀려 있으면 날짜와 무관하게 내민다 — 잊기 직전이 이 에이전트의 요점이다.
DUE_CARDS_BEFORE_OFFER = 5


def offer_reason(*, due_cards: int, days_idle: float,
                 weakest: str = "") -> dict | None:
    """무엇을 이어가자고 할 것인가. ★내밀 것이 없으면 None★.

    돌려주는 것은 코스모스가 읽을 **재료**이지 완성된 문장이 아니다 — 말은 사용자의
    언어로 코스모스가 만든다(에이전트가 문장을 박으면 한 언어에 묶인다).
    """
    due = max(0, int(due_cards or 0))
    idle = max(0.0, float(days_idle or 0))
    if due >= DUE_CARDS_BEFORE_OFFER:
        # 밀린 복습이 우선이다 — 이것은 **잊는 중인 것**이라 시간이 값을 깎는다.
        return {"kind": "review", "due": due, "weakest": weakest,
                "weight": min(0.9, 0.5 + due / 40.0)}
    if idle >= IDLE_DAYS_BEFORE_OFFER:
        return {"kind": "resume", "due": due, "days": round(idle),
                "weakest": weakest, "weight": 0.5}
    return None


def split_example(raw) -> dict:
    """예문 하나를 ★원문과 번역★으로 가른다 (v0.5.1).

    ⚠️ ★계약에 칸이 있는데 아무도 안 채우고 있었다★ — 화면 계약은 예문을
    `{text, translation}`으로 받는데 여기서 `translation: ""`을 **고정으로** 넣었고,
    도구 스키마도 예문을 **문자열 배열**로만 받아 모델이 번역을 줄 자리가 없었다.
    그래서 B1 학습자가 `La semana pasada fuimos a Sevilla.` 만 받는다 — 예문의 절반이다.
    (이 저장소가 "표에 있는데 아무도 안 채우면 있는 줄 알고 배선한다"고 부르는 그것이다.)

    ★옛 모양도 그대로 받는다★ 이미 쌓인 카드가 문자열이고, 갑자기 안 보이면 그것은
    개선이 아니라 고장이다.

      "Ayer comí paella."                     → 번역 없음(그대로 보인다)
      "Ayer comí paella. | 어제 파에야를 먹었다"  → 나란히 보인다
      {"text": …, "translation": …}            → 그대로
    """
    if isinstance(raw, dict):
        return {"text": str(raw.get("text") or "").strip(),
                "translation": str(raw.get("translation") or "").strip()}
    text = str(raw or "").strip()
    if "|" in text:
        left, _, right = text.partition("|")
        return {"text": left.strip(), "translation": right.strip()}
    return {"text": text, "translation": ""}


# ── ★무엇을 먼저 보여 주는가 — 학습의 우선순위★ (v0.5.1) ────────────────────
#
# 지금은 **최신순**(`reversed`)이다. 그것은 *"방금 뭐라 했지"* 에는 맞지만 학습에는
# 맞지 않는다 — 학습자가 화면을 여는 이유는 ★**무엇이 아직 안 붙었나**★를 보려는 것이다.
#
# 두 가지가 그것을 말한다:
#   · 여러 번 틀렸다(`seen`·`misses`)  — 아직 안 붙은 것
#   · 곧 잊는다(`box`가 낮다)          — 지금 만나야 하는 것
#
# ★순수 함수라야 그물이 잡는다★ — 정렬을 뷰 안에 묻어 두면 낱말만 남기는 뮤테이션이
# 그대로 빠져나간다(29차 교훈).
def learning_weight(item: dict) -> float:
    """클수록 먼저 보여 준다. 0~1."""
    misses = max(0, int(item.get("misses") or 0))
    seen = max(1, int(item.get("seen") or 1))
    box = max(1, int(item.get("box") or 1))
    stuck = min(1.0, (misses + (seen - 1) * 0.5) / 4.0)   # 자꾸 걸린다
    fresh = 1.0 - (box - 1) / max(1, len(SRS_INTERVALS) - 1)   # 아직 안 굳었다
    return round(min(1.0, 0.6 * stuck + 0.4 * fresh), 4)


def by_learning_need(items: list[dict]) -> list[dict]:
    """★안 붙은 것이 위로★ — 같으면 최신이 위(정렬이 매번 같아야 그물이 잡는다)."""
    rows = list(items or [])
    return sorted(rows, key=lambda i: (-learning_weight(i),
                                       -rows.index(i)))


def days_between(then: str, now_ts: float, *, parse=None) -> float:
    """마지막 학습으로부터 며칠. 읽을 수 없는 값은 **0일로 본다**.

    ★모르면 재촉하지 않는 쪽으로 떨어진다★ — 기록이 깨졌다고 매번 이어가자고 하면
    그 고장이 잔소리로 나타난다.
    """
    raw = str(then or "").strip()
    if not raw:
        return 0.0
    reader = parse or (lambda s: time.mktime(time.strptime(s, "%Y-%m-%d %H:%M")))
    try:
        return max(0.0, (float(now_ts) - reader(raw)) / 86400.0)
    except Exception:
        return 0.0


class LinguaLive(Plugin):
    name = "lingua"
    version = "0.5.2"
    description = (
        "Real-time language tutor. Call action=start ONCE at the beginning of a language-"
        "practice conversation to load the learner's profile and the teaching rules you "
        "must follow. Then just TALK — do not call this tool again while conversing. "
        "Corrections, vocabulary and level measurement happen automatically in the "
        "background and appear on the learner's screen. Call action=finish when the "
        "learner wants to stop, or action=set if they ask to change language/level/mode. "
        "Supports English, Spanish, Japanese, Chinese, German, French, Korean, Arabic."
    )
    parameters = {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING",
                       "description": "start | note_error | note_word | review_answer | "
                                      "set | status | finish"},
            "language": {"type": "STRING", "description": "Target language code: en, es, ja, zh, de, fr, ko, ar"},
            "level": {"type": "STRING", "description": "A1|A2|B1|B2|C1"},
            "mode": {"type": "STRING", "description": "chat|scene|drill|review|shadow"},
            "scene": {"type": "STRING", "description": "airport|restaurant|hotel|shopping|hospital|interview|meeting|phone|smalltalk|directions"},
            "policy": {"type": "STRING", "description": "flow|recast|focus — correction style"},
            "said": {"type": "STRING", "description": "What the learner actually said (verbatim)"},
            "correct": {"type": "STRING", "description": "The corrected form"},
            "kind": {"type": "STRING", "description": "grammar|vocab|pronunciation|register|fluency"},
            "note": {"type": "STRING", "description": "One-line explanation in the learner's own language"},
            "term": {"type": "STRING", "description": "Word or phrase to remember"},
            "reading": {"type": "STRING", "description": "Pronunciation/reading (kana, pinyin, IPA…)"},
            "meaning": {"type": "STRING", "description": "Meaning in the learner's own language"},
            # ★번역을 함께 받는다★ 원문만 주면 B1 학습자에게 절반만 주는 것이다.
            # 옛 모양(원문만)도 그대로 받는다 — 이미 쌓인 카드가 그 모양이다.
            "examples": {"type": "ARRAY",
                         "description": "Example sentences using it. Put the "
                                        "learner's-language translation after a '|' "
                                        "-- 'Ayer comi paella. | I ate paella "
                                        "yesterday.' Without it the learner only gets "
                                        "half the example.",
                         "items": {"type": "STRING"}},
            "item_id": {"type": "STRING", "description": "Review item id (review_answer)"},
            "correct_answer": {"type": "BOOLEAN", "description": "Did the learner get it right?"},
            "passed": {"type": "BOOLEAN",
                       "description": "note_probe: did the learner handle the harder form?"},
            "probe_level": {"type": "STRING",
                            "description": "note_probe: CEFR level of the form you planted"},
        },
        "required": ["action"],
    }
    author = "wangjacsi"
    # ★`memory`가 생겼다★(v0.5.0) 예전에는 학습 기록이 **자기 폴더에만** 있어서,
    # 코스모스는 이 사람이 무엇을 배우는지조차 몰랐다. 그래서 대화 중에 스페인어
    # 얘기가 나와도 잇지 못했고, 이어가자고 할 재료도 없었다(원칙 0 ③).
    capabilities = ["memory"]
    requires_desktop = False
    view_title = "🗣 Lingua Live"

    # ★설정은 이 화면의 Settings 탭에 있다★ (v0.5.2 · 코스모스 계약 2026-09-03)
    #
    # 이 선언이 없던 동안 코스모스의 에이전트 목록은 이 줄에 ★"Nothing to set up —
    # it just works"★ 를 붙였다 — 교정 방식·모드·언어·레벨 네 칸이 버젓이 있는데.
    # 판정이 플러그인 수준 `settings` 선언만 봤기 때문이다. 네 칸을 그쪽으로 옮기지
    # 않는 이유: 값이 학습 진행 데이터와 **한집**에 살아야 하고(레벨은 사용자가
    # 고르지만 대화가 그 위로 재기도 한다), 이 탭은 현재 선택 강조·모국어 병기·
    # 레벨 설명까지 얹어 일반 폼보다 낫다. 그래서 *"내 화면을 이 params로 열면
    # 설정이 나온다"* 만 선언한다.
    settings_at = {"_tab": "settings"}

    # ★말로 이렇게 시킨다★ — 설치 목록의 카드가 이 줄들을 사용자 언어로 보여 준다.
    # 이 줄들이 없던 동안 카드는 무엇을 하는지(description)는 말해도 **어떻게
    # 시키는지**는 말하지 않았다 — Sean 지적(2026-08-12) *"모든 에이전트가 어떻게
    # 사용되는 건지 … 하나도 안 나와 있어"* 의 마켓판이다.
    howto = (
        "Let's practice Spanish",
        "Stop correcting me",
        "How is my Japanese coming along?",
    )

    # ── ★협업 — 코스모스와 함께 돕는다★ (계약: `cosmos/contracts/collab.py`) ────
    #
    # > *"언어를 배우고 싶다는 것에서부터 사용자가 이 에이전트를 설치를 한 것임.
    # >  따라서 언어를 어떻게 배우고 있으며 진도는 어떻게 나가고 있고 어떤 것을
    # >  어려워 하고 어떤 도움을 줄수 있어야 하는지를 에이전트와 코스모스가 서로
    # >  협력을 해서 도움을 줄수 있어야 하는거야."*(Sean 2026-08-17)
    purpose = ("The user installed this to learn a language, so what matters is which "
               "language they are working on, how far along they are, and what keeps "
               "tripping them up.")
    makes_offers = True

    # ★기억의 규율 — 무엇을 브레인에 올리고 무엇을 여기 두는가★
    #
    # 카드 수백 장을 브레인에 넣으면 회상이 그것들로 덮인다(자기점검이 같은 문제를
    # 69번 기억해 브레인을 덮은 사고와 같은 부류). 그래서 **적고 오래 가는 것만** 올린다:
    #
    #   브레인   목표 언어 · 수준 · ★어디가 약한가★ — 나중에도 참이고 대화에서 쓰인다
    #   자기 폴더 개별 카드 · 복습 일정 · 세션 기록 — 많고 자주 바뀐다
    brain = {
        "stores": ("goal", "topic", "preference"),
        "reads": ("goal", "topic", "preference"),
        "settled": "The individual flashcards, their review schedule and the per-session "
                   "logs stay in this agent's own data folder. There can be hundreds of "
                   "them and they change every session, so putting them in the brain "
                   "would bury recall under material nobody asks about. What goes to the "
                   "brain is the small, lasting part: which language is being learned, "
                   "roughly how far along, and which kind of mistake keeps coming back.",
    }

    # ── ★협업 — 이어가자고 내민다★ (v0.5.0) ─────────────────────────────────
    def offer(self, ctx: ToolContext) -> dict | None:
        """이어갈 만한 것이 있으면 내민다. **때는 코스모스가 고른다.**

        ★말은 여기서 만들지 않는다★ 사용자의 언어로 말할 사람은 코스모스이고,
        여기서 문장을 박으면 이 에이전트는 그 언어 사용자에게만 쓸모 있게 된다
        (v0.4.0이 화면 어휘를 한국어로 박아 정확히 그렇게 됐었다).
        """
        try:
            data = self._load(ctx)
        except Exception:
            return None
        reason = offer_reason(
            due_cards=len(self._due(data)),
            days_idle=days_between(data.get("updated", ""), time.time()),
            weakest=self._analyze(data).get("weakest", ""))
        if not reason:
            return None
        lang = LANGUAGES.get(data["language"], {}).get("label", data["language"])
        if reason["kind"] == "review":
            say = (f"{reason['due']} {lang} items are due for review"
                   + (f", mostly {reason['weakest']}" if reason["weakest"] else "")
                   + " — offer to go through them now.")
        else:
            say = (f"It has been about {reason['days']} days since the last "
                   f"{lang} practice — offer to pick it back up.")
        return {"say": say, "weight": reason["weight"],
                # ★트리거★ 사용자가 "그래" 하면 이것이 시작된다.
                "start": {"tool": self.name,
                          "args": {"action": "start",
                                   "mode": "review" if reason["kind"] == "review"
                                           else data["mode"]}}}

    # ── ★기억 — 적고 오래 가는 것만 브레인으로★ (v0.5.0) ────────────────────
    #
    # 개별 카드는 자기 폴더에 남는다(위 `brain["settled"]`). 여기 올리는 셋은
    # **나중에도 참이고 대화에서 쓰이는 것**이다.
    def _remember_progress(self, ctx: ToolContext, data: dict) -> None:
        """무엇을 배우는 중이고 어디가 약한가 — 대화가 그것을 알아야 이어진다."""
        brain = getattr(ctx, "brain", None)
        if brain is None:
            return
        try:
            from cosmos.contracts.memory import Entity, Relation, Trust, now_ts
        except Exception:
            return
        code = data.get("language", "")
        label = LANGUAGES.get(code, {}).get("label", code)
        if not label:
            return
        uid = getattr(ctx, "user_id", "") or ""
        stamp = now_ts()
        # 확신 1.0 · provenance="user" — ★어느 언어를 배울지는 **사용자가 정한 것**★이라
        # 어떤 자동 파이프라인도 덮으면 안 된다(불변 규칙).
        trust = Trust(confidence=1.0, provenance="user", source_channel=CHANNEL)
        try:
            goal_id = brain.upsert_entity(uid, Entity(
                name=f"Learning {label}", kind="goal",
                attrs={**trust.to_attrs(), "language": code,
                       "level": data.get("level", ""),
                       "last_practised": _now()},
                valid_from=stamp))
            if not goal_id:
                return                    # 사용자가 지운 것은 되살리지 않는다(툼스톤)
            made = [goal_id]
            topic_id = brain.upsert_entity(uid, Entity(
                name=label, kind="topic", attrs={**trust.to_attrs()}, valid_from=stamp))
            if topic_id:
                made.append(topic_id)
                brain.upsert_relation(uid, Relation(
                    src=goal_id, dst=topic_id, rel="about",
                    attrs={**trust.to_attrs()}, valid_from=stamp))
            # ★약한 축은 **성향이 됐을 때만**★ 매 세션 적으면 브레인이 이 하나로 덮인다.
            weakest = self._analyze(data).get("weakest", "")
            if weakest and len(data.get("history") or ()) >= PROMOTE_AFTER:
                pref_id = brain.upsert_entity(uid, Entity(
                    name=f"Finds {label} {weakest} hard", kind="preference",
                    attrs={**Trust(confidence=0.7, provenance="extracted",
                                   source_channel=CHANNEL).to_attrs(),
                           "language": code, "axis": weakest},
                    valid_from=stamp))
                if pref_id:
                    made.append(pref_id)
            try:
                from cosmos.core import provenance
                provenance.record(brain, uid, self, made, now=stamp)
            except Exception:
                pass
        except Exception as e:
            ctx.write_log(f"[lingua] could not remember: {e}")

    def _recall_progress(self, ctx: ToolContext) -> str:
        """★되읽는 문★ — 새 세션이 백지에서 시작하지 않게 한다(원칙 0 ③).

        빈 문자열이면 아직 아무것도 모른다는 뜻이고, 그러면 평소대로 물어보면 된다.
        """
        try:
            hits = ctx.brain_search("language learning goal level", k=4,
                                    agent=self.name)
        except Exception:
            return ""
        lines = [str(h.get("text") or "").strip() for h in (hits or [])]
        return " · ".join([line for line in lines if line][:3])

    # ── 상태 저장 — 코드(설치 디렉터리)와 분리된 곳에 둔다(업데이트가 진도를 지우지 않게) ──
    def _dir(self, ctx: ToolContext):
        return ctx.data_dir("lingua-live")

    def _load(self, ctx: ToolContext) -> dict:
        try:
            data = json.loads((self._dir(ctx) / "state.json").read_text(encoding="utf-8"))
        except Exception:
            data = {}
        data.setdefault("language", "en")
        data.setdefault("level", "A2")
        data.setdefault("mode", "chat")
        data.setdefault("scene", "smalltalk")
        data.setdefault("policy", "recast")
        data.setdefault("session", 0)
        data.setdefault("items", [])
        data.setdefault("today", [])          # 이번 세션에서 만든 카드 id
        data.setdefault("history", [])        # 세션 기록(분석 리포트 누적)
        data.setdefault("probes", [])         # 대화 중 심은 난이도 시험 결과(동적 평가)
        data.setdefault("level_source", "user")
        return data

    def _save(self, ctx: ToolContext, data: dict) -> None:
        data["updated"] = _now()
        (self._dir(ctx) / "state.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    # ── 학습 규칙 ────────────────────────────────────────────────────────────
    def _due(self, data: dict) -> list[dict]:
        """지금 다시 만나야 할 항목 — 잊기 직전에 돌아온다(철학 ⑤)."""
        return [i for i in data["items"]
                if i["lang"] == data["language"] and not i.get("graduated")
                and i.get("due", 0) <= data["session"]]

    def _find_similar(self, data: dict, said: str, correct: str) -> dict | None:
        key = (correct or said or "").strip().lower()
        for item in data["items"]:
            if item["lang"] == data["language"] and item.get("correct", "").lower() == key:
                return item
        return None

    def _analyze(self, data: dict, *, session: int | None = None) -> dict:
        """대화 전체를 읽어 **무엇이 약하고 다음에 무엇을 할지**를 낸다(철학 ⑥).

        시험을 따로 보지 않는다. 재료는 이미 대화에서 나온 것들이다:
          · probe   — 대화 안에 심어 둔 한 단계 위 표현을 처리했는가(동적 평가)
          · 오류 축 — 문법/어휘/발음/격식/유창성 중 어디에 쏠렸는가
          · 복습    — 지난 것을 실제로 다시 해냈는가
        레벨은 **제안만** 한다. 바꾸는 것은 학습자의 결정이다(플랫폼 원칙과 같다).
        """
        code = data["language"]
        probes = [p for p in data["probes"] if p["lang"] == code]
        if session is not None:
            probes = [p for p in probes if p["session"] == session]
        recent = probes[-12:]
        rate = (sum(1 for p in recent if p["passed"]) / len(recent)) if recent else None

        items = [i for i in data["items"] if i["lang"] == code]
        scope = [i for i in items if i["id"] in data["today"]] if session is not None else items
        axes = {kind: 0 for kind in ERROR_KINDS}
        for item in scope:
            if item.get("type") != "word":
                axes[item.get("kind", "grammar")] = axes.get(item.get("kind", "grammar"), 0) + 1
        weakest = max(axes, key=lambda k: axes[k]) if any(axes.values()) else ""

        hits = sum(i.get("hits", 0) for i in items)
        misses = sum(i.get("misses", 0) for i in items)
        review_rate = hits / (hits + misses) if (hits + misses) else None

        order = list(LEVELS)
        idx = order.index(data["level"]) if data["level"] in order else 1
        # ★이유는 **번역 키와 인자로** 돌려준다★ 여기는 `ctx`가 없는 자리(순수 계산)라
        # 사용자 언어를 모른다. 완성된 문장을 만들어 두면 그 언어가 곧 굳어 버린다 —
        # 화면이 `lingua_i18n.t(ctx.lang, why, **why_args)`로 그때 옮긴다.
        suggest, why, why_args = "", "", {}
        if rate is not None and len(recent) >= 3:
            if rate >= PROBE_UP and idx < len(order) - 1:
                suggest = order[idx + 1]
                why, why_args = ("You handled {rate} of the next level up",
                                 {"rate": f"{rate:.0%}"})
            elif rate <= PROBE_DOWN and idx > 0:
                suggest = order[idx - 1]
                why, why_args = ("You cleared {rate} of the next level up",
                                 {"rate": f"{rate:.0%}"})
        if not suggest and review_rate is not None and review_rate <= 0.4 and idx > 0:
            suggest = order[idx - 1]
            why, why_args = ("Review accuracy is {rate}", {"rate": f"{review_rate:.0%}"})

        plan = PRESCRIPTIONS.get(weakest) if weakest else None
        return {
            "probe_rate": rate, "probes": len(recent),
            "axes": axes, "weakest": weakest,
            "review_rate": review_rate, "cards": len(scope),
            "suggest": suggest, "why": why, "why_args": why_args,
            "prescription": plan, "level": data["level"],
        }

    # ── 실행 ─────────────────────────────────────────────────────────────────
    def run(self, ctx: ToolContext, **args) -> str:
        action = str(args.get("action") or "status").strip()
        data = self._load(ctx)
        if (tab := str(args.get("_tab") or "").strip()):
            data["view_tab"] = tab          # 뷰의 탭 전환(화면 전용 — 모델은 쓰지 않는다)
        handler = getattr(self, f"_do_{action}", None)
        if handler is None:
            return (f"Unknown action '{action}'. "
                    f"Use: start, note_error, note_word, review_answer, set, status, finish")
        try:
            result = handler(ctx, data, args)
        except Exception as e:                      # 학습 도구가 대화를 죽이지 않는다
            return f"Lingua error: {e}"
        self._save(ctx, data)
        return result

    def _do_set(self, ctx, data, args) -> str:
        changed = []
        for field, vocab in (("language", LANGUAGES), ("level", LEVELS),
                             ("mode", MODES), ("scene", SCENES), ("policy", POLICIES)):
            value = str(args.get(field) or "").strip()
            if value and value in vocab:
                data[field] = value
                changed.append(f"{field}={value}")
            elif value:
                return (f"'{value}' is not a valid {field}. "
                        f"Choose one of: {', '.join(vocab)}")
        ctx.write_log(f"[lingua] {', '.join(changed) or _t(ctx.lang, 'no change')}")
        return f"Settings updated: {', '.join(changed) or '(none)'}. " + self._brief(data)

    def _do_status(self, ctx, data, args) -> str:
        return self._brief(data)

    def _brief(self, data: dict) -> str:
        lang = LANGUAGES[data["language"]]
        return (f"Target={lang['native']}({data['language']}), level={data['level']}, "
                f"mode={data['mode']}, correction policy={data['policy']}, "
                f"due for review={len(self._due(data))}, session #{data['session']}.")

    def _do_start(self, ctx, data, args) -> str:
        """세션 시작 — 모델에게 **이번 시간의 규칙**을 준다.

        철학이 문서에만 있으면 아무 일도 일어나지 않는다. 이 반환문이 그 철학을
        매 세션 모델의 행동 규칙으로 주입하는 지점이다.
        """
        for field, vocab in (("language", LANGUAGES), ("level", LEVELS),
                             ("mode", MODES), ("scene", SCENES), ("policy", POLICIES)):
            value = str(args.get(field) or "").strip()
            if value and value in vocab:
                data[field] = value
        data["session"] += 1
        data["today"] = []
        lang = LANGUAGES[data["language"]]
        policy = POLICIES[data["policy"]]
        mode = MODES[data["mode"]]
        due = self._due(data)[:MAX_FOCUS_ITEMS]
        report = self._analyze(data)
        # ★시작할 때 자세를 집중으로 올린다★ 지금 이걸 하는 중이라는 뜻이고, 그동안은
        # *"이어가자"* 고 또 권하지 않는다. 시간이 지나면 **저절로** 배경으로 돌아온다.
        try:
            from cosmos.core import collab as _collab
            _collab.set_stance(self.name, "focus", getattr(ctx, "user_id", "") or "")
        except Exception:
            pass                          # 자세를 못 적어도 수업은 계속된다

        lines = [
            f"[LINGUA LIVE — session #{data['session']}]",
            f"Target language: {lang['native']} ({data['language']}). "
            f"Learner level: {data['level']} — {LEVELS[data['level']]}",
            f"Mode: {mode['label']} — {mode['desc']}",
        ]
        # ★되읽는 문★ 브레인이 이미 아는 것을 세션 앞에 놓는다 — 없으면 빈 줄도 안 넣는다.
        if (known := self._recall_progress(ctx)):
            lines.append(f"What Cosmos already knows about this: {known}")
        if data["mode"] == "scene":
            lines.append(f"Scene: {SCENES[data['scene']]}. Play the other role. "
                         f"Stay in character; do not narrate.")
        if data["mode"] == "review":
            lines.append("Review mode: work ONLY through the review queue below. "
                         "Ask the learner to produce each item in a fresh sentence.")
        if data["mode"] == "shadow":
            lines.append("Shadowing: say one short line, ask the learner to repeat it "
                         "exactly, then give one specific pronunciation note.")

        lines += [
            "",
            "TEACHING RULES (follow strictly):",
            f"- Correction policy: {policy['label']} — {policy['instruction']}",
            "- Speak mostly in the target language, one step above the learner's level "
            "(i+1). Keep your turns SHORT so the learner talks more than you do.",
            "- Explanations of grammar/meaning go in the learner's own language, briefly.",
            "- Ask a question at the end of almost every turn — silence kills practice.",
            "- If the learner stops mid-sentence, WAIT. Do not finish their sentence.",
            "",
            "*** DO NOT CALL ANY TOOL WHILE TALKING. ***",
            "Corrections, vocabulary cards and level measurement all happen automatically "
            "in the background and appear on the learner's screen. Calling a tool mid-"
            "conversation makes you go silent while you write it — that is what broke the "
            "flow before. Just talk. Only call lingua again for: finish (session end), "
            "set (the learner asks to change language/level/mode), or status.",
            "",
            "CONTINUOUS LEVEL ADAPTATION (no test, no tool call):",
            f"- About every {PROBE_EVERY_TURNS} turns, slip ONE structure from the level "
            f"above {data['level']} into a normal sentence. Watch whether they handle it.",
            "- If they handle two in a row, raise your own level for the rest of the "
            "session. If they miss two, shorten sentences and simplify. Adapt live.",
        ]
        if due:
            lines += ["", f"REVIEW QUEUE — start with these {len(due)} items "
                          "(ask the learner to use each one, then call review_answer):"]
            for item in due:
                lines.append(f"  · [{item['id'][:6]}] {item.get('correct') or item.get('term')}"
                             f" — {item.get('note') or item.get('meaning') or ''}")
        else:
            lines += ["", "REVIEW QUEUE: empty — this is a fresh start, build from today."]
        if report["suggest"]:
            lines.append(
                f"NOTE: measurements suggest level {report['suggest']} "
                f"({_t('en', report['why'], **(report.get('why_args') or {}))}) — "
                f"ask the learner before changing it.")
        if report["weakest"] and report["prescription"]:
            lines.append(f"WEAKEST AXIS so far: {ERROR_KINDS[report['weakest']]} — "
                         f"{report['prescription']['say']}")

        ctx.write_log("[lingua] " + _t(
            ctx.lang, "Session #{session} · {language} · {mode} · "
                      "correction {policy} · {due} to review",
            session=data["session"], language=_t(ctx.lang, lang["label"]),
            mode=_t(ctx.lang, mode["label"]), policy=_t(ctx.lang, policy["label"]),
            due=len(due)))
        return "\n".join(lines)

    def _do_note_error(self, ctx, data, args) -> str:
        said = str(args.get("said") or "").strip()
        correct = str(args.get("correct") or "").strip()
        if not correct:
            return "note_error needs the corrected form ('correct')."
        kind = str(args.get("kind") or "grammar")
        kind = kind if kind in ERROR_KINDS else "grammar"
        note = str(args.get("note") or "").strip()

        existing = self._find_similar(data, said, correct)
        if existing is not None:
            existing["seen"] = existing.get("seen", 0) + 1
            existing["said"] = said or existing.get("said", "")
            existing["last"] = _now()
            promoted = existing["seen"] >= PROMOTE_AFTER and existing.get("box", 0) == 0
            if promoted:
                # 반복되는 오류만 승격한다(철학 ④) — 그제야 복습 큐로 들어간다
                existing["box"] = 1
                existing["due"] = data["session"] + SRS_INTERVALS[0]
            item = existing
        else:
            item = {"id": uuid.uuid4().hex, "type": "error", "lang": data["language"],
                    "said": said, "correct": correct, "kind": kind, "note": note,
                    "examples": [str(e) for e in (args.get("examples") or [])][:3],
                    "seen": 1, "box": 0, "due": 0, "hits": 0, "misses": 0,
                    "created": _now(), "last": _now()}
            data["items"].append(item)
            promoted = False
        if item["id"] not in data["today"]:
            data["today"].append(item["id"])

        # 피드에는 한 줄만 — 교정 본문은 화면(뷰)이 카드로 보여준다
        ctx.write_log("[lingua] ✎ " + _t(ctx.lang, "1 correction")
                      + (" · " + _t(ctx.lang, "promoted to the review queue")
                         if promoted else ""))
        policy = data["policy"]
        if policy == "flow":
            guidance = ("Logged silently and shown on the learner's screen. "
                        "Do NOT mention it aloud. Continue the conversation.")
        elif policy == "recast":
            guidance = (f"Reply naturally, but weave the correct form in as a recast "
                        f"(say the idea back using '{correct}'), then ask your next "
                        f"question. Do not lecture.")
        else:
            guidance = (f"Stop briefly: name the error in one clause, give '{correct}', "
                        f"and ask the learner to say the whole sentence again.")
        if item["seen"] >= PROMOTE_AFTER:
            guidance += (f" This is mistake #{item['seen']} of the same kind — it is now "
                         f"in the review queue, so make the learner produce it once more "
                         f"before moving on.")
        return f"Recorded ({ERROR_KINDS[kind]}). {guidance}"

    def _do_note_word(self, ctx, data, args) -> str:
        term = str(args.get("term") or "").strip()
        if not term:
            return "note_word needs 'term'."
        meaning = str(args.get("meaning") or "").strip()
        item = {"id": uuid.uuid4().hex, "type": "word", "lang": data["language"],
                "term": term, "reading": str(args.get("reading") or "").strip(),
                "meaning": meaning, "note": str(args.get("note") or "").strip(),
                "examples": [str(e) for e in (args.get("examples") or [])][:3],
                "seen": 1, "box": 1, "due": data["session"] + SRS_INTERVALS[0],
                "hits": 0, "misses": 0, "created": _now(), "last": _now()}
        data["items"].append(item)
        data["today"].append(item["id"])
        ctx.write_log(f"[lingua] 📚 {term}"
                      + (f" [{item['reading']}]" if item["reading"] else "")
                      + (f" — {meaning}" if meaning else ""))
        return (f"Saved '{term}' to the learner's cards (visible on their screen with "
                f"examples and playback). Use it again within the next few turns — "
                f"a word met once is a word forgotten.")

    def _do_review_answer(self, ctx, data, args) -> str:
        item_id = str(args.get("item_id") or "").strip()
        item = next((i for i in data["items"] if i["id"].startswith(item_id)), None) \
            if item_id else None
        if item is None:
            due = self._due(data)
            item = due[0] if due else None
        if item is None:
            return "No review item matched."
        ok = bool(args.get("correct_answer"))
        if ok:
            item["hits"] = item.get("hits", 0) + 1
            item["box"] = min(len(SRS_INTERVALS), item.get("box", 1) + 1)
            item["due"] = data["session"] + SRS_INTERVALS[item["box"] - 1]
            if item["box"] >= len(SRS_INTERVALS):
                item["graduated"] = True
        else:
            item["misses"] = item.get("misses", 0) + 1
            item["box"] = 1                       # 틀리면 처음부터 — 간격을 되감는다
            item["due"] = data["session"] + SRS_INTERVALS[0]
        item["last"] = _now()
        label = item.get("correct") or item.get("term")
        ctx.write_log(f"[lingua] {'○' if ok else '✕'} " + _t(
            ctx.lang, "review {label} (box {box}/{total})",
            label=label, box=item["box"], total=len(SRS_INTERVALS)))
        if item.get("graduated"):
            return f"'{label}' graduated — the learner owns it now. Tell them so."
        return (f"Review recorded ({'correct' if ok else 'missed'}). "
                f"It returns in {SRS_INTERVALS[item['box'] - 1]} session(s)."
                + ("" if ok else " Make them use it correctly once before moving on."))

    def _do_note_probe(self, ctx, data, args) -> str:
        """대화 안에 심어 둔 '한 단계 위'를 처리했는가 — 시험 없이 재는 방법(철학 ⑥)."""
        passed = bool(args.get("passed"))
        level = str(args.get("probe_level") or "").strip()
        level = level if level in LEVELS else data["level"]
        data["probes"].append({"session": data["session"], "lang": data["language"],
                               "level": level, "passed": passed,
                               "note": str(args.get("note") or "")[:200], "at": _now()})
        data["probes"] = data["probes"][-200:]
        recent = [p for p in data["probes"] if p["lang"] == data["language"]][-2:]
        streak = len(recent) == 2 and all(p["passed"] == passed for p in recent)
        ctx.write_log(f"[lingua] {'✓' if passed else '·'} " + _t(
            ctx.lang, "level {level} handled" if passed else "level {level} not handled",
            level=level))
        if streak and passed:
            return (f"Two probes passed in a row — speak at {level} from now on: longer "
                    f"sentences, less scaffolding. Keep planting probes above that.")
        if streak and not passed:
            return ("Two probes missed in a row — drop back: shorter sentences, more "
                    "familiar vocabulary, and re-teach the form you just planted.")
        return ("Probe recorded. Keep the conversation natural — the learner must not "
                "feel tested.")

    def _do_report(self, ctx, data, args) -> str:
        report = self._analyze(data)
        lines = [f"[LINGUA REPORT] level {report['level']}"]
        if report["probe_rate"] is not None:
            lines.append(f"- Handles one level up: {report['probe_rate']:.0%} "
                         f"({report['probes']} probes)")
        if report["review_rate"] is not None:
            lines.append(f"- Recalls past corrections: {report['review_rate']:.0%}")
        if any(report["axes"].values()):
            lines.append("- Error mix: " + ", ".join(
                f"{ERROR_KINDS[k]} {v}" for k, v in report["axes"].items() if v))
        if report["prescription"]:
            lines.append(f"- Prescription: {report['prescription']['say']}")
        if report["suggest"]:
            lines.append(f"- Suggested level: {report['suggest']} ({report['why']})")
        return "\n".join(lines)

    def _do_finish(self, ctx, data, args) -> str:
        """세션 마무리 = **분석과 처방**. 요약만 하고 끝나면 다음 세션이 달라지지 않는다."""
        cards = [i for i in data["items"] if i["id"] in data["today"]]
        report = self._analyze(data, session=data["session"])
        overall = self._analyze(data)
        record = {"session": data["session"], "at": _now(), "cards": len(cards),
                  "level": data["level"], "probe_rate": report["probe_rate"],
                  "axes": report["axes"], "weakest": report["weakest"],
                  "suggest": overall["suggest"],
                  "hits": sum(i.get("hits", 0) for i in cards),
                  "misses": sum(i.get("misses", 0) for i in cards)}
        data["history"] = (data["history"] + [record])[-50:]
        due_next = len([i for i in data["items"]
                        if not i.get("graduated") and i.get("box")])

        plan = overall["prescription"]
        if plan:                       # 처방은 말로만 하지 않는다 — 다음 세션의 기본값을 바꾼다
            data["mode"] = plan["mode"]
            if plan["policy"]:
                data["policy"] = plan["policy"]
        # ★세션이 끝날 때가 **기억할 것이 확정되는 자리**다★ 도중에 적으면 한 세션이
        # 여러 번 남고, 안 적으면 다음 세션이 백지에서 시작한다(원칙 0 ②).
        self._remember_progress(ctx, data)
        # 수업이 끝났으므로 자세를 배경으로 되돌린다 — 시간이 풀어 주기를 기다리면
        # 그 사이 *"이어가자"* 를 못 한다.
        try:
            from cosmos.core import collab as _collab
            _collab.set_stance(self.name, "ambient", getattr(ctx, "user_id", "") or "")
        except Exception:
            pass
        ctx.write_log("[lingua] " + _t(
            ctx.lang, "Session #{session} closed — {cards} cards · {due} awaiting review",
            session=data["session"], cards=len(cards), due=due_next)
            + (_t(ctx.lang, " · weak: {axis}",
                  axis=_t(ctx.lang, ERROR_KINDS[overall["weakest"]]))
               if overall["weakest"] else "")
            + (_t(ctx.lang, " · next mode {mode}",
                  mode=_t(ctx.lang, MODES[data["mode"]]["label"])) if plan else ""))

        summary = [f"Session #{data['session']} closed. {len(cards)} card(s), "
                   f"{due_next} item(s) in the review queue.",
                   "", "Report this back to the learner in THEIR language, briefly:"]
        if report["probe_rate"] is not None:
            summary.append(f"  · handled {report['probe_rate']:.0%} of next-level "
                           f"forms this session ({report['probes']} probes)")
        if any(report["axes"].values()):
            summary.append("  · error mix: " + ", ".join(
                f"{ERROR_KINDS[k]} {v}" for k, v in report["axes"].items() if v))
        for item in cards[:MAX_FOCUS_ITEMS]:
            summary.append(f"  · {item.get('correct') or item.get('term')}"
                           f" — {item.get('note') or item.get('meaning') or ''}")
        if plan:
            summary.append(f"  · to shore up: {plan['say']} "
                           f"(next session is set to {MODES[data['mode']]['label']})")
        if overall["suggest"]:
            summary.append(
                f"  · level re-read: {data['level']} → {overall['suggest']} "
                f"({_t('en', overall['why'], **(overall.get('why_args') or {}))}). "
                f"Ask the learner first; if they agree, call "
                f"set(level={overall['suggest']}).")
        summary.append("Then tell them when the cards come back (spaced repetition).")
        return "\n".join(summary)

    # ── 백그라운드 교정 — 대화는 계속 흐른다(v0.2.0 핵심) ────────────────────
    observes_turns = True
    _busy = False
    _pending = ""      # 분석 중에 들어온 최신 발화(버리지 않는다)

    def observe_turn(self, ctx: ToolContext, role: str, text: str) -> None:
        """사용자 발화 한 턴을 **대화와 무관하게** 분석해 화면에 카드를 쌓는다.

        여기서 무엇을 하든 튜터는 계속 말한다. 이것이 v0.1.0과의 결정적 차이다:
        예전엔 교정을 툴 호출로 해서, 꼼꼼할수록 대화가 끊겼다.
        """
        text = (text or "").strip()
        if role != "user" or len(text) < MIN_ANALYZE_CHARS:
            return
        with _LOCK:
            data = self._load(ctx)
            if not data.get("session"):
                return                       # 세션을 시작하지 않았으면 관여하지 않는다
            if LinguaLive._busy:
                # 분석 중이면 **버리지 않고 최신 것만 남긴다**. 그냥 건너뛰면 말이
                # 빠른 학습자의 발화가 통째로 사라진다. 다만 밀린 것을 다 처리하면
                # 화면이 과거로 뒤덮이므로, 최신 하나만 이어서 본다.
                LinguaLive._pending = text
                return
            LinguaLive._busy = True
        try:
            lang = LANGUAGES[data["language"]]
            report = self._ask_analyst(ctx, data, text, lang)
            if report is None:
                return
            with _LOCK:
                data = self._load(ctx)       # 그 사이 바뀌었을 수 있다
                added = self._absorb(data, report, text)
                self._save(ctx, data)
            # 코치 — 분석 결과를 **다음 발화에 얹는다**. 턴을 닫지 않으므로 지금 하는
            # 말을 끊지 않는다. 세 역할(대화·분석·코치)이 여기서 만난다.
            if (coach := str(report.get("coach") or "").strip()):
                ctx.nudge(f"[TUTOR COACH — do not read this aloud] {coach}")
            if added:
                # 피드에는 **한 줄만**. 교정 본문을 대화창에 쏟으면 읽히지도 않고
                # 대화 기록을 덮어 버린다(실사용 스크린샷의 그 벽).
                ctx.write_log("[lingua] ✎ " + _t(
                    ctx.lang, "{count} corrections — see them on the 🧩 screen",
                    count=added))
        except Exception as e:
            print(f"[lingua] background analysis failed: {e}")
        finally:
            LinguaLive._busy = False
            with _LOCK:
                queued, LinguaLive._pending = LinguaLive._pending, ""
            if queued:
                self.observe_turn(ctx, "user", queued)   # 밀린 최신 발화를 이어서

    def _ask_analyst(self, ctx: ToolContext, data: dict, text: str, lang: dict) -> dict | None:
        prompt = (f"Target language: {lang['native']} ({data['language']}). "
                  f"Learner level: {data['level']}. "
                  f"The learner's own language is Korean — write notes in Korean.\n"
                  f"Learner just said:\n\"{text}\"")
        try:
            # fast: 사고를 끈다. 형식이 정해진 추출이라 정확도는 그대로인데 지연이
            # 몇 배 줄어든다(실측 8.3s → 1.3s). 실시간 대화 옆에서는 이 차이가
            # '몇 번째 발화까지 따라잡느냐'를 가른다.
            raw = ctx.think(prompt, system=ANALYST_SYSTEM, fast=True)
        except Exception as e:
            print(f"[lingua] analyst unavailable: {e}")
            return None
        match = re.search(r"\{.*\}", raw or "", re.S)
        if not match:
            return None
        try:
            report = json.loads(match.group(0))
        except Exception:
            return None
        return report if isinstance(report, dict) else None

    def _absorb(self, data: dict, report: dict, said: str) -> int:
        """분석 결과를 학습 항목으로 흡수 — 승격·간격 반복 규칙은 그대로 적용된다."""
        added = 0
        for raw in (report.get("corrections") or [])[:MAX_CORRECTIONS_PER_TURN]:
            if not isinstance(raw, dict) or not str(raw.get("right") or "").strip():
                continue
            correct = str(raw["right"]).strip()
            kind = str(raw.get("kind") or "grammar")
            kind = kind if kind in ERROR_KINDS else "grammar"
            existing = self._find_similar(data, said, correct)
            if existing is not None:
                existing["seen"] = existing.get("seen", 0) + 1
                existing["last"] = _now()
                if existing["seen"] >= PROMOTE_AFTER and not existing.get("box"):
                    existing["box"] = 1      # 반복되는 오류만 복습 큐로(철학 ④)
                    existing["due"] = data["session"] + SRS_INTERVALS[0]
                item = existing
            else:
                item = {"id": uuid.uuid4().hex, "type": "error", "lang": data["language"],
                        "said": str(raw.get("wrong") or said).strip(), "correct": correct,
                        "kind": kind, "note": str(raw.get("note") or "").strip(),
                        "tag": str(raw.get("tag") or "").strip(),
                        "examples": [], "seen": 1, "box": 0, "due": 0,
                        "hits": 0, "misses": 0, "created": _now(), "last": _now()}
                data["items"].append(item)
            if item["id"] not in data["today"]:
                data["today"].append(item["id"])
            added += 1

        for raw in (report.get("words") or [])[:1]:
            term = str((raw or {}).get("term") or "").strip()
            if not term or any(i.get("term") == term and i["lang"] == data["language"]
                               for i in data["items"]):
                continue
            item = {"id": uuid.uuid4().hex, "type": "word", "lang": data["language"],
                    "term": term, "reading": str(raw.get("reading") or "").strip(),
                    "meaning": str(raw.get("meaning") or "").strip(), "note": "",
                    "examples": [str(e) for e in (raw.get("examples") or [])][:2],
                    "seen": 1, "box": 1, "due": data["session"] + SRS_INTERVALS[0],
                    "hits": 0, "misses": 0, "created": _now(), "last": _now()}
            data["items"].append(item)
            data["today"].append(item["id"])
            added += 1

        fit = str(report.get("level_fit") or "")
        if fit in ("below", "at", "above"):
            # 툴 호출 없이도 수준이 측정된다 — 발화 자체가 probe다(철학 ⑥·⑦의 결합)
            data["probes"].append({"session": data["session"], "lang": data["language"],
                                   "level": data["level"], "passed": fit != "below",
                                   "note": f"level_fit={fit}", "at": _now()})
            data["probes"] = data["probes"][-200:]
        return added

    # ── 전용 뷰 — 대화가 흘러가도 눈으로 남는 것 ─────────────────────────────
    def view(self, ctx: ToolContext, **params) -> dict:
        """말은 사라진다. 학습자가 붙잡을 수 있는 것은 화면에 남는 카드다.

        탭은 셋뿐이다: 오늘 / 복습 / 설정. 설정을 늘리는 대신 철학이 정하게 한다.
        """
        data = self._load(ctx)
        # 탭은 **상태**다(params가 아니라). 액션이 상태를 바꾸고 뷰가 그것을 읽는 한 방향
        # 흐름이라야, 셸이 무엇을 되돌려 주든 화면과 상태가 어긋나지 않는다.
        tab = str(data.get("view_tab") or params.get("tab") or "today")
        lang = LANGUAGES[data["language"]]
        code = data["language"]
        ui = ctx.lang                     # ★사용자가 **읽는** 언어(배우는 언어가 아니다)★
        due = self._due(data)
        tabs = (("today", _t(ui, "Today")),
                ("review", _t(ui, "Review {count}", count=len(due))),
                ("report", _t(ui, "Report")),
                ("settings", _t(ui, "Settings")))
        blocks: list[dict] = [{
            "type": "chips", "items": [
                {"label": _t(ui, "Language"),
                 "value": f"{_t(ui, lang['label'])} {lang['native']}"},
                {"label": _t(ui, "Level"), "value": data["level"]},
                {"label": _t(ui, "Mode"), "value": _t(ui, MODES[data["mode"]]["label"])},
                {"label": _t(ui, "Correction"),
                 "value": _t(ui, POLICIES[data["policy"]]["label"]),
                 "tone": "warn" if data["policy"] == "focus" else "good"},
                {"label": _t(ui, "Session"), "value": f"#{data['session']}"},
            ]}, {
            "type": "actions", "items": [
                {"label": label, "tool": self.name,
                 "args": {"action": "status", "_tab": key},
                 "style": "primary" if tab == key else "ghost"}
                for key, label in tabs]}]

        if tab == "review":
            blocks += self._review_blocks(data, due, code, ui)
        elif tab == "settings":
            blocks += self._settings_blocks(data, ui)
        elif tab == "report":
            blocks += self._report_blocks(data, ui)
        else:
            blocks += self._today_blocks(data, code, ui)

        graduated = sum(1 for i in data["items"] if i.get("graduated"))
        total = len(data["items"])
        return {
            "title": "🗣 Lingua Live",
            "subtitle": f"{_t(ui, lang['label'])} · {data['level']} · "
                        f"{_t(ui, MODES[data['mode']]['label'])} · "
                        + _t(ui, "{cards} cards · {graduated} graduated",
                             cards=total, graduated=graduated),
            "params": {"tab": tab},
            "blocks": blocks,
        }

    def _card(self, item: dict, code: str, ui: str) -> dict:
        """단어 카드 — 뜻·읽기·예문."""
        return {"title": item.get("term", ""), "reading": item.get("reading", ""),
                "subtitle": item.get("meaning", ""), "body": item.get("note", ""),
                "lang": code, "tone": "info",
                "tags": [_t(ui, "review {box}/{total}",
                            box=item.get("box", 0), total=len(SRS_INTERVALS))],
                # ★번역을 채운다★ 예전에는 여기서 빈 문자열을 고정으로 넣어
                # 계약의 칸이 영영 비어 있었다(위 `split_example` 참고).
                "examples": [split_example(e) for e in item.get("examples") or []]}

    def _correction(self, item: dict, code: str, ui: str) -> dict:
        """교정 카드 — **틀린 것과 고친 것을 나란히**. 문단으로 늘어놓으면 무엇이
        어떻게 바뀌었는지 읽히지 않는다(v0.1.0의 실패)."""
        tag = " · ".join(x for x in (
            item.get("tag") or _t(ui, ERROR_KINDS.get(item.get("kind", ""), "")),
            _t(ui, "seen {count}×", count=item["seen"]) if item.get("seen", 1) > 1 else "",
            _t(ui, "review {box}/{total}", box=item["box"], total=len(SRS_INTERVALS))
            if item.get("box") else "") if x)
        return {"wrong": item.get("said", ""), "right": item.get("correct", ""),
                "note": item.get("note", ""), "lang": code, "tag": tag,
                # ★번역을 채운다★ 예전에는 여기서 빈 문자열을 고정으로 넣어
                # 계약의 칸이 영영 비어 있었다(위 `split_example` 참고).
                "examples": [split_example(e) for e in item.get("examples") or []]}

    def _split(self, items: list[dict]) -> tuple[list[dict], list[dict]]:
        return ([i for i in items if i.get("type") != "word"],
                [i for i in items if i.get("type") == "word"])

    def _today_blocks(self, data: dict, code: str, ui: str) -> list[dict]:
        today = [i for i in data["items"] if i["id"] in data["today"]]
        errors, words = self._split(today)
        if not today:
            return [{"type": "text", "tone": "muted",
                     "text": _t(ui, "Start talking and your corrections and new words "
                                    "pile up here. Nothing interrupts you while you "
                                    "speak — anything to fix appears quietly on this "
                                    "screen. Tap 🔊 to hear it again.")},
                    {"type": "actions", "items": [
                        {"label": _t(ui, "Start talking"), "tool": self.name,
                         "style": "primary",
                         "args": {"action": "start", "mode": "chat", "_tab": "today"}},
                        {"label": _t(ui, "Role-play"), "tool": self.name,
                         "args": {"action": "start", "mode": "scene", "_tab": "today"}},
                        {"label": _t(ui, "Review"), "tool": self.name,
                         "args": {"action": "start", "mode": "review", "_tab": "today"}}]}]
        waiting = len([i for i in data["items"]
                       if i.get("box") and not i.get("graduated")])
        blocks: list[dict] = [{"type": "chips", "items": [
            {"label": _t(ui, "Corrections today"), "value": f"{len(errors)}", "tone": "warn"},
            {"label": _t(ui, "New words"), "value": f"{len(words)}", "tone": "info"},
            {"label": _t(ui, "Waiting for review"), "value": f"{waiting}"},
        ]}]
        if errors:
            # 최신이 위로 — 방금 말한 것을 바로 확인하게 한다
            # ★안 붙은 것이 위로★(최신순이 아니다 — 위 `by_learning_need` 참고)
            blocks.append({"type": "correction",
                           "items": [self._correction(i, code, ui)
                                     for i in by_learning_need(errors)]})
        if words:
            blocks.append({"type": "text", "tone": "muted",
                           "text": _t(ui, "Words you met today")})
            blocks.append({"type": "cards",
                           "items": [self._card(i, code, ui) for i in reversed(words)]})
        blocks.append({"type": "actions", "items": [
            {"label": _t(ui, "Review these"), "tool": self.name, "style": "primary",
             "args": {"action": "start", "mode": "review", "_tab": "today"}},
            {"label": _t(ui, "Wrap up today"), "tool": self.name,
             "args": {"action": "finish", "_tab": "report"}}]})
        return blocks

    def _review_blocks(self, data: dict, due: list[dict], code: str,
                       ui: str) -> list[dict]:
        queued = [i for i in data["items"]
                  if i["lang"] == code and i.get("box") and not i.get("graduated")]
        blocks: list[dict] = [{
            "type": "progress", "label": _t(ui, "Review queue"),
            "value": (len(queued) - len(due)) / len(queued) if queued else 0.0,
            "caption": _t(ui, "{due} to see now · {queued} waiting · "
                              "intervals {intervals} sessions",
                          due=len(due), queued=len(queued),
                          intervals="→".join(str(s) for s in SRS_INTERVALS))}]
        if due:
            errors, words = self._split(due[:10])
            if errors:
                blocks.append({"type": "correction",
                               "items": [self._correction(i, code, ui)
                                         for i in by_learning_need(errors)]})
            if words:
                blocks.append({"type": "cards",
                               "items": [self._card(i, code, ui) for i in words]})
            blocks.append({"type": "actions", "items": [
                {"label": _t(ui, "Start review"), "tool": self.name, "style": "primary",
                 "args": {"action": "start", "mode": "review", "_tab": "today"}}]})
        else:
            blocks.append({"type": "text", "tone": "good",
                           "text": _t(ui, "Nothing to review right now. It will come "
                                          "back just before you forget.")})
        if queued:
            blocks.append({"type": "list", "items": [
                {"text": i.get("correct") or i.get("term", ""),
                 "sub": _t(ui, "box {box}/{total} · in {sessions} sessions",
                           box=i.get("box"), total=len(SRS_INTERVALS),
                           sessions=max(0, i.get("due", 0) - data["session"])),
                 "lang": code, "tone": "muted"} for i in queued[:20]]})
        return blocks

    def _report_blocks(self, data: dict, ui: str) -> list[dict]:
        """분석 탭 — 무엇이 약하고 다음에 무엇을 할지. 숫자가 아니라 **처방**이 결론이다."""
        report = self._analyze(data)
        blocks: list[dict] = []
        if report["probe_rate"] is not None:
            blocks.append({"type": "progress",
                           "label": _t(ui, "How much of the next level you handled"),
                           "value": report["probe_rate"],
                           "caption": _t(ui, "Measured {probes}× mid-conversation — "
                                             "planted in the talk, not a test",
                                         probes=report["probes"])})
        if report["review_rate"] is not None:
            blocks.append({"type": "progress",
                           "label": _t(ui, "Past corrections you got right again"),
                           "value": report["review_rate"],
                           "caption": _t(ui, "How often you actually did it right "
                                             "in review")})
        total = sum(report["axes"].values())
        if total:
            blocks.append({"type": "list", "items": [
                {"text": f"{_t(ui, ERROR_KINDS[k])}  {'█' * min(20, v)} "
                         + _t(ui, "{count} times", count=v),
                 "tone": "warn" if k == report["weakest"] else "muted"}
                for k, v in report["axes"].items() if v]})
        if report["prescription"]:
            blocks.append({"type": "text", "tone": "info",
                           "text": _t(ui, "What to shore up — ")
                                   + _t(ui, report["prescription"]["say"])})
            blocks.append({"type": "actions", "items": [
                {"label": _t(ui, "Start {mode}",
                             mode=_t(ui, MODES[report["prescription"]["mode"]]["label"])),
                 "tool": self.name, "style": "primary",
                 "args": {"action": "start", "mode": report["prescription"]["mode"],
                          "_tab": "today"}}]})
        if report["suggest"]:
            blocks.append({"type": "text", "tone": "good",
                           "text": _t(ui, "Level re-read: {level} → {suggest} ({why})",
                                      level=report["level"], suggest=report["suggest"],
                                      why=_t(ui, report["why"],
                                             **(report.get("why_args") or {})))})
            up = report["suggest"] > report["level"]
            blocks.append({"type": "actions", "items": [
                {"label": _t(ui, "Move up to {level}" if up else "Move down to {level}",
                             level=report["suggest"]),
                 "tool": self.name, "style": "primary",
                 "args": {"action": "set", "level": report["suggest"], "_tab": "report"}}]})
        if not blocks:
            blocks.append({"type": "text", "tone": "muted",
                           "text": _t(ui, "No conversations to analyse yet. After a few "
                                          "talks your weak axis and level estimate "
                                          "appear here.")})
        history = [h for h in data["history"]][-8:]
        if history:
            blocks.append({"type": "list", "items": [
                {"text": _t(ui, "Session #{session} · {level} · {cards} cards",
                            session=h["session"], level=h.get("level", ""),
                            cards=h.get("cards", 0))
                         + (_t(ui, " · weak: {axis}",
                               axis=_t(ui, ERROR_KINDS.get(h.get("weakest"), "")))
                            if h.get("weakest") else ""),
                 "sub": h.get("at", ""), "tone": "muted"} for h in reversed(history)]})
        return blocks

    def _settings_blocks(self, data: dict, ui: str) -> list[dict]:
        return [
            {"type": "text",
             "text": _t(ui, "Four settings, and that is all — the rest is decided by "
                            "the teaching method. (See the README.)")},
            {"type": "text", "tone": "muted",
             "text": _t(ui, "Correction style: ")
                     + _t(ui, POLICIES[data["policy"]]["desc"])},
            {"type": "actions", "items": [
                {"label": _t(ui, "Correction {style}", style=_t(ui, p["label"])),
                 "tool": self.name,
                 "style": "primary" if key == data["policy"] else "ghost",
                 "args": {"action": "set", "policy": key, "_tab": "settings"}}
                for key, p in POLICIES.items()]},
            {"type": "actions", "items": [
                {"label": _t(ui, m["label"]), "tool": self.name,
                 "style": "primary" if key == data["mode"] else "ghost",
                 "args": {"action": "set", "mode": key, "_tab": "settings"}}
                for key, m in MODES.items()]},
            # 배우는 언어를 고르는 자리 — **이름은 사용자 언어로, 그러나 고르는 것은
            # 그 언어 자체**다. 그래서 `native`를 함께 보여 준다("Spanish / Español").
            {"type": "actions", "items": [
                {"label": _t(ui, spec["label"]), "tool": self.name,
                 "style": "primary" if key == data["language"] else "ghost",
                 "args": {"action": "set", "language": key, "_tab": "settings"}}
                for key, spec in list(LANGUAGES.items())[:8]]},
            {"type": "actions", "items": [
                {"label": lv, "tool": self.name,
                 "style": "primary" if lv == data["level"] else "ghost",
                 "args": {"action": "set", "level": lv, "_tab": "settings"}}
                for lv in LEVELS]},
            {"type": "list", "items": [{"text": f"{lv} — {_t(ui, desc)}", "tone": "muted"}
                                       for lv, desc in LEVELS.items()]},
        ]
