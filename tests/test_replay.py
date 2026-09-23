from option_desk.agents.desk import enforce_desk_rules
from option_desk.replay import SCENARIO_IDS, build_replay, iter_replay, list_scenarios
from option_desk.schemas import DeltaBucket, DeskAction, DeskRun
from option_desk.web.app import create_app
from fastapi.testclient import TestClient


def _decision(case, stamped: bool = True):
    output = case.stamped if stamped else case.proposal
    return output.decisions[0]


def test_scenario_list_is_stable():
    listed = [item["id"] for item in list_scenarios("zh")]
    assert listed == list(SCENARIO_IDS)
    assert list_scenarios("zh")[0]["title"] == "硬门控"
    assert list_scenarios("en")[0]["title"] == "Hard gate"


def test_hard_gate_rewrites_open_to_skip():
    case = build_replay("hard-gate", "zh")
    proposal = _decision(case, stamped=False)
    stamped = _decision(case)
    assert proposal.action == DeskAction.OPEN
    assert proposal.contract_id == "NVDA-2026-09-11-P-170"
    assert stamped.action == DeskAction.SKIP
    assert stamped.contract_id is None
    assert "财报" in stamped.why
    changed = {row["field"]: row for row in case.rewrite["changes"]}
    assert changed["action"]["before"] == "OPEN"
    assert changed["action"]["after"] == "SKIP"
    assert changed["action"]["changed"] is True


def test_invented_contract_is_rejected():
    case = build_replay("invented-contract", "en")
    proposal = _decision(case, stamped=False)
    stamped = _decision(case)
    assert proposal.contract_id == "NVDA-2026-09-11-P-999"
    assert stamped.action == DeskAction.SKIP
    assert "not in the delta buckets" in stamped.why
    changed = {row["field"]: row for row in case.rewrite["changes"]}
    assert changed["contract_id"]["changed"] is True
    assert changed["contract_id"]["after"] == ""


def test_reduce_keeps_a_legal_open_on_the_conservative_contract():
    case = build_replay("reduce-risk", "en")
    proposal = _decision(case, stamped=False)
    allowed = enforce_desk_rules(case.proposal, [case.snapshot], 55000, "en")
    stamped = _decision(case)
    assert proposal.delta_bucket == DeltaBucket.STANDARD
    assert allowed.decisions[0].action == DeskAction.OPEN
    assert allowed.decisions[0].contract_id == "NVDA-2026-09-11-P-170"
    assert stamped.action == DeskAction.OPEN
    assert stamped.delta_bucket == DeltaBucket.CONSERVATIVE
    assert stamped.contract_id == "NVDA-2026-09-11-P-155"
    assert stamped.payoff is not None
    assert "risk_off" in stamped.why


def test_iter_replay_finishes_without_live_calls():
    events = list(iter_replay("hard-gate", "zh"))
    types = [event.type for event in events]
    assert types[0] == "run_started"
    assert types[-1] == "run_finished"
    assert "desk_done" in types
    finished = events[-1]
    run = DeskRun.model_validate(finished.data["run"])
    assert run.desk.decisions[0].action == DeskAction.SKIP
    assert "录制" in run.snapshots[0].notes[0]


def test_demo_endpoints():
    with TestClient(create_app()) as client:
        listed = client.get("/api/demos", headers={"X-Option-Desk-Lang": "zh"})
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()["scenarios"]] == list(SCENARIO_IDS)

        missing = client.post("/api/demos/not-a-demo")
        assert missing.status_code == 404

        with client.stream(
            "POST",
            "/api/demos/invented-contract",
            headers={"X-Option-Desk-Lang": "en"},
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())
    assert "event: desk_done" in body
    assert "NVDA-2026-09-11-P-999" in body
    assert "run_finished" in body
