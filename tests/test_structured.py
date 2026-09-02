from option_desk.agents.structured import message_text, parse_model_json, structured_methods
from option_desk.schemas import EventList


def test_deepseek_skips_json_schema():
    assert structured_methods("deepseek")[0] == "json_mode"
    assert "json_schema" not in structured_methods("deepseek")


def test_openai_tries_json_schema_first():
    assert structured_methods("openai")[0] == "json_schema"


def test_parse_fenced_event_list():
    text = """
    here you go
    ```json
    {"events": [{"title": "BIS rumor", "expected_time": "2026-09-03",
      "tickers": ["NVDA"], "mechanism": "gap", "already_priced": false,
      "action": "skip", "sources": [], "detail": ""}]}
    ```
    """
    parsed = parse_model_json(text, EventList)
    assert len(parsed.events) == 1
    assert parsed.events[0].title == "BIS rumor"
    assert parsed.events[0].action.value == "skip"


def test_message_text_reads_deepseek_reasoning_content():
    class Fake:
        content = ""
        additional_kwargs = {"reasoning_content": '{"events": []}'}
        response_metadata = {}

    assert '{"events"' in message_text(Fake())
