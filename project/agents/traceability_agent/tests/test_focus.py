from agents.traceability_agent import prompts
from agents.traceability_agent.agent import TraceabilityAgent
from agents.traceability_agent.focus import GAP, focus_code
from shared.schemas.traceability import Artifact

CODE = "\n".join(
    ["public class Shop {"]
    + [f"    int filler{i}() {{ return {i}; }}" for i in range(60)]
    + ["    void sendInvoiceByEmail(Customer customer) { mailer.send(customer.email(), invoice(customer)); }"]
    + [f"    int more{i}() {{ return {i}; }}" for i in range(60)]
    + ["}"]
)


def test_short_code_is_returned_unchanged():
    assert focus_code("class A {}", "anything", 1500) == "class A {}"


def test_zero_budget_means_whole_file():
    assert focus_code(CODE, "send invoice by email", 0) == CODE


def test_long_code_is_cut_to_the_budget_and_keeps_the_matching_part():
    out = focus_code(CODE, "The system sends the invoice to the customer by email", 1200)
    assert len(out) < len(CODE) / 2
    assert "sendInvoiceByEmail" in out          # the block that matches the requirement
    assert out.startswith("public class Shop")  # the first block (declaration) is kept
    assert GAP.strip() in out                   # and the cut is marked


def test_blocks_stay_in_file_order():
    out = focus_code(CODE, "invoice email customer", 1200)
    assert out.index("public class Shop") < out.index("sendInvoiceByEmail")


def test_agent_shows_the_whole_file_by_default_and_the_focused_one_when_asked():
    source = Artifact(id="R1", type="requirement", text="The system sends the invoice by email", project="p")
    target = Artifact(id="C1", type="code", text=CODE, project="p")
    whole = TraceabilityAgent(uskg=object(), embedder=object(), llm=object())
    focused = TraceabilityAgent(uskg=object(), embedder=object(), llm=object(), focus_chars=1200)
    assert whole.llm_inputs(source, target)[1].text.count("filler") > focused.llm_inputs(source, target)[1].text.count("filler")
    assert "sendInvoiceByEmail" in focused.llm_inputs(source, target)[1].text


def test_short_reasoning_note_is_appended_once():
    out = prompts.with_short_reasoning(prompts.SYSTEM_PROMPT)
    assert out.startswith(prompts.SYSTEM_PROMPT.rstrip("\n")) and out.count("ONE short sentence") == 1
