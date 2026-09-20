"""Lingua Live의 화면 어휘 — **영어가 원문이고 번역은 여기 모인다**.

## 왜 이 파일이 있나

v0.4.0까지 이 에이전트의 화면 어휘는 **한국어로 박혀 있었다.** 한국어를 읽지 못하는
사용자는 설치해도 쓸 수 없었다 — 마켓에 올라간 물건으로서는 반쪽이었다.

원인은 개발자의 게으름이 아니라 **통로의 부재**였다. 코스모스의 `AGENT_GUIDE.md`는
*"`ctx`가 알려 주는 사용자 언어에 맞춰 골라 넣어라"* 고 적어 뒀지만 정작 `ctx`에는
언어 칸이 없었다. 2026-08-03에 `ToolContext.lang`·`ToolContext.localized()`가 생기면서
이 파일이 가능해졌다.

## 구조 — 코스모스 코어와 **같은 패턴**이다

    영어 원문이 키 · 언어별 카탈로그가 값

코어의 `cosmos/i18n/*.json`과 같은 규칙이라 배울 것이 하나뿐이다. 새 언어는
`TRANSLATIONS`에 칸 하나 늘리면 되고(원칙 1), **번역이 없으면 영어가 그대로** 나온다 —
감추지 않는다. 빈칸은 사용자가 고장으로 읽는다.

## 두 언어를 섞지 마라 (함정 28)

이 에이전트에는 언어가 **둘** 있다:

- **배우는 언어**(`LANGUAGES` 표의 키) — 스페인어를 배운다
- **읽는 언어**(`ctx.lang`) — 설명은 한국어로 읽는다

이 파일이 옮기는 것은 **뒤쪽뿐**이다. 앞쪽을 옮기면 스페인어를 배우는 사람에게
설명까지 스페인어로 나간다.

## 모델에게 가는 문장은 여기 없다

교정 지침(`POLICIES[*]["instruction"]`)·세션 요약처럼 **모델이 읽는 것**은 영어
하나로 둔다. 모델은 그것을 읽고 **사용자의 언어로 말한다** — 지침까지 번역하면
번역 품질이 곧 교습 품질이 되고, 언어마다 튜터가 달라진다.
"""
from __future__ import annotations

# ── 번역 ────────────────────────────────────────────────────────────────────
#
# ⚠️ 원어민 검수 전이다(코스모스 §3 ⑥과 같은 상태). 뜻이 틀린 것을 발견하면
# 이 표만 고치면 된다 — 코드는 건드리지 않는다.
TRANSLATIONS: dict[str, dict[str, str]] = {
    "ko": {
        # 배우는 언어의 이름
        "English": "영어", "Spanish": "스페인어", "Japanese": "일본어",
        "Chinese": "중국어", "German": "독일어", "French": "프랑스어",
        "Korean": "한국어", "Arabic": "아랍어", "Italian": "이탈리아어",
        "Portuguese": "포르투갈어", "Russian": "러시아어",
        # 레벨
        "Survival — greetings, ordering, directions": "생존 표현 — 인사·주문·길찾기",
        "Everyday talk — say how your day went in short sentences":
            "일상 대화 — 짧은 문장으로 하루를 말한다",
        "Opinions — explain with reasons": "의견 말하기 — 이유를 붙여 설명한다",
        "Discussion — handle abstract topics": "토론 — 추상적 주제를 다룬다",
        "Precision — nuance, idiom and register": "정교함 — 뉘앙스·관용·격식을 가른다",
        # 모드
        "Free talk": "자유 회화",
        "Talk about whatever interests you — how much you say is the point":
            "관심사로 그냥 떠든다 — 발화량이 목적",
        "Scenes": "상황별",
        "Rehearse a real situation as role-play": "역할극으로 실제 상황을 예행연습한다",
        "Drills": "집중 훈련",
        "Only the things you keep getting wrong": "내가 반복해 틀리는 것만 집중적으로",
        "Review": "복습",
        "Review queue only — meet it again just before you forget":
            "복습 큐만 — 잊기 직전에 다시 만난다",
        "Shadowing": "섀도잉",
        "Listen and say it back exactly — pronunciation and rhythm":
            "듣고 그대로 따라 말한다 — 발음·리듬",
        # 상황
        "Airport — check-in, transfers, baggage": "공항 — 체크인·환승·수하물",
        "Restaurant — ordering, requests, paying": "식당 — 주문·요청·계산",
        "Hotel — check-in, requests, problems": "호텔 — 체크인·요청·문제 해결",
        "Shopping — prices, exchanges, refunds": "쇼핑 — 가격·교환·환불",
        "Clinic — describing symptoms, prescriptions": "병원 — 증상 설명·처방",
        "Interview — introducing yourself, experience, questions":
            "면접 — 자기소개·경험·질문",
        "Meeting — opinions, disagreement, wrapping up": "회의 — 의견·반대·정리",
        "Phone — talking to someone you cannot see": "전화 — 안 보이는 상대와의 대화",
        "Small talk — weather, the weekend, catching up": "스몰토크 — 날씨·주말·근황",
        "Directions — asking and understanding the answer": "길찾기 — 묻고 알아듣기",
        # 교정 정책
        "Flow first": "흐름 우선",
        "Never interrupts you. Corrections appear only as cards on screen — "
        "for when confidence has to come first":
            "말로는 절대 끊지 않는다. 교정은 화면 카드로만 — 자신감이 먼저인 단계",
        "Recast (default)": "되풀이(기본)",
        "Says your idea back in the correct form — the conversation never stops":
            "자연스럽게 올바른 형태로 되받아 준다 — 대화는 끊기지 않는다",
        "Correct now": "즉시 교정",
        "Stops at important errors and has you say it again — for exams and advanced learners":
            "중요한 오류에서 즉시 끊고 다시 말하게 한다 — 시험·상급자용",
        # 오류 축
        "Grammar": "문법", "Vocabulary": "어휘", "Pronunciation": "발음",
        "Register": "말투·격식", "Fluency": "유창성",
        # 처방
        "Grammar errors dominate — the next session drills the same structures "
        "across different situations.":
            "문법 오류가 가장 많습니다 — 다음 세션은 집중 훈련으로 같은 구조를 "
            "여러 상황에서 반복합니다.",
        "Vocabulary is the bottleneck — moving to scenes so you actually use "
        "the words you need.":
            "어휘가 병목입니다 — 상황극으로 옮겨 필요한 말을 실제로 써 보게 합니다.",
        "Pronunciation and rhythm are weak — more shadowing: listen, then say it back.":
            "발음·리듬이 약합니다 — 섀도잉으로 듣고 따라 말하기를 늘립니다.",
        "Register slips — interviews and meetings with immediate correction will fix it.":
            "말투·격식에서 어긋납니다 — 면접·회의 상황에서 즉시 교정으로 잡습니다.",
        "You stall often — lowering correction to get your speaking volume back first.":
            "말이 자주 끊깁니다 — 교정을 낮추고 발화량을 먼저 회복합니다.",
        # 화면 — 탭·요약
        "Today": "오늘", "Report": "분석", "Settings": "설정",
        "Language": "언어", "Level": "레벨", "Mode": "모드",
        "Correction": "교정", "Session": "세션",
        "{cards} cards · {graduated} graduated": "카드 {cards}장 · 졸업 {graduated}",
        "Review {count}": "복습 {count}",
        # 화면 — 오늘
        "Start talking and your corrections and new words pile up here. "
        "Nothing interrupts you while you speak — anything to fix appears quietly "
        "on this screen. Tap 🔊 to hear it again.":
            "대화를 시작하면 교정과 새 단어가 여기 쌓입니다. 말하는 도중에는 끊지 "
            "않습니다 — 고칠 것은 이 화면에만 조용히 올라옵니다. 🔊로 발음을 다시 "
            "들을 수 있어요.",
        "Start talking": "회화 시작",
        "Role-play": "상황극",
        "Corrections today": "오늘 교정",
        "New words": "새 단어",
        "Waiting for review": "복습 대기",
        "Words you met today": "오늘 만난 표현",
        "Review these": "이걸로 복습하기",
        "Wrap up today": "오늘 마무리",
        # 화면 — 복습
        "Review queue": "복습 큐",
        "{due} to see now · {queued} waiting · intervals {intervals} sessions":
            "지금 볼 것 {due}개 · 대기 {queued}개 · 간격 {intervals} 세션",
        "Start review": "복습 시작",
        "Nothing to review right now. It will come back just before you forget.":
            "지금 복습할 항목이 없습니다. 잊을 때쯤 다시 꺼내 드릴게요.",
        "box {box}/{total} · in {sessions} sessions": "box {box}/{total} · {sessions} 세션 뒤",
        "review {box}/{total}": "복습 {box}/{total}",
        "seen {count}×": "{count}번째",
        # 화면 — 분석
        "How much of the next level you handled": "한 단계 위 표현 소화율",
        "Measured {probes}× mid-conversation — planted in the talk, not a test":
            "대화 중 {probes}회 측정 — 시험이 아니라 대화 안에 심어 잰 값입니다",
        "Past corrections you got right again": "지난 교정 재현율",
        "How often you actually did it right in review": "복습에서 실제로 다시 해낸 비율",
        "{count} times": "{count}건",
        "What to shore up — ": "보충할 것 — ",
        "Start {mode}": "{mode}으로 시작",
        "Level re-read: {level} → {suggest} ({why})":
            "레벨 재분석: {level} → {suggest} ({why})",
        "Move up to {level}": "{level}로 올리기",
        "Move down to {level}": "{level}로 내리기",
        "No conversations to analyse yet. After a few talks your weak axis and "
        "level estimate appear here.":
            "아직 분석할 대화가 없습니다. 몇 번 대화하면 약점 축과 레벨 추정이 "
            "여기 나타납니다.",
        "Session #{session} · {level} · {cards} cards":
            "세션 #{session} · {level} · 카드 {cards}장",
        " · weak: {axis}": " · 약점 {axis}",
        "You handled {rate} of the next level up": "한 단계 위 표현을 {rate} 소화했습니다",
        "You cleared {rate} of the next level up": "한 단계 위 표현 통과율이 {rate}입니다",
        "Review accuracy is {rate}": "복습 정답률이 {rate}입니다",
        # 화면 — 설정
        "Four settings, and that is all — the rest is decided by the teaching method. "
        "(See the README.)":
            "설정은 넷뿐입니다 — 나머지는 학습 철학이 정합니다. (README의 방법론 참고)",
        "Correction style: ": "교정 방식: ",
        "Correction {style}": "교정 {style}",
        # 로그 — 대화 피드에 한 줄로 남는다(사용자가 읽는다)
        "Session #{session} · {language} · {mode} · correction {policy} · {due} to review":
            "세션 #{session} · {language} · {mode} · 교정 {policy} · 복습 {due}건",
        "1 correction": "교정 1건",
        "promoted to the review queue": "복습 큐 승격",
        "review {label} (box {box}/{total})": "복습 {label} (box {box}/{total})",
        "level {level} handled": "난이도 {level} 소화",
        "level {level} not handled": "난이도 {level} 미소화",
        "Session #{session} closed — {cards} cards · {due} awaiting review":
            "세션 #{session} 종료 — 카드 {cards}장 · 복습 대기 {due}건",
        " · next mode {mode}": " · 다음 모드 {mode}",
        "{count} corrections — see them on the 🧩 screen":
            "교정 {count}건 — 🧩 화면에서 확인하세요",
        "no change": "변경 없음",
    },
    "ja": {
        "English": "英語", "Spanish": "スペイン語", "Japanese": "日本語",
        "Chinese": "中国語", "German": "ドイツ語", "French": "フランス語",
        "Korean": "韓国語", "Arabic": "アラビア語", "Italian": "イタリア語",
        "Portuguese": "ポルトガル語", "Russian": "ロシア語",
        "Survival — greetings, ordering, directions": "サバイバル — あいさつ・注文・道案内",
        "Everyday talk — say how your day went in short sentences":
            "日常会話 — 短い文で一日を話す",
        "Opinions — explain with reasons": "意見を言う — 理由をつけて説明する",
        "Discussion — handle abstract topics": "議論 — 抽象的な話題を扱う",
        "Precision — nuance, idiom and register": "精密さ — ニュアンス・慣用・敬体を使い分ける",
        "Free talk": "フリートーク",
        "Talk about whatever interests you — how much you say is the point":
            "興味のあることを自由に話す — 発話量が目的",
        "Scenes": "場面別",
        "Rehearse a real situation as role-play": "ロールプレイで実際の場面を予行する",
        "Drills": "集中トレーニング",
        "Only the things you keep getting wrong": "繰り返し間違えるものだけを集中的に",
        "Review": "復習",
        "Review queue only — meet it again just before you forget":
            "復習キューのみ — 忘れる直前にもう一度出会う",
        "Shadowing": "シャドーイング",
        "Listen and say it back exactly — pronunciation and rhythm":
            "聞いてそのまま繰り返す — 発音・リズム",
        "Airport — check-in, transfers, baggage": "空港 — チェックイン・乗り継ぎ・荷物",
        "Restaurant — ordering, requests, paying": "レストラン — 注文・依頼・会計",
        "Hotel — check-in, requests, problems": "ホテル — チェックイン・依頼・トラブル対応",
        "Shopping — prices, exchanges, refunds": "買い物 — 値段・交換・返金",
        "Clinic — describing symptoms, prescriptions": "病院 — 症状の説明・処方",
        "Interview — introducing yourself, experience, questions":
            "面接 — 自己紹介・経験・質問",
        "Meeting — opinions, disagreement, wrapping up": "会議 — 意見・反対・まとめ",
        "Phone — talking to someone you cannot see": "電話 — 相手が見えない会話",
        "Small talk — weather, the weekend, catching up": "雑談 — 天気・週末・近況",
        "Directions — asking and understanding the answer": "道案内 — 尋ねて聞き取る",
        "Flow first": "流れ優先",
        "Never interrupts you. Corrections appear only as cards on screen — "
        "for when confidence has to come first":
            "話をさえぎりません。訂正は画面のカードだけ — 自信が先の段階に",
        "Recast (default)": "言い直し（既定）",
        "Says your idea back in the correct form — the conversation never stops":
            "正しい形で自然に言い返します — 会話は止まりません",
        "Correct now": "即時訂正",
        "Stops at important errors and has you say it again — for exams and advanced learners":
            "重要な誤りで止めて言い直させます — 試験・上級者向け",
        "Grammar": "文法", "Vocabulary": "語彙", "Pronunciation": "発音",
        "Register": "話し方・敬体", "Fluency": "流暢さ",
        "Grammar errors dominate — the next session drills the same structures "
        "across different situations.":
            "文法の誤りが最も多いです — 次のセッションは集中トレーニングで同じ構造を"
            "いろいろな場面で繰り返します。",
        "Vocabulary is the bottleneck — moving to scenes so you actually use "
        "the words you need.":
            "語彙がボトルネックです — 場面別に移り、必要な言葉を実際に使わせます。",
        "Pronunciation and rhythm are weak — more shadowing: listen, then say it back.":
            "発音・リズムが弱いです — シャドーイングで聞いて繰り返す量を増やします。",
        "Register slips — interviews and meetings with immediate correction will fix it.":
            "話し方・敬体がずれています — 面接・会議の場面で即時訂正により整えます。",
        "You stall often — lowering correction to get your speaking volume back first.":
            "言葉が詰まりがちです — 訂正を減らし、まず発話量を回復します。",
        "Today": "今日", "Report": "分析", "Settings": "設定",
        "Language": "言語", "Level": "レベル", "Mode": "モード",
        "Correction": "訂正", "Session": "セッション",
        "{cards} cards · {graduated} graduated": "カード {cards}枚 · 卒業 {graduated}",
        "Review {count}": "復習 {count}",
        "Start talking and your corrections and new words pile up here. "
        "Nothing interrupts you while you speak — anything to fix appears quietly "
        "on this screen. Tap 🔊 to hear it again.":
            "話し始めると訂正と新しい語がここに溜まります。話している間はさえぎりません — "
            "直すべきものはこの画面に静かに現れます。🔊で発音をもう一度聞けます。",
        "Start talking": "会話を始める",
        "Role-play": "ロールプレイ",
        "Corrections today": "今日の訂正",
        "New words": "新しい語",
        "Waiting for review": "復習待ち",
        "Words you met today": "今日出会った表現",
        "Review these": "これで復習する",
        "Wrap up today": "今日を締める",
        "Review queue": "復習キュー",
        "{due} to see now · {queued} waiting · intervals {intervals} sessions":
            "今見るもの {due}件 · 待ち {queued}件 · 間隔 {intervals} セッション",
        "Start review": "復習を始める",
        "Nothing to review right now. It will come back just before you forget.":
            "今復習する項目はありません。忘れる頃にまたお出しします。",
        "box {box}/{total} · in {sessions} sessions": "box {box}/{total} · {sessions} セッション後",
        "review {box}/{total}": "復習 {box}/{total}",
        "seen {count}×": "{count}回目",
        "How much of the next level you handled": "一つ上の表現の消化率",
        "Measured {probes}× mid-conversation — planted in the talk, not a test":
            "会話中に {probes}回測定 — 試験ではなく会話に埋めて測った値です",
        "Past corrections you got right again": "過去の訂正の再現率",
        "How often you actually did it right in review": "復習で実際にできた割合",
        "{count} times": "{count}件",
        "What to shore up — ": "補うこと — ",
        "Start {mode}": "{mode}で始める",
        "Level re-read: {level} → {suggest} ({why})":
            "レベル再判定: {level} → {suggest} ({why})",
        "Move up to {level}": "{level}に上げる",
        "Move down to {level}": "{level}に下げる",
        "No conversations to analyse yet. After a few talks your weak axis and "
        "level estimate appear here.":
            "まだ分析する会話がありません。何度か話すと弱点とレベル推定がここに出ます。",
        "Session #{session} · {level} · {cards} cards":
            "セッション #{session} · {level} · カード {cards}枚",
        " · weak: {axis}": " · 弱点 {axis}",
        "You handled {rate} of the next level up": "一つ上の表現を {rate} 消化しました",
        "You cleared {rate} of the next level up": "一つ上の表現の通過率が {rate} です",
        "Review accuracy is {rate}": "復習の正答率が {rate} です",
        "Four settings, and that is all — the rest is decided by the teaching method. "
        "(See the README.)":
            "設定は四つだけです — 残りは学習の考え方が決めます。（README の方法論を参照）",
        "Correction style: ": "訂正の方式: ",
        "Correction {style}": "訂正 {style}",
        "Session #{session} · {language} · {mode} · correction {policy} · {due} to review":
            "セッション #{session} · {language} · {mode} · 訂正 {policy} · 復習 {due}件",
        "1 correction": "訂正 1件",
        "promoted to the review queue": "復習キューへ昇格",
        "review {label} (box {box}/{total})": "復習 {label} (box {box}/{total})",
        "level {level} handled": "難易度 {level} 消化",
        "level {level} not handled": "難易度 {level} 未消化",
        "Session #{session} closed — {cards} cards · {due} awaiting review":
            "セッション #{session} 終了 — カード {cards}枚 · 復習待ち {due}件",
        " · next mode {mode}": " · 次のモード {mode}",
        "{count} corrections — see them on the 🧩 screen":
            "訂正 {count}件 — 🧩 画面で確認してください",
        "no change": "変更なし",
    },
    "es": {
        "English": "Inglés", "Spanish": "Español", "Japanese": "Japonés",
        "Chinese": "Chino", "German": "Alemán", "French": "Francés",
        "Korean": "Coreano", "Arabic": "Árabe", "Italian": "Italiano",
        "Portuguese": "Portugués", "Russian": "Ruso",
        "Survival — greetings, ordering, directions":
            "Supervivencia: saludos, pedidos, direcciones",
        "Everyday talk — say how your day went in short sentences":
            "Conversación diaria: cuenta tu día en frases cortas",
        "Opinions — explain with reasons": "Opiniones: explica con razones",
        "Discussion — handle abstract topics": "Debate: maneja temas abstractos",
        "Precision — nuance, idiom and register": "Precisión: matiz, modismo y registro",
        "Free talk": "Charla libre",
        "Talk about whatever interests you — how much you say is the point":
            "Habla de lo que te interese: lo que cuenta es cuánto hablas",
        "Scenes": "Situaciones",
        "Rehearse a real situation as role-play": "Ensaya una situación real con juego de roles",
        "Drills": "Ejercicios",
        "Only the things you keep getting wrong": "Solo lo que fallas una y otra vez",
        "Review": "Repaso",
        "Review queue only — meet it again just before you forget":
            "Solo la cola de repaso: vuelve justo antes de que lo olvides",
        "Shadowing": "Shadowing",
        "Listen and say it back exactly — pronunciation and rhythm":
            "Escucha y repite exactamente: pronunciación y ritmo",
        "Airport — check-in, transfers, baggage":
            "Aeropuerto: facturación, conexiones, equipaje",
        "Restaurant — ordering, requests, paying": "Restaurante: pedir, peticiones, pagar",
        "Hotel — check-in, requests, problems": "Hotel: entrada, peticiones, problemas",
        "Shopping — prices, exchanges, refunds": "Compras: precios, cambios, devoluciones",
        "Clinic — describing symptoms, prescriptions": "Consulta: describir síntomas, recetas",
        "Interview — introducing yourself, experience, questions":
            "Entrevista: presentarte, experiencia, preguntas",
        "Meeting — opinions, disagreement, wrapping up":
            "Reunión: opiniones, desacuerdo, cierre",
        "Phone — talking to someone you cannot see":
            "Teléfono: hablar con alguien a quien no ves",
        "Small talk — weather, the weekend, catching up":
            "Charla informal: el tiempo, el fin de semana, ponerse al día",
        "Directions — asking and understanding the answer":
            "Direcciones: preguntar y entender la respuesta",
        "Flow first": "Fluidez primero",
        "Never interrupts you. Corrections appear only as cards on screen — "
        "for when confidence has to come first":
            "Nunca te interrumpe. Las correcciones solo aparecen como tarjetas: "
            "para cuando la confianza va primero",
        "Recast (default)": "Reformulación (predeterminado)",
        "Says your idea back in the correct form — the conversation never stops":
            "Repite tu idea en la forma correcta: la conversación no se detiene",
        "Correct now": "Corregir al momento",
        "Stops at important errors and has you say it again — for exams and advanced learners":
            "Se detiene en errores importantes y te hace repetir: para exámenes y nivel avanzado",
        "Grammar": "Gramática", "Vocabulary": "Vocabulario", "Pronunciation": "Pronunciación",
        "Register": "Registro", "Fluency": "Fluidez",
        "Grammar errors dominate — the next session drills the same structures "
        "across different situations.":
            "Predominan los errores de gramática: la próxima sesión practica las mismas "
            "estructuras en distintas situaciones.",
        "Vocabulary is the bottleneck — moving to scenes so you actually use "
        "the words you need.":
            "El vocabulario es el cuello de botella: pasamos a situaciones para que uses "
            "de verdad las palabras que necesitas.",
        "Pronunciation and rhythm are weak — more shadowing: listen, then say it back.":
            "La pronunciación y el ritmo flojean: más shadowing, escuchar y repetir.",
        "Register slips — interviews and meetings with immediate correction will fix it.":
            "El registro se te escapa: entrevistas y reuniones con corrección inmediata lo arreglan.",
        "You stall often — lowering correction to get your speaking volume back first.":
            "Te trabas a menudo: bajamos la corrección para recuperar primero el volumen de habla.",
        "Today": "Hoy", "Report": "Análisis", "Settings": "Ajustes",
        "Language": "Idioma", "Level": "Nivel", "Mode": "Modo",
        "Correction": "Corrección", "Session": "Sesión",
        "{cards} cards · {graduated} graduated": "{cards} tarjetas · {graduated} completadas",
        "Review {count}": "Repaso {count}",
        "Start talking and your corrections and new words pile up here. "
        "Nothing interrupts you while you speak — anything to fix appears quietly "
        "on this screen. Tap 🔊 to hear it again.":
            "Empieza a hablar y aquí se acumulan tus correcciones y palabras nuevas. "
            "Nada te interrumpe mientras hablas: lo que hay que corregir aparece en "
            "silencio en esta pantalla. Toca 🔊 para volver a escucharlo.",
        "Start talking": "Empezar a hablar",
        "Role-play": "Juego de roles",
        "Corrections today": "Correcciones de hoy",
        "New words": "Palabras nuevas",
        "Waiting for review": "Pendientes de repaso",
        "Words you met today": "Expresiones de hoy",
        "Review these": "Repasar esto",
        "Wrap up today": "Cerrar el día",
        "Review queue": "Cola de repaso",
        "{due} to see now · {queued} waiting · intervals {intervals} sessions":
            "{due} para ver ahora · {queued} en espera · intervalos {intervals} sesiones",
        "Start review": "Empezar el repaso",
        "Nothing to review right now. It will come back just before you forget.":
            "Nada que repasar ahora. Volverá justo antes de que lo olvides.",
        "box {box}/{total} · in {sessions} sessions":
            "caja {box}/{total} · dentro de {sessions} sesiones",
        "review {box}/{total}": "repaso {box}/{total}",
        "seen {count}×": "{count}ª vez",
        "How much of the next level you handled": "Cuánto del nivel siguiente manejaste",
        "Measured {probes}× mid-conversation — planted in the talk, not a test":
            "Medido {probes} veces durante la conversación: sembrado en la charla, no un examen",
        "Past corrections you got right again": "Correcciones anteriores acertadas de nuevo",
        "How often you actually did it right in review":
            "Con qué frecuencia lo hiciste bien en el repaso",
        "{count} times": "{count} veces",
        "What to shore up — ": "Qué reforzar: ",
        "Start {mode}": "Empezar {mode}",
        "Level re-read: {level} → {suggest} ({why})":
            "Relectura de nivel: {level} → {suggest} ({why})",
        "Move up to {level}": "Subir a {level}",
        "Move down to {level}": "Bajar a {level}",
        "No conversations to analyse yet. After a few talks your weak axis and "
        "level estimate appear here.":
            "Aún no hay conversaciones que analizar. Tras algunas charlas aparecerán aquí "
            "tu punto débil y la estimación de nivel.",
        "Session #{session} · {level} · {cards} cards":
            "Sesión #{session} · {level} · {cards} tarjetas",
        " · weak: {axis}": " · débil: {axis}",
        "You handled {rate} of the next level up": "Manejaste el {rate} del nivel siguiente",
        "You cleared {rate} of the next level up": "Superaste el {rate} del nivel siguiente",
        "Review accuracy is {rate}": "Tu acierto en el repaso es del {rate}",
        "Four settings, and that is all — the rest is decided by the teaching method. "
        "(See the README.)":
            "Cuatro ajustes y ya está: el resto lo decide el método de enseñanza. "
            "(Consulta el README.)",
        "Correction style: ": "Estilo de corrección: ",
        "Correction {style}": "Corrección {style}",
        "Session #{session} · {language} · {mode} · correction {policy} · {due} to review":
            "Sesión #{session} · {language} · {mode} · corrección {policy} · {due} por repasar",
        "1 correction": "1 corrección",
        "promoted to the review queue": "pasa a la cola de repaso",
        "review {label} (box {box}/{total})": "repaso {label} (caja {box}/{total})",
        "level {level} handled": "nivel {level} superado",
        "level {level} not handled": "nivel {level} no superado",
        "Session #{session} closed — {cards} cards · {due} awaiting review":
            "Sesión #{session} cerrada — {cards} tarjetas · {due} pendientes de repaso",
        " · next mode {mode}": " · siguiente modo {mode}",
        "{count} corrections — see them on the 🧩 screen":
            "{count} correcciones: míralas en la pantalla 🧩",
        "no change": "sin cambios",
    },
    "fr": {
        "English": "Anglais", "Spanish": "Espagnol", "Japanese": "Japonais",
        "Chinese": "Chinois", "German": "Allemand", "French": "Français",
        "Korean": "Coréen", "Arabic": "Arabe", "Italian": "Italien",
        "Portuguese": "Portugais", "Russian": "Russe",
        "Survival — greetings, ordering, directions":
            "Survie : salutations, commander, demander son chemin",
        "Everyday talk — say how your day went in short sentences":
            "Conversation quotidienne : raconter sa journée en phrases courtes",
        "Opinions — explain with reasons": "Opinions : expliquer avec des raisons",
        "Discussion — handle abstract topics": "Discussion : aborder des sujets abstraits",
        "Precision — nuance, idiom and register": "Précision : nuance, idiome et registre",
        "Free talk": "Discussion libre",
        "Talk about whatever interests you — how much you say is the point":
            "Parlez de ce qui vous intéresse : ce qui compte, c'est le volume de parole",
        "Scenes": "Situations",
        "Rehearse a real situation as role-play":
            "Répéter une situation réelle en jeu de rôle",
        "Drills": "Entraînement ciblé",
        "Only the things you keep getting wrong": "Uniquement ce que vous ratez sans cesse",
        "Review": "Révision",
        "Review queue only — meet it again just before you forget":
            "Uniquement la file de révision : revoir juste avant d'oublier",
        "Shadowing": "Shadowing",
        "Listen and say it back exactly — pronunciation and rhythm":
            "Écouter et répéter à l'identique : prononciation et rythme",
        "Airport — check-in, transfers, baggage":
            "Aéroport : enregistrement, correspondances, bagages",
        "Restaurant — ordering, requests, paying":
            "Restaurant : commander, demander, régler",
        "Hotel — check-in, requests, problems": "Hôtel : arrivée, demandes, problèmes",
        "Shopping — prices, exchanges, refunds": "Achats : prix, échanges, remboursements",
        "Clinic — describing symptoms, prescriptions":
            "Cabinet médical : décrire les symptômes, ordonnances",
        "Interview — introducing yourself, experience, questions":
            "Entretien : se présenter, expérience, questions",
        "Meeting — opinions, disagreement, wrapping up":
            "Réunion : avis, désaccord, conclusion",
        "Phone — talking to someone you cannot see":
            "Téléphone : parler à quelqu'un qu'on ne voit pas",
        "Small talk — weather, the weekend, catching up":
            "Bavardage : météo, week-end, prendre des nouvelles",
        "Directions — asking and understanding the answer":
            "Itinéraire : demander et comprendre la réponse",
        "Flow first": "La fluidité d'abord",
        "Never interrupts you. Corrections appear only as cards on screen — "
        "for when confidence has to come first":
            "Ne vous interrompt jamais. Les corrections n'apparaissent qu'en cartes à "
            "l'écran — pour quand la confiance passe avant",
        "Recast (default)": "Reformulation (par défaut)",
        "Says your idea back in the correct form — the conversation never stops":
            "Reprend votre idée sous la forme correcte : la conversation ne s'arrête pas",
        "Correct now": "Correction immédiate",
        "Stops at important errors and has you say it again — for exams and advanced learners":
            "S'arrête aux erreurs importantes et vous fait répéter : examens et niveau avancé",
        "Grammar": "Grammaire", "Vocabulary": "Vocabulaire", "Pronunciation": "Prononciation",
        "Register": "Registre", "Fluency": "Aisance",
        "Grammar errors dominate — the next session drills the same structures "
        "across different situations.":
            "Les erreurs de grammaire dominent : la prochaine séance travaille les mêmes "
            "structures dans différentes situations.",
        "Vocabulary is the bottleneck — moving to scenes so you actually use "
        "the words you need.":
            "Le vocabulaire est le goulot d'étranglement : passage aux situations pour que "
            "vous utilisiez vraiment les mots nécessaires.",
        "Pronunciation and rhythm are weak — more shadowing: listen, then say it back.":
            "La prononciation et le rythme sont faibles : plus de shadowing, écouter puis répéter.",
        "Register slips — interviews and meetings with immediate correction will fix it.":
            "Le registre dérape : entretiens et réunions avec correction immédiate y remédient.",
        "You stall often — lowering correction to get your speaking volume back first.":
            "Vous bloquez souvent : on baisse la correction pour retrouver d'abord le volume de parole.",
        "Today": "Aujourd'hui", "Report": "Analyse", "Settings": "Réglages",
        "Language": "Langue", "Level": "Niveau", "Mode": "Mode",
        "Correction": "Correction", "Session": "Séance",
        "{cards} cards · {graduated} graduated": "{cards} cartes · {graduated} acquises",
        "Review {count}": "Révision {count}",
        "Start talking and your corrections and new words pile up here. "
        "Nothing interrupts you while you speak — anything to fix appears quietly "
        "on this screen. Tap 🔊 to hear it again.":
            "Commencez à parler : vos corrections et vos nouveaux mots s'accumulent ici. "
            "Rien ne vous interrompt pendant que vous parlez — ce qui est à corriger "
            "apparaît discrètement sur cet écran. Touchez 🔊 pour réécouter.",
        "Start talking": "Commencer à parler",
        "Role-play": "Jeu de rôle",
        "Corrections today": "Corrections du jour",
        "New words": "Nouveaux mots",
        "Waiting for review": "En attente de révision",
        "Words you met today": "Expressions rencontrées aujourd'hui",
        "Review these": "Réviser ceci",
        "Wrap up today": "Clore la journée",
        "Review queue": "File de révision",
        "{due} to see now · {queued} waiting · intervals {intervals} sessions":
            "{due} à voir maintenant · {queued} en attente · intervalles {intervals} séances",
        "Start review": "Commencer la révision",
        "Nothing to review right now. It will come back just before you forget.":
            "Rien à réviser pour l'instant. Cela reviendra juste avant que vous n'oubliiez.",
        "box {box}/{total} · in {sessions} sessions":
            "boîte {box}/{total} · dans {sessions} séances",
        "review {box}/{total}": "révision {box}/{total}",
        "seen {count}×": "{count}e fois",
        "How much of the next level you handled": "Part du niveau supérieur maîtrisée",
        "Measured {probes}× mid-conversation — planted in the talk, not a test":
            "Mesuré {probes} fois en pleine conversation — glissé dans l'échange, pas un test",
        "Past corrections you got right again": "Corrections passées réussies de nouveau",
        "How often you actually did it right in review":
            "Fréquence de réussite effective en révision",
        "{count} times": "{count} fois",
        "What to shore up — ": "À consolider : ",
        "Start {mode}": "Commencer {mode}",
        "Level re-read: {level} → {suggest} ({why})":
            "Relecture du niveau : {level} → {suggest} ({why})",
        "Move up to {level}": "Passer à {level}",
        "Move down to {level}": "Redescendre à {level}",
        "No conversations to analyse yet. After a few talks your weak axis and "
        "level estimate appear here.":
            "Pas encore de conversation à analyser. Après quelques échanges, votre point "
            "faible et l'estimation de niveau apparaîtront ici.",
        "Session #{session} · {level} · {cards} cards":
            "Séance #{session} · {level} · {cards} cartes",
        " · weak: {axis}": " · point faible : {axis}",
        "You handled {rate} of the next level up": "Vous avez maîtrisé {rate} du niveau supérieur",
        "You cleared {rate} of the next level up": "Votre taux de réussite au niveau supérieur est de {rate}",
        "Review accuracy is {rate}": "Votre précision en révision est de {rate}",
        "Four settings, and that is all — the rest is decided by the teaching method. "
        "(See the README.)":
            "Quatre réglages, pas plus — le reste est décidé par la méthode pédagogique. "
            "(Voir le README.)",
        "Correction style: ": "Style de correction : ",
        "Correction {style}": "Correction {style}",
        "Session #{session} · {language} · {mode} · correction {policy} · {due} to review":
            "Séance #{session} · {language} · {mode} · correction {policy} · {due} à réviser",
        "1 correction": "1 correction",
        "promoted to the review queue": "passe en file de révision",
        "review {label} (box {box}/{total})": "révision {label} (boîte {box}/{total})",
        "level {level} handled": "niveau {level} maîtrisé",
        "level {level} not handled": "niveau {level} non maîtrisé",
        "Session #{session} closed — {cards} cards · {due} awaiting review":
            "Séance #{session} close — {cards} cartes · {due} en attente de révision",
        " · next mode {mode}": " · mode suivant {mode}",
        "{count} corrections — see them on the 🧩 screen":
            "{count} corrections — à voir sur l'écran 🧩",
        "no change": "aucun changement",
    },
    "de": {
        "English": "Englisch", "Spanish": "Spanisch", "Japanese": "Japanisch",
        "Chinese": "Chinesisch", "German": "Deutsch", "French": "Französisch",
        "Korean": "Koreanisch", "Arabic": "Arabisch", "Italian": "Italienisch",
        "Portuguese": "Portugiesisch", "Russian": "Russisch",
        "Survival — greetings, ordering, directions":
            "Überleben: Begrüßung, Bestellen, Wegbeschreibung",
        "Everyday talk — say how your day went in short sentences":
            "Alltagsgespräch: den Tag in kurzen Sätzen erzählen",
        "Opinions — explain with reasons": "Meinungen: mit Gründen erklären",
        "Discussion — handle abstract topics": "Diskussion: abstrakte Themen bewältigen",
        "Precision — nuance, idiom and register": "Präzision: Nuance, Idiom und Register",
        "Free talk": "Freies Sprechen",
        "Talk about whatever interests you — how much you say is the point":
            "Sprich über das, was dich interessiert — es zählt, wie viel du sprichst",
        "Scenes": "Situationen",
        "Rehearse a real situation as role-play":
            "Eine echte Situation im Rollenspiel proben",
        "Drills": "Gezieltes Üben",
        "Only the things you keep getting wrong": "Nur das, was du immer wieder falsch machst",
        "Review": "Wiederholung",
        "Review queue only — meet it again just before you forget":
            "Nur die Wiederholungsliste — kurz bevor du es vergisst",
        "Shadowing": "Shadowing",
        "Listen and say it back exactly — pronunciation and rhythm":
            "Hören und genau nachsprechen — Aussprache und Rhythmus",
        "Airport — check-in, transfers, baggage": "Flughafen: Check-in, Umsteigen, Gepäck",
        "Restaurant — ordering, requests, paying": "Restaurant: Bestellen, Bitten, Zahlen",
        "Hotel — check-in, requests, problems": "Hotel: Anreise, Wünsche, Probleme",
        "Shopping — prices, exchanges, refunds": "Einkaufen: Preise, Umtausch, Rückgabe",
        "Clinic — describing symptoms, prescriptions": "Praxis: Beschwerden schildern, Rezepte",
        "Interview — introducing yourself, experience, questions":
            "Vorstellungsgespräch: sich vorstellen, Erfahrung, Fragen",
        "Meeting — opinions, disagreement, wrapping up":
            "Besprechung: Meinungen, Widerspruch, Abschluss",
        "Phone — talking to someone you cannot see":
            "Telefon: mit jemandem sprechen, den man nicht sieht",
        "Small talk — weather, the weekend, catching up":
            "Small Talk: Wetter, Wochenende, Neuigkeiten",
        "Directions — asking and understanding the answer":
            "Wegbeschreibung: fragen und die Antwort verstehen",
        "Flow first": "Redefluss zuerst",
        "Never interrupts you. Corrections appear only as cards on screen — "
        "for when confidence has to come first":
            "Unterbricht dich nie. Korrekturen erscheinen nur als Karten auf dem "
            "Bildschirm — für die Phase, in der Selbstvertrauen zuerst kommt",
        "Recast (default)": "Umformulierung (Standard)",
        "Says your idea back in the correct form — the conversation never stops":
            "Gibt deine Aussage in der richtigen Form zurück — das Gespräch stoppt nie",
        "Correct now": "Sofort korrigieren",
        "Stops at important errors and has you say it again — for exams and advanced learners":
            "Hält bei wichtigen Fehlern an und lässt dich wiederholen — für Prüfungen "
            "und Fortgeschrittene",
        "Grammar": "Grammatik", "Vocabulary": "Wortschatz", "Pronunciation": "Aussprache",
        "Register": "Register", "Fluency": "Sprechfluss",
        "Grammar errors dominate — the next session drills the same structures "
        "across different situations.":
            "Grammatikfehler überwiegen — die nächste Sitzung übt dieselben Strukturen "
            "in verschiedenen Situationen.",
        "Vocabulary is the bottleneck — moving to scenes so you actually use "
        "the words you need.":
            "Der Wortschatz ist der Engpass — wir wechseln zu Situationen, damit du die "
            "nötigen Wörter wirklich benutzt.",
        "Pronunciation and rhythm are weak — more shadowing: listen, then say it back.":
            "Aussprache und Rhythmus sind schwach — mehr Shadowing: hören, dann nachsprechen.",
        "Register slips — interviews and meetings with immediate correction will fix it.":
            "Das Register rutscht ab — Vorstellungsgespräche und Besprechungen mit "
            "sofortiger Korrektur beheben das.",
        "You stall often — lowering correction to get your speaking volume back first.":
            "Du stockst oft — wir senken die Korrektur, um zuerst die Sprechmenge zurückzuholen.",
        "Today": "Heute", "Report": "Auswertung", "Settings": "Einstellungen",
        "Language": "Sprache", "Level": "Niveau", "Mode": "Modus",
        "Correction": "Korrektur", "Session": "Sitzung",
        "{cards} cards · {graduated} graduated": "{cards} Karten · {graduated} abgeschlossen",
        "Review {count}": "Wiederholung {count}",
        "Start talking and your corrections and new words pile up here. "
        "Nothing interrupts you while you speak — anything to fix appears quietly "
        "on this screen. Tap 🔊 to hear it again.":
            "Fang an zu sprechen, und deine Korrekturen und neuen Wörter sammeln sich "
            "hier. Nichts unterbricht dich beim Sprechen — was zu korrigieren ist, "
            "erscheint still auf diesem Bildschirm. Tippe auf 🔊, um es erneut zu hören.",
        "Start talking": "Sprechen beginnen",
        "Role-play": "Rollenspiel",
        "Corrections today": "Korrekturen heute",
        "New words": "Neue Wörter",
        "Waiting for review": "Wartet auf Wiederholung",
        "Words you met today": "Heute begegnete Ausdrücke",
        "Review these": "Damit wiederholen",
        "Wrap up today": "Tag abschließen",
        "Review queue": "Wiederholungsliste",
        "{due} to see now · {queued} waiting · intervals {intervals} sessions":
            "{due} jetzt fällig · {queued} wartend · Abstände {intervals} Sitzungen",
        "Start review": "Wiederholung starten",
        "Nothing to review right now. It will come back just before you forget.":
            "Gerade nichts zu wiederholen. Es kommt zurück, kurz bevor du es vergisst.",
        "box {box}/{total} · in {sessions} sessions":
            "Fach {box}/{total} · in {sessions} Sitzungen",
        "review {box}/{total}": "Wiederholung {box}/{total}",
        "seen {count}×": "{count}. Mal",
        "How much of the next level you handled": "Anteil der nächsthöheren Stufe bewältigt",
        "Measured {probes}× mid-conversation — planted in the talk, not a test":
            "{probes}× im Gespräch gemessen — eingebaut ins Gespräch, kein Test",
        "Past corrections you got right again": "Frühere Korrekturen erneut richtig",
        "How often you actually did it right in review":
            "Wie oft du es in der Wiederholung tatsächlich richtig gemacht hast",
        "{count} times": "{count} Fälle",
        "What to shore up — ": "Was zu festigen ist: ",
        "Start {mode}": "{mode} starten",
        "Level re-read: {level} → {suggest} ({why})":
            "Niveau neu eingeschätzt: {level} → {suggest} ({why})",
        "Move up to {level}": "Auf {level} anheben",
        "Move down to {level}": "Auf {level} absenken",
        "No conversations to analyse yet. After a few talks your weak axis and "
        "level estimate appear here.":
            "Noch keine Gespräche zum Auswerten. Nach ein paar Gesprächen erscheinen hier "
            "deine Schwachstelle und die Niveauschätzung.",
        "Session #{session} · {level} · {cards} cards":
            "Sitzung #{session} · {level} · {cards} Karten",
        " · weak: {axis}": " · schwach: {axis}",
        "You handled {rate} of the next level up": "Du hast {rate} der nächsthöheren Stufe bewältigt",
        "You cleared {rate} of the next level up": "Deine Erfolgsquote auf der nächsten Stufe liegt bei {rate}",
        "Review accuracy is {rate}": "Deine Trefferquote in der Wiederholung liegt bei {rate}",
        "Four settings, and that is all — the rest is decided by the teaching method. "
        "(See the README.)":
            "Vier Einstellungen, mehr nicht — den Rest bestimmt die Lehrmethode. "
            "(Siehe README.)",
        "Correction style: ": "Korrekturstil: ",
        "Correction {style}": "Korrektur {style}",
        "Session #{session} · {language} · {mode} · correction {policy} · {due} to review":
            "Sitzung #{session} · {language} · {mode} · Korrektur {policy} · {due} zu wiederholen",
        "1 correction": "1 Korrektur",
        "promoted to the review queue": "in die Wiederholungsliste aufgenommen",
        "review {label} (box {box}/{total})": "Wiederholung {label} (Fach {box}/{total})",
        "level {level} handled": "Stufe {level} bewältigt",
        "level {level} not handled": "Stufe {level} nicht bewältigt",
        "Session #{session} closed — {cards} cards · {due} awaiting review":
            "Sitzung #{session} beendet — {cards} Karten · {due} zur Wiederholung",
        " · next mode {mode}": " · nächster Modus {mode}",
        "{count} corrections — see them on the 🧩 screen":
            "{count} Korrekturen — auf dem 🧩-Bildschirm ansehen",
        "no change": "keine Änderung",
    },
}


# 개인별 학습 설정. 영어 원문은 그대로 두고 화면 언어로만 옮긴다.
TRANSLATIONS.setdefault("ko", {}).update({
    "Your learning preferences": "나의 학습 설정",
    "Learning goal": "학습 목적",
    "Topics you enjoy": "좋아하는 주제",
    "Practice experience": "학습 체험 방식",
    "Explanation language": "설명 언어",
    "Use interface language": "화면 언어 사용",
    "Save learning preferences": "학습 설정 저장",
    "Varied examples and role-play": "다양한 예시와 상황극",
    "Conversation first": "대화 중심",
    "Learning goal: {goal}": "학습 목적: {goal}",
    "Choose your own goal in Settings": "설정에서 나의 학습 목적을 정해 주세요",
    "Your language plan: {languages}": "나의 언어 학습 계획: {languages}",
    "Each language keeps its own level, practice and review history. Tell Cosmos which language you want to learn next.": "언어마다 수준·연습·복습 기록이 따로 유지됩니다. 다음에 배우고 싶은 언어는 Cosmos에게 말해 주세요.",
})

TRANSLATIONS.setdefault("ja", {}).update({
    "Your learning preferences": "学習の設定",
    "Learning goal": "学習の目的",
    "Topics you enjoy": "好きな話題",
    "Practice experience": "練習のスタイル",
    "Explanation language": "説明の言語",
    "Use interface language": "画面の言語を使う",
    "Save learning preferences": "学習設定を保存",
    "Varied examples and role-play": "多様な例とロールプレイ",
    "Conversation first": "会話を中心に",
    "Learning goal: {goal}": "学習の目的: {goal}",
    "Choose your own goal in Settings": "設定で自分の学習目的を選んでください",
    "Your language plan: {languages}": "言語の学習計画: {languages}",
    "Each language keeps its own level, practice and review history. Tell Cosmos which language you want to learn next.": "言語ごとにレベル・練習・復習の記録が保存されます。次に学びたい言語をCosmosに伝えてください。",
})

TRANSLATIONS.setdefault("es", {}).update({
    "Your learning preferences": "Tus preferencias de aprendizaje",
    "Learning goal": "Objetivo de aprendizaje",
    "Topics you enjoy": "Temas que disfrutas",
    "Practice experience": "Experiencia de práctica",
    "Explanation language": "Idioma de las explicaciones",
    "Use interface language": "Usar el idioma de la interfaz",
    "Save learning preferences": "Guardar preferencias",
    "Varied examples and role-play": "Ejemplos variados y juegos de rol",
    "Conversation first": "Conversación ante todo",
    "Learning goal: {goal}": "Objetivo: {goal}",
    "Choose your own goal in Settings": "Elige tu objetivo en Ajustes",
    "Your language plan: {languages}": "Tu plan de idiomas: {languages}",
    "Each language keeps its own level, practice and review history. Tell Cosmos which language you want to learn next.": "Cada idioma conserva su nivel y su historial de práctica y repaso. Dile a Cosmos qué idioma quieres aprender después.",
})

TRANSLATIONS.setdefault("fr", {}).update({
    "Your learning preferences": "Vos préférences d’apprentissage",
    "Learning goal": "Objectif d’apprentissage",
    "Topics you enjoy": "Sujets qui vous plaisent",
    "Practice experience": "Style de pratique",
    "Explanation language": "Langue des explications",
    "Use interface language": "Utiliser la langue de l’interface",
    "Save learning preferences": "Enregistrer les préférences",
    "Varied examples and role-play": "Exemples variés et jeux de rôle",
    "Conversation first": "La conversation avant tout",
    "Learning goal: {goal}": "Objectif : {goal}",
    "Choose your own goal in Settings": "Choisissez votre objectif dans les paramètres",
    "Your language plan: {languages}": "Votre parcours linguistique : {languages}",
    "Each language keeps its own level, practice and review history. Tell Cosmos which language you want to learn next.": "Chaque langue conserve son niveau et son historique de pratique et de révision. Dites à Cosmos quelle langue apprendre ensuite.",
})

TRANSLATIONS.setdefault("de", {}).update({
    "Your learning preferences": "Deine Lernpräferenzen",
    "Learning goal": "Lernziel",
    "Topics you enjoy": "Themen, die dir gefallen",
    "Practice experience": "Übungsstil",
    "Explanation language": "Erklärungssprache",
    "Use interface language": "Sprache der Oberfläche verwenden",
    "Save learning preferences": "Lernpräferenzen speichern",
    "Varied examples and role-play": "Vielfältige Beispiele und Rollenspiele",
    "Conversation first": "Gespräche im Mittelpunkt",
    "Learning goal: {goal}": "Lernziel: {goal}",
    "Choose your own goal in Settings": "Wähle dein eigenes Ziel in den Einstellungen",
    "Your language plan: {languages}": "Dein Sprachenplan: {languages}",
    "Each language keeps its own level, practice and review history. Tell Cosmos which language you want to learn next.": "Jede Sprache behält ihr Niveau sowie ihren Übungs- und Wiederholungsverlauf. Sag Cosmos, welche Sprache du als Nächstes lernen möchtest.",
})


TRANSLATIONS['ko'].update({
    'YOUR CONVERSATION SPACE': '나의 대화 연습 공간',
    'A little practice. A wider world.': '조금씩 말하다 보면, 더 넓은 세상으로.',
    'Your words become a constellation. Keep a conversation going, then revisit what needs care.': '함께 익힌 표현이 나만의 별자리가 됩니다. 즐겁게 대화하고, 조금 더 연습할 표현을 다시 만나 보세요.',
    'Ready to practise': '대화를 시작해 볼까요', 'Practice session open': '학습 세션이 열려 있어요',
    'Use Cosmos chat or its voice controls to talk. This view does not indicate microphone status.': '코스모스의 대화창이나 음성 버튼으로 대화하세요. 이 화면은 마이크 연결 상태를 나타내지 않습니다.',
    'Start a conversation': '가볍게 대화하기', 'Try a role-play': '상황극으로 연습',
    'Practise review items': '복습 대화 시작', 'Finish this session': '이번 학습 마무리',
    'Continue in Cosmos chat': '코스모스 대화에서 이어가기',
    'Saved expressions': '함께 익힌 표현', 'Ready for review': '다시 만날 표현',
    'Review milestones': '복습 단계 완료', 'Your learning constellation': '나의 학습 별자리',
    'Blue: collected · Amber: due · Mint: review milestone. One star per expression, up to 80. Not a fluency score.': '파랑: 수집 · 노랑: 복습 차례 · 민트: 복습 단계 완료. 표현 하나가 별 하나이며 최대 80개를 표시합니다. 유창성 점수는 아닙니다.',
    'Pause motion': '움직임 멈추기', 'Enable motion': '움직임 켜기', '2D view': '2D 보기',
    'One expression to revisit': '지금 다시 만나 볼 표현',
    'Your first expressions will appear here after practice.': '대화를 나누면 함께 익힌 첫 표현이 이곳에 남아요.',
    'Write or say a sentence before revealing the example.': '예시를 보기 전에 문장을 적거나 말해 보세요.',
    'Try your own sentence…': '나만의 문장으로 표현해 보세요…', 'Reveal & compare': '예시를 보고 비교하기',
    'I recalled it': '기억해 냈어요', 'I need practice': '조금 더 연습할래요',
    'Self-check, not an automatic assessment. Compare your answer before recording it.': '자동 채점이 아닌 자기 점검입니다. 나의 답과 예시를 비교한 뒤 기록하세요.',
    'Nothing is due in this session. Practise to discover new expressions.': '이번 세션에 복습할 표현은 없어요. 대화하며 새로운 표현을 만나 보세요.',
    'Expressions from your practice': '대화에서 만난 표현들',
    'Showing the latest 8. Find more in Review and Report.': '최근 8개를 표시합니다. 복습과 리포트에서 더 확인하세요.',
    'Updating your learning…': '학습 기록을 반영하고 있어요…', 'Learning updated': '학습 기록에 반영했어요',
    'Could not update. Your answer is kept. Please try again.': '반영하지 못했어요. 작성한 답은 유지됩니다. 다시 시도해 주세요.',
    'Refresh learning': '학습 기록 새로고침',
    'Draft answers stay in this view until you close it. Only your self-check is saved.': '작성 중인 문장은 이 화면을 닫기 전까지만 유지됩니다. 자기 점검 결과만 저장합니다.',
})


# Visual learning summaries.
TRANSLATIONS['ko'].update({'Review self-checks': '복습 자기 점검', 'Practice distribution': '연습 단계 분포', 'Not yet practised': '아직 연습 전', 'In practice': '연습 중', 'Recorded self-checks, not a fluency score.': '기록한 자기 점검 결과입니다. 유창성 점수가 아닙니다.'})
TRANSLATIONS['ja'].update({'Review self-checks': '復習の自己チェック', 'Practice distribution': '練習段階の分布', 'Not yet practised': 'まだ練習前', 'In practice': '練習中', 'Recorded self-checks, not a fluency score.': '記録した自己チェックです。流暢さの点数ではありません。'})
TRANSLATIONS['de'].update({'Review self-checks': 'Selbsteinschätzung beim Wiederholen', 'Practice distribution': 'Verteilung der Übungsstände', 'Not yet practised': 'Noch nicht geübt', 'In practice': 'In Übung', 'Recorded self-checks, not a fluency score.': 'Erfasste Selbsteinschätzungen, kein Sprachniveau-Wert.'})
TRANSLATIONS['es'].update({'Review self-checks': 'Autoevaluaciones de repaso', 'Practice distribution': 'Distribución de práctica', 'Not yet practised': 'Aún sin practicar', 'In practice': 'En práctica', 'Recorded self-checks, not a fluency score.': 'Autoevaluaciones registradas, no una puntuación de fluidez.'})
TRANSLATIONS['fr'].update({'Review self-checks': 'Auto-évaluations de révision', 'Practice distribution': 'Répartition de la pratique', 'Not yet practised': 'Pas encore pratiqué', 'In practice': 'En cours de pratique', 'Recorded self-checks, not a fluency score.': 'Auto-évaluations enregistrées, pas un score de maîtrise.'})

# Independent learning presentation, 2026-09-13.
TRANSLATIONS["ko"].update({'Learning overview': '학습 한눈에', 'Focus on practice': '연습에 집중', 'Learning settings': '학습 설정', 'One expression. Your own words.': '표현 하나를, 나의 문장으로.', 'Recall an expression, compare the example, then choose what needs more practice.': '표현을 떠올리고 예문과 비교한 뒤, 다시 연습할지 골라 보세요.', 'Learning layout saved': '학습 화면을 저장했어요'})
TRANSLATIONS["ja"].update({'Learning overview': '学習の全体像', 'Focus on practice': '練習に集中', 'Learning settings': '学習設定', 'One expression. Your own words.': '一つの表現を、自分の言葉で。', 'Recall an expression, compare the example, then choose what needs more practice.': '表現を思い出し、例文と比べて、もう一度練習するか選びましょう。', 'Learning layout saved': '学習画面を保存しました'})
TRANSLATIONS["de"].update({'Learning overview': 'Lernübersicht', 'Focus on practice': 'Auf Übungen konzentrieren', 'Learning settings': 'Lerneinstellungen', 'One expression. Your own words.': 'Ein Ausdruck. Deine eigenen Worte.', 'Recall an expression, compare the example, then choose what needs more practice.': 'Erinnere dich an einen Ausdruck, vergleiche das Beispiel und entscheide, was du weiter üben möchtest.', 'Learning layout saved': 'Lernansicht gespeichert'})
TRANSLATIONS["es"].update({'Learning overview': 'Resumen del aprendizaje', 'Focus on practice': 'Centrarse en practicar', 'Learning settings': 'Ajustes de aprendizaje', 'One expression. Your own words.': 'Una expresión. Tus propias palabras.', 'Recall an expression, compare the example, then choose what needs more practice.': 'Recuerda una expresión, compárala con el ejemplo y decide qué practicar más.', 'Learning layout saved': 'Vista de aprendizaje guardada'})
TRANSLATIONS["fr"].update({'Learning overview': 'Vue d’ensemble', 'Focus on practice': 'Se concentrer sur la pratique', 'Learning settings': 'Réglages d’apprentissage', 'One expression. Your own words.': 'Une expression. Vos propres mots.', 'Recall an expression, compare the example, then choose what needs more practice.': 'Retrouvez une expression, comparez l’exemple et choisissez ce qu’il faut retravailler.', 'Learning layout saved': 'Vue d’apprentissage enregistrée'})

def t(lang: str, text: str, /, **params) -> str:
    """`text`(영어 원문)를 `lang`으로. ★없으면 원문 그대로★ — 빈칸을 만들지 않는다.

    `{name}` 자리는 `params`로 채운다. **번역에 없는 이름을 쓰면 원문으로 떨어진다** —
    번역자가 자리표시자를 잘못 옮겨도 화면이 깨지는 대신 영어가 보인다.
    """
    out = TRANSLATIONS.get(str(lang or "en"), {}).get(text) or text
    if params:
        try:
            return out.format(**params)
        except (KeyError, IndexError, ValueError):
            try:
                return text.format(**params)
            except Exception:
                return text
    return out
