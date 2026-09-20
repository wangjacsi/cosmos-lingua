import json
import threading

import pytest

from cosmos.contracts import ToolContext
from lingua_live import LinguaLive, learning_state, CHANNEL


def test_older_core_gets_upgrade_message_without_reading_or_writing_learning_files():
    class OldContext:
        user_id = "local"
        def data_dir(self, *args):
            pytest.fail("Old core must not migrate or modify learning data")
    agent, ctx = LinguaLive(), OldContext()
    assert "0.3.0" in agent.run(ctx, action="start")
    assert "0.3.0" in agent.view(ctx)["blocks"][0]["text"]


def test_dynamic_view_uses_real_data_and_keeps_html_stable():
    agent, ctx = LinguaLive(), Context()
    before = agent.view(ctx)['blocks'][-1]
    agent.run(ctx, action='note_word', term='catch up', meaning='Reconnect with someone')
    after = agent.view(ctx)['blocks'][-1]
    assert after['html'] == before['html']
    assert after['key'] == before['key'] == 'lingua-learning-v1'
    assert before['state']['total'] == 0 and after['state']['total'] == 1
    assert len(after['state']['stars']) == 1
    assert after['state']['due'] == 0
    assert after['libraries'] == ['three']
    assert len(after['html']) < 400_000


def test_review_stale_submission_and_wrong_id_do_not_change_another_card():
    from lingua_viewer import review_token
    agent, ctx = LinguaLive(), Context()
    agent.run(ctx, action='note_word', term='hello')
    agent.run(ctx, action='start')
    item = agent._load(ctx)['items'][0]
    args = dict(action='review_answer', item_id=item['id'], review_token=review_token(item),
                correct_answer=True, language='en')
    assert not agent.run(ctx, **args).startswith('Lingua error')
    assert agent.run(ctx, **args).startswith('Lingua error')
    assert agent.run(ctx, **{**args, 'language':'es'}).startswith('Lingua error')
    assert agent.run(ctx, **{**args, 'item_id':'missing'}) == 'No review item matched.'
    assert agent._load(ctx)['items'][0]['hits'] == 1


def test_one_off_errors_are_not_due_until_repeated():
    agent, ctx = LinguaLive(), Context()
    agent.run(ctx, action='note_error', said='I goed', correct='I went')
    assert agent._due(agent._load(ctx)) == []


def test_snapshot_is_bounded_and_language_specific():
    from cosmos.contracts.view import normalize
    agent, ctx = LinguaLive(), Context()
    data = agent._load(ctx)
    data['items'] = [dict(id=str(i), lang='en', type='word', term='term', box=1, due=0,
                          meaning='meaning', examples=['example']) for i in range(200)]
    agent._save(ctx, data)
    result = normalize(agent.view(ctx))
    snapshot = result['blocks'][-1]['state']
    assert snapshot['total'] == 200 and len(snapshot['stars']) == 80 and len(snapshot['recent']) == 8
    agent.run(ctx, action='set', language='ja')
    assert agent.view(ctx)['blocks'][-1]['state']['total'] == 0


class Context(ToolContext):
    def __init__(self, user_id="sean", lang="ko", brain=None):
        self._uid, self._lang, self._brain = user_id, lang, brain
        self.prompts, self.nudges = [], []

    @property
    def user_id(self):
        return self._uid

    @property
    def lang(self):
        return self._lang

    @property
    def brain(self):
        return self._brain

    def nudge(self, text):
        self.nudges.append(text)

    def think(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return '{"corrections": [], "words": [], "coach": ""}'


def test_users_do_not_share_language_or_goal():
    agent = LinguaLive()
    a, b = Context(), Context("other", "en")
    agent.run(a, action="set", language="en", language_order=["en", "es", "ja"],
              goal="Natural conversation", interests="Comedy and travel")
    agent.run(b, action="set", language="ja", goal="Work meetings")
    assert agent._load(a)["language_order"] == ["en", "es", "ja"]
    assert agent._load(b)["language"] == "ja"
    assert agent._load(a)["goal"] == "Natural conversation"
    assert agent._load(b)["goal"] == "Work meetings"


def test_sean_is_not_a_global_default():
    data = LinguaLive()._load(Context("new"))
    assert data["goal"] == ""
    assert data["language_order"] == ["en"]
    assert data["level_source"] == "unassessed"


def test_roundtrip_english_spanish_japanese_preserves_progress():
    agent, ctx = LinguaLive(), Context()
    agent.run(ctx, action="start", language="en", level="B1", goal="Natural conversation")
    agent.run(ctx, action="note_word", term="catch up", meaning="talk after a while")
    agent.run(ctx, action="finish")
    english = agent._load(ctx)
    agent.run(ctx, action="start", language="es", level="A1", goal="Travel")
    spanish = agent._load(ctx)
    assert spanish["session"] == 1 and spanish["items"] == []
    assert spanish["history"] == []
    agent.run(ctx, action="set", language="ja")
    assert agent._load(ctx)["level"] == "A2"
    agent.run(ctx, action="set", language="en")
    restored = LinguaLive()._load(Context())
    for field in ("items", "level", "session", "history", "goal"):
        assert restored[field] == english[field]
    assert restored["active"] is False


def test_invalid_settings_do_not_partially_switch_language():
    agent, ctx = LinguaLive(), Context()
    agent.run(ctx, action="set", language="en", level="B1")
    result = agent.run(ctx, action="set", language="es", level="INVALID")
    assert "Lingua error" in result
    assert agent._load(ctx)["language"] == "en"
    assert agent._load(ctx)["level"] == "B1"


def test_legacy_migration_keeps_cards_and_review_numbers():
    old = {"language": "en", "session": 12, "level": "B1",
           "items": [{"id": "e", "lang": "en", "due": 13},
                     {"id": "s", "lang": "es", "due": 15}],
           "history": [{"session": 12, "cards": 1}]}
    data = learning_state(old)
    assert data["items"] == [old["items"][0]]
    assert data["profiles"]["es"]["items"][0]["due"] == 15
    assert data["profiles"]["es"]["session"] == 12
    assert data["profiles"]["es"]["history"] == []
    assert learning_state(data) == data
    assert len(old["items"]) == 2


def test_unknown_future_schema_is_not_overwritten():
    with pytest.raises(ValueError):
        learning_state({"schema": 99})


def test_only_local_owner_migrates_legacy_file(tmp_path, monkeypatch):
    from cosmos.core import deployment
    monkeypatch.setattr(deployment, "available", lambda key: False)
    agent = LinguaLive()
    legacy = tmp_path / "state.json"
    original = json.dumps({"language": "es", "goal": "Private legacy goal"})
    legacy.write_text(original)
    monkeypatch.setattr(agent, "_dir", lambda ctx: tmp_path)
    assert agent._load(Context("someone"))["goal"] == ""
    assert agent._load(Context("local"))["goal"] == "Private legacy goal"
    assert legacy.read_text() == original
    legacy.write_text('{"language":"ja"}')
    assert agent._load(Context("local"))["language"] == "es"


@pytest.mark.parametrize("ui,target,explanation,expected", [
    ("ko", "en", "auto", "Korean"), ("en", "ja", "auto", "English"),
    ("ko", "es", "fr", "French"), ("es-MX", "en", "auto", "Spanish")])
def test_target_and_explanation_languages_are_independent(ui, target, explanation, expected):
    agent, ctx = LinguaLive(), Context(lang=ui)
    result = agent.run(ctx, action="start", language=target, explanation_language=explanation)
    agent.observe_turn(ctx, "user", "This is a long enough example sentence.")
    assert f"Explanation language: {expected}" in result
    assert f"Write notes and meanings in {expected}." in ctx.prompts[0]


def test_goal_and_fun_examples_reach_the_tutor():
    result = LinguaLive().run(Context(), action="start", goal="Speak naturally", interests="Travel comedy")
    assert "Speak naturally" in result and "Travel comedy" in result
    assert "two different everyday situations" in result
    assert "Never invent a famous video" in result


def test_finish_stops_background_corrections():
    agent, ctx = LinguaLive(), Context()
    agent.run(ctx, action="start")
    agent.run(ctx, action="finish")
    agent.observe_turn(ctx, "user", "Do not analyse this private unrelated conversation.")
    assert ctx.prompts == []


def test_late_analysis_cannot_cross_language_switch(monkeypatch):
    agent, ctx = LinguaLive(), Context()
    agent.run(ctx, action="start", language="en")
    def delayed(*args):
        agent.run(ctx, action="start", language="es")
        return {"corrections": [{"right": "English only"}], "coach": "Old coach"}
    monkeypatch.setattr(agent, "_ask_analyst", delayed)
    agent.observe_turn(ctx, "user", "A long enough English utterance.")
    assert agent._load(ctx)["items"] == []
    assert ctx.nudges == []


def test_concurrent_users_never_exchange_pending_utterances(monkeypatch):
    agent = LinguaLive()
    a, b = Context(), Context("other", "en")
    agent.run(a, action="start", language="en")
    agent.run(b, action="start", language="ja")
    entered, release = threading.Event(), threading.Event()
    seen = []
    def analyst(ctx, data, text, lang):
        seen.append((ctx.user_id, text))
        if ctx.user_id == "sean" and text == "First English sentence.":
            entered.set()
            assert release.wait(3)
        return {"corrections": [], "words": []}
    monkeypatch.setattr(agent, "_ask_analyst", analyst)
    worker = threading.Thread(target=agent.observe_turn, args=(a, "user", "First English sentence."))
    worker.start()
    try:
        assert entered.wait(3)
        agent.observe_turn(a, "user", "Second English sentence.")
        agent.observe_turn(b, "user", "Japanese learner sentence.")
    finally:
        release.set()
        worker.join(3)
    assert not worker.is_alive()
    assert seen == [("sean", "First English sentence."), ("other", "Japanese learner sentence."),
                    ("sean", "Second English sentence.")]


def test_settings_and_status_do_not_reset_last_practice():
    agent, ctx = LinguaLive(), Context()
    data = agent._load(ctx)
    data["last_practised"] = "2026-01-01 12:00"
    agent._save(ctx, data)
    agent.run(ctx, action="status", _tab="settings")
    agent.run(ctx, action="set", policy="flow")
    assert agent._load(ctx)["last_practised"] == "2026-01-01 12:00"
    assert agent.offer(ctx)["start"]["args"]["language"] == "en"


def test_brain_roundtrip_is_scoped_to_user_and_language(tmp_path):
    from cosmos.runtime.memory_lite.provider import LiteMemoryProvider
    brain = LiteMemoryProvider(tmp_path / "brain")
    agent, a, b = LinguaLive(), Context(brain=brain), Context("other", brain=brain)
    agent.run(a, action="set", language="en", goal="Natural English conversation")
    agent.run(a, action="set", language="es", goal="Spanish travel")
    agent.run(b, action="set", language="en", goal="Other private goal")
    entities = brain.find_entities(a.user_id, name_like="Learning English")
    assert entities and entities[0].attrs["source_channel"] == CHANNEL
    agent.run(a, action="set", language="en")
    remembered = agent._recall_progress(a, agent._load(a))
    assert "Natural English conversation" in remembered
    assert "Spanish travel" not in remembered and "Other private goal" not in remembered


def test_settings_form_escapes_user_content_and_has_working_contract():
    agent, ctx = LinguaLive(), Context()
    agent.run(ctx, action="set", goal='"><script>alert(1)</script>', _tab="settings")
    view = agent.view(ctx)
    form = next(b["html"] for b in view["blocks"] if b["type"] == "html")
    assert '&lt;script&gt;' in form and '<script>alert(1)</script>' not in form
    assert "cosmos.call('lingua'" in form
    assert 'type="button"' in form and 'type="submit"' not in form
    assert 'name="goal"' in form and 'name="explanation_language"' in form
    languages = [i["args"]["language"] for b in view["blocks"] if b["type"] == "actions"
                 for i in b["items"] if "language" in i["args"]]
    assert "it" in languages and "pt" in languages and "ru" in languages


def test_viewer_can_open_beside_cosmos_without_forcing_a_window():
    from cosmos.contracts.view import chosen_space, spaces_of
    agent = LinguaLive()
    assert spaces_of(agent) == ("screen", "window", "browser")
    assert chosen_space(agent, "window") == "window"
    assert chosen_space(agent, "screen") == "screen"


def test_visual_review_counts_use_recorded_answers_not_fake_proficiency():
    from lingua_viewer import block
    data={'items':[{'id':'a','hits':2,'misses':1,'box':1},
                   {'id':'b','hits':0,'misses':0,'box':0},
                   {'id':'c','hits':5,'misses':2,'box':5,'graduated':True}],
          'language':'en','goal':'','session':2}
    snapshot=block(data,[], 'en','English')['state']
    assert snapshot['recall']=={'hits':7,'misses':3}
    assert snapshot['stages']==[1,1,1]
    assert sum(snapshot['stages'])==snapshot['total']


def test_settings_entry_overrides_saved_tab_without_changing_profile():
    agent, ctx = LinguaLive(), Context()
    agent.run(ctx, action="status", _tab="today")
    before = ctx.load_agent_state("lingua-live")
    assert agent.view(ctx, **agent.settings_at)["params"]["tab"] == "settings"
    assert ctx.load_agent_state("lingua-live") == before


def test_layout_is_user_scoped_and_does_not_change_learning_evidence():
    agent, ctx = LinguaLive(), Context()
    agent.run(ctx, action="set", goal="Travel")
    agent.run(ctx, action="note_word", term="hello")
    before = agent._load(ctx)
    agent.run(ctx, action="layout", view_mode="practice")
    after = LinguaLive().view(ctx)["blocks"][-1]
    assert after["state"]["view_mode"] == "practice"
    assert after["state"]["total"] == 1 and after["state"]["goal"] == "Travel"
    assert agent._load(ctx)["last_practised"] == before["last_practised"]
    assert agent.view(Context("other"))["blocks"][-1]["state"]["view_mode"] == "overview"


@pytest.mark.parametrize("mode", [None, "", "unknown", []])
def test_invalid_layout_preserves_preference(mode):
    agent, ctx = LinguaLive(), Context()
    agent.run(ctx, action="layout", view_mode="practice")
    assert agent.run(ctx, action="layout", view_mode=mode).startswith("Lingua error")
    assert agent.view(ctx)["blocks"][-1]["state"]["view_mode"] == "practice"


@pytest.mark.parametrize("disable", ["turn", "agent"])
def test_late_analysis_is_discarded_after_turn_hook_disabled(monkeypatch, disable):
    from cosmos.contracts import hooks
    agent, ctx = LinguaLive(), Context()
    agent.run(ctx, action="start")
    before = agent._load(ctx)
    def analyze(*args):
        if disable == "turn":
            hooks.save(agent, {"turn": False}, user_id=ctx.user_id)
        else:
            from cosmos.core import agents
            agents.set_enabled(agent.name, False, user_id=ctx.user_id)
        return {"words": [{"term": "unwanted", "meaning": "late"}], "coach": "late coach"}
    monkeypatch.setattr(agent, "_ask_analyst", analyze)
    agent.observe_turn(ctx, "user", "A sufficiently long learner sentence")
    assert agent._load(ctx)["items"] == before["items"]
    assert not ctx.nudges
    monkeypatch.setattr(agent, "_ask_analyst", lambda *a: pytest.fail("Disabled hook called"))
    agent.observe_turn(ctx, "user", "Another sufficiently long sentence")


def test_analysis_drops_result_when_memory_permission_is_revoked(monkeypatch):
    from cosmos.core import permissions, userstate
    agent,ctx=LinguaLive(),Context(user_id='late-memory-revoke',lang='en')
    with userstate.scope(ctx.user_id):
        agent.run(ctx,action='start')
        before=agent._load(ctx)
        def analyze(*args):
            permissions.set_state('memory','deny')
            return {'words':[{'term':'late','meaning':'must not be saved'}],'coach':'late coach'}
        monkeypatch.setattr(agent,'_ask_analyst',analyze)
        try:
            agent.observe_turn(ctx,'user','A sufficiently long learner utterance.')
            assert agent._load(ctx)['items']==before['items'] and not ctx.nudges
            monkeypatch.setattr(agent,'_ask_analyst',lambda *a:pytest.fail('revoked analysis started'))
            agent.observe_turn(ctx,'user','Another sufficiently long learner utterance.')
        finally:
            permissions.set_state('memory','allow')
