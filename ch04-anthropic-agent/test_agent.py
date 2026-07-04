"""Offline unit tests for the ch04 multi-step Claude agent.

Every test runs with NO Anthropic SDK, NO API key, and NO network. We exercise
the pure core — the safe calculator, tool dispatch, state updates, response
interpretation, the full agentic loop (via an injected fake caller), and
Markdown rendering — against fixture data. The only function that touches the
wire (`_call_claude`) is a thin adapter and is not tested here.

Run:  pytest -q
"""

from __future__ import annotations

import datetime as _dt

import agent


# --- safe calculator -----------------------------------------------------

def test_calculator_basic_arithmetic():
    st = agent.AgentState.start("g")
    assert agent.tool_calculator(st, "11 / 2.5") == "4.4"
    assert agent.tool_calculator(st, "2 + 3 * 4") == "14"      # precedence
    assert agent.tool_calculator(st, "10 / 2") == "5"          # whole -> no .0


def test_calculator_rejects_code_injection():
    st = agent.AgentState.start("g")
    # Names, calls, and attribute access must not evaluate.
    assert agent.tool_calculator(st, "__import__('os').system('x')").startswith("error")
    assert agent.tool_calculator(st, "open('f')").startswith("error")
    assert agent.tool_calculator(st, "1 + foo").startswith("error")


# --- scratchpad tools (state) --------------------------------------------

def test_remember_and_recall_roundtrip():
    st = agent.AgentState.start("g")
    agent.tool_remember(st, "loaves", "4")
    assert st.scratchpad["loaves"] == "4"
    assert agent.tool_recall(st, "loaves") == "4"


def test_recall_missing_key_reports_error():
    st = agent.AgentState.start("g")
    assert agent.tool_recall(st, "nope").startswith("error")


def test_finish_sets_done_and_answer():
    st = agent.AgentState.start("g")
    agent.tool_finish(st, "42 loaves")
    assert st.done is True
    assert st.final_answer == "42 loaves"


# --- run_tool dispatch ---------------------------------------------------

def test_run_tool_unknown_name():
    st = agent.AgentState.start("g")
    assert agent.run_tool(st, "teleport", {}).startswith("error: unknown tool")


def test_run_tool_bad_arguments():
    st = agent.AgentState.start("g")
    # calculator requires `expression`; wrong kwarg -> clean error, no crash.
    assert agent.run_tool(st, "calculator", {"wrong": "1"}).startswith("error: bad arguments")


# --- extract_blocks ------------------------------------------------------

def test_extract_blocks_splits_thinking_text_and_tools():
    resp = {"content": [
        {"type": "thinking", "thinking": "let me compute"},
        {"type": "text", "text": "Working on it."},
        {"type": "tool_use", "id": "t1", "name": "calculator",
         "input": {"expression": "1+1"}},
    ]}
    thinking, texts, tools = agent.extract_blocks(resp)
    assert thinking == "let me compute"
    assert texts[0]["text"] == "Working on it."
    assert tools[0]["name"] == "calculator"


# --- apply_response (one step of the pure core) --------------------------

def _tool_use_resp(tool_id, name, tool_input, thinking="", text=""):
    content = []
    if thinking:
        content.append({"type": "thinking", "thinking": thinking})
    if text:
        content.append({"type": "text", "text": text})
    content.append({"type": "tool_use", "id": tool_id, "name": name, "input": tool_input})
    return {"content": content}


def test_apply_response_runs_tool_and_appends_result_turn():
    st = agent.AgentState.start("compute 1+1")
    resp = _tool_use_resp("t1", "calculator", {"expression": "1 + 1"}, thinking="add them")
    agent.apply_response(st, resp)
    assert st.step == 1
    # assistant turn + tool_result user turn appended to the original goal turn
    assert st.messages[-1]["role"] == "user"
    assert st.messages[-1]["content"][0]["type"] == "tool_result"
    assert st.messages[-1]["content"][0]["content"] == "2"
    assert st.trace[0]["actions"][0]["result"] == "2"
    assert st.done is False


def test_apply_response_finish_ends_run():
    st = agent.AgentState.start("g")
    resp = _tool_use_resp("t9", "finish", {"answer": "all done"})
    agent.apply_response(st, resp)
    assert st.done is True
    assert st.final_answer == "all done"


def test_apply_response_no_tool_ends_run():
    st = agent.AgentState.start("g")
    resp = {"content": [{"type": "text", "text": "The answer is 7."}]}
    agent.apply_response(st, resp)
    assert st.done is True
    assert st.final_answer == "The answer is 7."


# --- build_request -------------------------------------------------------

def test_build_request_includes_tools_and_thinking():
    st = agent.AgentState.start("g")
    req = agent.build_request(st, model="claude-sonnet-4-5", thinking=True)
    assert req["model"] == "claude-sonnet-4-5"
    assert req["tools"] == agent.TOOL_SCHEMAS
    assert req["thinking"]["type"] == "enabled"
    assert req["messages"] == st.messages


def test_build_request_can_disable_thinking():
    st = agent.AgentState.start("g")
    req = agent.build_request(st, thinking=False)
    assert "thinking" not in req


# --- run_agent: a full multi-step loop with an injected fake caller ------

def test_run_agent_full_multistep_loop():
    """Drive a real 4-step run: calc -> remember -> recall -> finish.

    A scripted fake caller replaces the network. This proves the whole agentic
    loop — multi-step processing AND state (scratchpad) — works offline.
    """
    scripted = [
        _tool_use_resp("a", "calculator", {"expression": "11 / 2.5"}, thinking="divide"),
        _tool_use_resp("b", "remember", {"key": "loaves", "value": "4"}),
        _tool_use_resp("c", "recall", {"key": "loaves"}),
        _tool_use_resp("d", "finish", {"answer": "4 loaves, 1 cup flour left"}),
    ]
    calls = {"n": 0}

    def fake_caller(request, api_key):
        resp = scripted[calls["n"]]
        calls["n"] += 1
        return resp

    state = agent.run_agent("bake loaves", max_steps=10, caller=fake_caller)
    assert state.done is True
    assert state.step == 4
    assert state.final_answer == "4 loaves, 1 cup flour left"
    assert state.scratchpad["loaves"] == "4"          # state persisted across steps
    # trace captured every action in order
    tools_called = [e["actions"][0]["tool"] for e in state.trace]
    assert tools_called == ["calculator", "remember", "recall", "finish"]


def test_run_agent_respects_max_steps():
    """A caller that never finishes must stop at max_steps, not loop forever."""
    def never_finishes(request, api_key):
        return _tool_use_resp("x", "calculator", {"expression": "1+1"})

    state = agent.run_agent("loop forever", max_steps=3, caller=never_finishes)
    assert state.step == 3
    assert state.done is False
    assert "step limit" in state.final_answer


def test_run_agent_rejects_empty_goal():
    import pytest
    with pytest.raises(RuntimeError):
        agent.run_agent("   ", caller=lambda r, k: {"content": []})


# --- render_transcript ---------------------------------------------------

_FIXED_NOW = _dt.datetime(2026, 7, 4, tzinfo=_dt.timezone.utc)


def test_render_transcript_shows_goal_answer_and_memory():
    st = agent.AgentState.start("How many loaves?")
    st.step = 4
    st.final_answer = "4 loaves"
    st.scratchpad = {"loaves": "4"}
    md = agent.render_transcript(st, show_trace=False, now=_FIXED_NOW)
    assert "# Agent Run" in md
    assert "2026-07-04" in md and "4 steps" in md
    assert "How many loaves?" in md
    assert "4 loaves" in md
    assert "## Working memory" in md and "**loaves**: 4" in md


def test_render_transcript_trace_included_when_requested():
    st = agent.AgentState.start("g")
    st.step = 1
    st.final_answer = "done"
    st.trace = [{"step": 1, "thinking": "hmm", "said": "",
                 "actions": [{"tool": "calculator", "input": {"expression": "1+1"},
                              "result": "2"}]}]
    md = agent.render_transcript(st, show_trace=True, now=_FIXED_NOW)
    assert "## Step-by-step trace" in md
    assert "### Step 1" in md
    assert "*thinking:* hmm" in md
    assert "**calculator**" in md and "`2`" in md
