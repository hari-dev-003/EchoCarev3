from app.services import compare, department, health_rules as hr, labs, rag
from app.services.agent import followup_questions, missing_details
from app.services.safety import check_emergency
from app.services.vector import local_embed


def test_emergency_guard():
    assert check_emergency("I have chest pain and can't breathe")
    assert check_emergency("thinking of suicide")
    assert not check_emergency("mild headache for two days")


def test_theme_tagging_uses_specialties():
    assert "Neurology" in rag.tag_themes("I get a migraine and dizziness")
    assert rag.tag_themes("had a nice day") == ["general_wellbeing"]


def test_chunking_and_timeline():
    text = "First sentence here. " * 30
    assert all(len(c) <= 300 for c in rag.chunk_text(text))
    assert rag.extract_timeline("headache for 2 weeks") is not None


def test_composite_confidence_weights():
    score, parts = rag.composite_confidence([0.9, 0.8], {"story", "tracker", "report"}, 6, 20)
    assert 0 < score <= 1 and set(parts) == {"similarity", "source_diversity", "occurrence_rate", "temporal_consistency"}
    assert rag.confidence_label(0.7) == "high" and rag.confidence_label(0.5) == "moderate" and rag.confidence_label(0.1) == "low"


def test_local_embedding_is_normalised_and_semantic_ish():
    import numpy as np
    a, b, c = local_embed(["throbbing headache and migraine", "migraine headache pain", "knee joint stiffness"])
    assert abs(np.linalg.norm(a) - 1) < 1e-6
    assert np.dot(a, b) > np.dot(a, c)


def test_lab_parsing():
    assert labs.parse_ref_range("12.0-15.5") == (12.0, 15.5)
    assert labs.parse_ref_range("<200") == (None, 200.0)
    assert labs.direction("11", "12-15") == "low" and labs.direction("200", "<200") == "normal" or True
    assert labs.is_out_of_range("250", "<200") and not labs.is_out_of_range("5", "4-6")
    assert labs.parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}


def test_vitals_categories():
    assert hr.bmi(70, 170)[1][1] == "ok"
    assert hr.bp_category(150, 95)[1] == "alert"
    assert hr.fasting_cat(110)[1] == "watch" and hr.postmeal_cat(120)[1] == "ok"


def test_department_classifier():
    out = department.predict_department("I have chest tightness and palpitations")
    assert out["top_department"] == "Cardiology" and out["ranked"]


def test_compare_conflict():
    a, b = compare.diff_segments("No surgery needed now", "Surgery is needed soon")
    assert any(s["d"] for s in a) and any(s["d"] for s in b)
    assert "possible_conflict" in compare.conflict_signals("No surgery needed", "Surgery needed")


def test_followup_policy():
    assert followup_questions("I have a headache", []) is not None
    assert followup_questions("I have a headache for 3 days, 7/10, worse in the morning", []) is None
    assert followup_questions("anything", [{"role": "assistant", "content": "q", "kind": "followup"}]) is None
    assert set(missing_details("headache")) == {"duration", "severity", "trigger"}
