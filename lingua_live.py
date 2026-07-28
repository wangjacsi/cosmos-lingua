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

의존성은 cosmos.contracts와 표준 라이브러리뿐이다.
"""
from __future__ import annotations

import json
import time
import uuid

from cosmos.contracts import Plugin, ToolContext

# ── 어휘: 전부 단일 진실원. 새 언어·모드·상황은 여기 한 줄이면 UI까지 자동 반영된다 ──
LANGUAGES: dict[str, dict] = {
    "en": {"label": "영어",     "native": "English",  "locale": "en-US"},
    "es": {"label": "스페인어", "native": "Español",  "locale": "es-ES"},
    "ja": {"label": "일본어",   "native": "日本語",    "locale": "ja-JP"},
    "zh": {"label": "중국어",   "native": "中文",      "locale": "zh-CN"},
    "de": {"label": "독일어",   "native": "Deutsch",  "locale": "de-DE"},
    "fr": {"label": "프랑스어", "native": "Français", "locale": "fr-FR"},
    "ko": {"label": "한국어",   "native": "한국어",    "locale": "ko-KR"},
    "ar": {"label": "아랍어",   "native": "العربية",  "locale": "ar-SA", "rtl": True},
    "it": {"label": "이탈리아어", "native": "Italiano", "locale": "it-IT"},
    "pt": {"label": "포르투갈어", "native": "Português", "locale": "pt-BR"},
    "ru": {"label": "러시아어", "native": "Русский",  "locale": "ru-RU"},
}

LEVELS: dict[str, str] = {
    "A1": "생존 표현 — 인사·주문·길찾기",
    "A2": "일상 대화 — 짧은 문장으로 하루를 말한다",
    "B1": "의견 말하기 — 이유를 붙여 설명한다",
    "B2": "토론 — 추상적 주제를 다룬다",
    "C1": "정교함 — 뉘앙스·관용·격식을 가른다",
}

MODES: dict[str, dict] = {
    "chat":   {"label": "자유 회화", "desc": "관심사로 그냥 떠든다 — 발화량이 목적"},
    "scene":  {"label": "상황별",    "desc": "역할극으로 실제 상황을 예행연습한다"},
    "drill":  {"label": "집중 훈련", "desc": "내가 반복해 틀리는 것만 집중적으로"},
    "review": {"label": "복습",      "desc": "복습 큐만 — 잊기 직전에 다시 만난다"},
    "shadow": {"label": "섀도잉",    "desc": "듣고 그대로 따라 말한다 — 발음·리듬"},
}

SCENES: dict[str, str] = {
    "airport":    "공항 — 체크인·환승·수하물",
    "restaurant": "식당 — 주문·요청·계산",
    "hotel":      "호텔 — 체크인·요청·문제 해결",
    "shopping":   "쇼핑 — 가격·교환·환불",
    "hospital":   "병원 — 증상 설명·처방",
    "interview":  "면접 — 자기소개·경험·질문",
    "meeting":    "회의 — 의견·반대·정리",
    "phone":      "전화 — 안 보이는 상대와의 대화",
    "smalltalk":  "스몰토크 — 날씨·주말·근황",
    "directions": "길찾기 — 묻고 알아듣기",
}

# 교정 정책 — **이 에이전트에서 가장 중요한 설정 하나**.
# 교정을 언제 어떻게 주느냐가 학습 곡선을 바꾼다(README §철학 ①).
POLICIES: dict[str, dict] = {
    "flow": {
        "label": "흐름 우선",
        "desc": "말로는 절대 끊지 않는다. 교정은 화면 카드로만 — 자신감이 먼저인 단계",
        "instruction": "NEVER interrupt to correct. Do not mention mistakes aloud. "
                       "Log them silently with note_error and keep the conversation moving. "
                       "Praise attempts, not accuracy.",
    },
    "recast": {
        "label": "되풀이(기본)",
        "desc": "자연스럽게 올바른 형태로 되받아 준다 — 대화는 끊기지 않는다",
        "instruction": "Do not stop the conversation. When the learner makes a mistake, "
                       "reply naturally but REPEAT their idea back using the correct form "
                       "(a recast), then continue. Log it with note_error. "
                       "Never lecture mid-flow.",
    },
    "focus": {
        "label": "즉시 교정",
        "desc": "중요한 오류에서 즉시 끊고 다시 말하게 한다 — 시험·상급자용",
        "instruction": "When a mistake blocks meaning or repeats a known error, stop the "
                       "flow: name the error briefly, give the correct form, and ask the "
                       "learner to say the whole sentence again (pushed output). "
                       "Then resume. Max 3 interruptions per session.",
    },
}

ERROR_KINDS: dict[str, str] = {
    "grammar": "문법", "vocab": "어휘", "pronunciation": "발음",
    "register": "말투·격식", "fluency": "유창성",
}

# 약점 축 → **다음에 무엇을 할지**. 처방이 철학에서 나온다는 것이 여기서 드러난다:
# 유창성이 약하면 교정을 더 하는 게 아니라 **덜 한다**(말이 멈추면 학습도 멈추므로).
PRESCRIPTIONS: dict[str, dict] = {
    "grammar": {"mode": "drill", "policy": None,
                "say": "문법 오류가 가장 많습니다 — 다음 세션은 집중 훈련으로 "
                       "같은 구조를 여러 상황에서 반복합니다."},
    "vocab": {"mode": "scene", "policy": None,
              "say": "어휘가 병목입니다 — 상황극으로 옮겨 필요한 말을 실제로 써 보게 합니다."},
    "pronunciation": {"mode": "shadow", "policy": None,
                      "say": "발음·리듬이 약합니다 — 섀도잉으로 듣고 따라 말하기를 늘립니다."},
    "register": {"mode": "scene", "policy": "focus",
                 "say": "말투·격식에서 어긋납니다 — 면접·회의 상황에서 즉시 교정으로 잡습니다."},
    "fluency": {"mode": "chat", "policy": "flow",
                "say": "말이 자주 끊깁니다 — 교정을 낮추고 발화량을 먼저 회복합니다."},
}

PROBE_EVERY_TURNS = 6        # 몇 턴마다 난이도를 하나 심을지(대화를 시험처럼 만들지 않는 간격)
PROBE_UP = 0.8               # 이 이상 통과하면 한 단계 위로
PROBE_DOWN = 0.4             # 이 이하면 한 단계 아래로

# 간격 반복(세션 단위). 짧게 시작해 점점 벌린다 — 잊기 직전에 다시 만나는 게 목적이다.
SRS_INTERVALS = (1, 3, 7, 16, 35)
MAX_FOCUS_ITEMS = 3          # 한 세션에 다루는 교정 항목 상한(철학 ④)
PROMOTE_AFTER = 2            # 같은 오류가 이만큼 반복되면 복습 큐로 승격


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


class LinguaLive(Plugin):
    name = "lingua"
    version = "0.1.0"
    description = (
        "Real-time language tutor. Call this at the START of any language-practice "
        "conversation (action=start) to load the learner's profile, review queue and "
        "the teaching policy you must follow. During practice, call action=note_error "
        "every time the learner makes a mistake, and action=note_word when a word is "
        "worth remembering. Call action=finish to close the session. "
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
            "examples": {"type": "ARRAY", "description": "Example sentences using it",
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
    capabilities = []          # 표준 역량 중 쓰는 것이 없다 — 학습 기록은 자기 데이터 폴더에만 남는다
    requires_desktop = False
    view_title = "🗣 Lingua Live"

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
        suggest, why = "", ""
        if rate is not None and len(recent) >= 3:
            if rate >= PROBE_UP and idx < len(order) - 1:
                suggest, why = order[idx + 1], f"한 단계 위 표현을 {rate:.0%} 소화했습니다"
            elif rate <= PROBE_DOWN and idx > 0:
                suggest, why = order[idx - 1], f"한 단계 위 표현 통과율이 {rate:.0%}입니다"
        if not suggest and review_rate is not None and review_rate <= 0.4 and idx > 0:
            suggest, why = order[idx - 1], f"복습 정답률이 {review_rate:.0%}입니다"

        plan = PRESCRIPTIONS.get(weakest) if weakest else None
        return {
            "probe_rate": rate, "probes": len(recent),
            "axes": axes, "weakest": weakest,
            "review_rate": review_rate, "cards": len(scope),
            "suggest": suggest, "why": why,
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
        ctx.write_log(f"[lingua] {', '.join(changed) or '변경 없음'}")
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

        lines = [
            f"[LINGUA LIVE — session #{data['session']}]",
            f"Target language: {lang['native']} ({data['language']}). "
            f"Learner level: {data['level']} — {LEVELS[data['level']]}",
            f"Mode: {mode['label']} — {mode['desc']}",
        ]
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
            "TEACHING RULES (follow strictly — they come from the learner's chosen policy):",
            f"- Correction policy: {policy['label']} — {policy['instruction']}",
            "- Speak mostly in the target language, one step above the learner's level "
            "(i+1). Keep your turns SHORT so the learner talks more than you do.",
            "- Explanations of grammar/meaning go in the learner's own language, briefly.",
            "- Ask a question at the end of almost every turn — silence kills practice.",
            "- Call note_error(said, correct, kind, note) for EVERY mistake you notice, "
            "even when the policy tells you not to mention it aloud. The screen shows it.",
            "- Call note_word(term, reading, meaning, examples) when a word is worth "
            "keeping. Give 2 example sentences that use it in a real situation.",
            f"- Focus on at most {MAX_FOCUS_ITEMS} teaching points this session. "
            "Ignore minor slips that do not block meaning.",
            "- Call finish when the learner wants to stop.",
            "",
            "CONTINUOUS LEVEL MEASUREMENT (do this without ever calling it a test):",
            f"- About every {PROBE_EVERY_TURNS} turns, plant ONE structure or word from "
            f"the level above {data['level']} inside a normal sentence. Do not announce "
            "it. Watch whether the learner understands it and can respond.",
            "- Immediately after, call note_probe(probe_level, passed, note) with what you "
            "planted and whether they handled it.",
            "- If they pass two probes in a row, RAISE your own speech to that level for "
            "the rest of the session. If they miss two in a row, drop back a level and "
            "shorten your sentences. Adapt within the conversation, not after it.",
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
            lines.append(f"NOTE: measurements suggest level {report['suggest']} "
                         f"({report['why']}) — ask the learner before changing it.")
        if report["weakest"] and report["prescription"]:
            lines.append(f"WEAKEST AXIS so far: {ERROR_KINDS[report['weakest']]} — "
                         f"{report['prescription']['say']}")

        ctx.write_log(f"[lingua] 세션 #{data['session']} · {lang['label']} · "
                      f"{mode['label']} · 교정 {policy['label']} · 복습 {len(due)}건")
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

        ctx.write_log(f"[lingua] ✎ {said or '(발화)'} → {correct}"
                      + (f" · {note}" if note else "")
                      + (f" · 반복 {item['seen']}회 → 복습 큐 승격" if promoted else ""))
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
        ctx.write_log(f"[lingua] {'○' if ok else '✕'} 복습 {label} "
                      f"(box {item['box']}/{len(SRS_INTERVALS)})")
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
        ctx.write_log(f"[lingua] {'✓' if passed else '·'} 난이도 {level} "
                      f"{'소화' if passed else '미소화'}")
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
        ctx.write_log(f"[lingua] 세션 #{data['session']} 종료 — 카드 {len(cards)}장 · "
                      f"복습 대기 {due_next}건"
                      + (f" · 약점 {ERROR_KINDS[overall['weakest']]}" if overall["weakest"] else "")
                      + (f" · 다음 모드 {MODES[data['mode']]['label']}" if plan else ""))

        summary = [f"Session #{data['session']} closed. {len(cards)} card(s), "
                   f"{due_next} item(s) in the review queue.",
                   "", "Report this back to the learner in THEIR language, briefly:"]
        if report["probe_rate"] is not None:
            summary.append(f"  · 이번 대화에서 한 단계 위 표현 소화율 "
                           f"{report['probe_rate']:.0%} ({report['probes']}회 측정)")
        if any(report["axes"].values()):
            summary.append("  · 오류 분포: " + ", ".join(
                f"{ERROR_KINDS[k]} {v}건" for k, v in report["axes"].items() if v))
        for item in cards[:MAX_FOCUS_ITEMS]:
            summary.append(f"  · {item.get('correct') or item.get('term')}"
                           f" — {item.get('note') or item.get('meaning') or ''}")
        if plan:
            summary.append(f"  · 보충할 것: {plan['say']} "
                           f"(다음 세션 모드를 {MODES[data['mode']]['label']}으로 맞춰 두었습니다)")
        if overall["suggest"]:
            summary.append(f"  · 레벨 재분석: {data['level']} → {overall['suggest']} "
                           f"({overall['why']}). 바꿀지 물어보고, 동의하면 "
                           f"set(level={overall['suggest']})을 호출하세요.")
        summary.append("Then tell them when the cards come back (spaced repetition).")
        return "\n".join(summary)

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
        due = self._due(data)
        tabs = (("today", "오늘"), ("review", f"복습 {len(due)}"),
                ("report", "분석"), ("settings", "설정"))
        blocks: list[dict] = [{
            "type": "chips", "items": [
                {"label": "언어", "value": f"{lang['label']} {lang['native']}"},
                {"label": "레벨", "value": data["level"]},
                {"label": "모드", "value": MODES[data["mode"]]["label"]},
                {"label": "교정", "value": POLICIES[data["policy"]]["label"],
                 "tone": "warn" if data["policy"] == "focus" else "good"},
                {"label": "세션", "value": f"#{data['session']}"},
            ]}, {
            "type": "actions", "items": [
                {"label": label, "tool": self.name,
                 "args": {"action": "status", "_tab": key},
                 "style": "primary" if tab == key else "ghost"}
                for key, label in tabs]}]

        if tab == "review":
            blocks += self._review_blocks(data, due, code)
        elif tab == "settings":
            blocks += self._settings_blocks(data)
        elif tab == "report":
            blocks += self._report_blocks(data)
        else:
            blocks += self._today_blocks(data, code)

        graduated = sum(1 for i in data["items"] if i.get("graduated"))
        total = len(data["items"])
        return {
            "title": "🗣 Lingua Live",
            "subtitle": f"{lang['label']} · {data['level']} · "
                        f"{MODES[data['mode']]['label']} · 카드 {total}장 · 졸업 {graduated}",
            "params": {"tab": tab},
            "blocks": blocks,
        }

    def _card(self, item: dict, code: str) -> dict:
        if item.get("type") == "word":
            return {"title": item.get("term", ""), "reading": item.get("reading", ""),
                    "subtitle": item.get("meaning", ""), "body": item.get("note", ""),
                    "lang": code, "tone": "info",
                    "tags": [f"box {item.get('box', 0)}/{len(SRS_INTERVALS)}"],
                    "examples": [{"text": e, "translation": ""}
                                 for e in item.get("examples") or []]}
        return {"title": item.get("correct", ""), "reading": "",
                "subtitle": (f"내가 말한 것: {item.get('said')}" if item.get("said") else ""),
                "body": item.get("note", ""), "lang": code, "tone": "warn",
                "tags": [ERROR_KINDS.get(item.get("kind", ""), ""),
                         f"{item.get('seen', 1)}회",
                         f"box {item.get('box', 0)}/{len(SRS_INTERVALS)}"],
                "examples": [{"text": e, "translation": ""}
                             for e in item.get("examples") or []]}

    def _today_blocks(self, data: dict, code: str) -> list[dict]:
        cards = [i for i in data["items"] if i["id"] in data["today"]]
        if not cards:
            return [{"type": "text", "tone": "muted",
                     "text": "아직 오늘의 카드가 없습니다. 대화를 시작하면 교정과 새 단어가 "
                             "여기 쌓입니다 — 🔊를 누르면 발음을 다시 들을 수 있어요."},
                    {"type": "actions", "items": [
                        {"label": "회화 시작", "tool": self.name, "style": "primary",
                         "args": {"action": "start", "mode": "chat"}},
                        {"label": "상황극 시작", "tool": self.name,
                         "args": {"action": "start", "mode": "scene"}},
                        {"label": "복습만 하기", "tool": self.name,
                         "args": {"action": "start", "mode": "review"}}]}]
        return [{"type": "text", "text": f"오늘의 카드 {len(cards)}장 — "
                                         "노란 카드는 교정, 파란 카드는 새 단어입니다."},
                {"type": "cards", "items": [self._card(i, code) for i in cards]}]

    def _review_blocks(self, data: dict, due: list[dict], code: str) -> list[dict]:
        queued = [i for i in data["items"]
                  if i["lang"] == code and i.get("box") and not i.get("graduated")]
        blocks: list[dict] = [{
            "type": "progress", "label": "복습 큐",
            "value": (len(queued) - len(due)) / len(queued) if queued else 0.0,
            "caption": f"지금 볼 것 {len(due)}개 · 대기 {len(queued)}개 · "
                       f"간격 {'→'.join(str(s) for s in SRS_INTERVALS)} 세션"}]
        if due:
            blocks.append({"type": "cards",
                           "items": [self._card(i, code) for i in due[:10]]})
            blocks.append({"type": "actions", "items": [
                {"label": "복습 시작", "tool": self.name, "style": "primary",
                 "args": {"action": "start", "mode": "review"}}]})
        else:
            blocks.append({"type": "text", "tone": "good",
                           "text": "지금 복습할 항목이 없습니다. 잊을 때쯤 다시 꺼내 드릴게요."})
        if queued:
            blocks.append({"type": "list", "items": [
                {"text": i.get("correct") or i.get("term", ""),
                 "sub": f"box {i.get('box')}/{len(SRS_INTERVALS)} · "
                        f"{max(0, i.get('due', 0) - data['session'])} 세션 뒤",
                 "lang": code, "tone": "muted"} for i in queued[:20]]})
        return blocks

    def _report_blocks(self, data: dict) -> list[dict]:
        """분석 탭 — 무엇이 약하고 다음에 무엇을 할지. 숫자가 아니라 **처방**이 결론이다."""
        report = self._analyze(data)
        blocks: list[dict] = []
        if report["probe_rate"] is not None:
            blocks.append({"type": "progress", "label": "한 단계 위 표현 소화율",
                           "value": report["probe_rate"],
                           "caption": f"대화 중 {report['probes']}회 측정 — "
                                      f"시험이 아니라 대화 안에 심어 잰 값입니다"})
        if report["review_rate"] is not None:
            blocks.append({"type": "progress", "label": "지난 교정 재현율",
                           "value": report["review_rate"],
                           "caption": "복습에서 실제로 다시 해낸 비율"})
        total = sum(report["axes"].values())
        if total:
            blocks.append({"type": "list", "items": [
                {"text": f"{ERROR_KINDS[k]}  {'█' * min(20, v)} {v}건",
                 "tone": "warn" if k == report["weakest"] else "muted"}
                for k, v in report["axes"].items() if v]})
        if report["prescription"]:
            blocks.append({"type": "text", "tone": "info",
                           "text": "보충할 것 — " + report["prescription"]["say"]})
            blocks.append({"type": "actions", "items": [
                {"label": f"{MODES[report['prescription']['mode']]['label']}으로 시작",
                 "tool": self.name, "style": "primary",
                 "args": {"action": "start", "mode": report["prescription"]["mode"],
                          "_tab": "today"}}]})
        if report["suggest"]:
            blocks.append({"type": "text", "tone": "good",
                           "text": f"레벨 재분석: {report['level']} → {report['suggest']} "
                                   f"({report['why']})"})
            blocks.append({"type": "actions", "items": [
                {"label": f"{report['suggest']}로 올리기" if report["suggest"] > report["level"]
                 else f"{report['suggest']}로 내리기",
                 "tool": self.name, "style": "primary",
                 "args": {"action": "set", "level": report["suggest"], "_tab": "report"}}]})
        if not blocks:
            blocks.append({"type": "text", "tone": "muted",
                           "text": "아직 분석할 대화가 없습니다. 몇 번 대화하면 "
                                   "약점 축과 레벨 추정이 여기 나타납니다."})
        history = [h for h in data["history"]][-8:]
        if history:
            blocks.append({"type": "list", "items": [
                {"text": f"세션 #{h['session']} · {h.get('level','')} · 카드 {h.get('cards',0)}장"
                         + (f" · 약점 {ERROR_KINDS.get(h.get('weakest'),'')}"
                            if h.get("weakest") else ""),
                 "sub": h.get("at", ""), "tone": "muted"} for h in reversed(history)]})
        return blocks

    def _settings_blocks(self, data: dict) -> list[dict]:
        return [
            {"type": "text", "text": "설정은 넷뿐입니다 — 나머지는 학습 철학이 정합니다. "
                                     "(README의 방법론 참고)"},
            {"type": "text", "tone": "muted",
             "text": f"교정 방식: {POLICIES[data['policy']]['desc']}"},
            {"type": "actions", "items": [
                {"label": f"교정 {p['label']}", "tool": self.name,
                 "style": "primary" if key == data["policy"] else "ghost",
                 "args": {"action": "set", "policy": key, "_tab": "settings"}}
                for key, p in POLICIES.items()]},
            {"type": "actions", "items": [
                {"label": m["label"], "tool": self.name,
                 "style": "primary" if key == data["mode"] else "ghost",
                 "args": {"action": "set", "mode": key, "_tab": "settings"}}
                for key, m in MODES.items()]},
            {"type": "actions", "items": [
                {"label": spec["label"], "tool": self.name,
                 "style": "primary" if key == data["language"] else "ghost",
                 "args": {"action": "set", "language": key, "_tab": "settings"}}
                for key, spec in list(LANGUAGES.items())[:8]]},
            {"type": "actions", "items": [
                {"label": lv, "tool": self.name,
                 "style": "primary" if lv == data["level"] else "ghost",
                 "args": {"action": "set", "level": lv, "_tab": "settings"}}
                for lv in LEVELS]},
            {"type": "list", "items": [{"text": f"{lv} — {desc}", "tone": "muted"}
                                       for lv, desc in LEVELS.items()]},
        ]
