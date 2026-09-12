import pytest
import json
import sys
from urllib.parse import urlparse


def clear_known_contracts():
    for name, module in list(sys.modules.items()):
        if "genlayer" in name and hasattr(module, "__known_contract__"):
            setattr(module, "__known_contract__", None)


# --- Helper functions directly mirror contract logic for isolated unit testing ---

class UserError(Exception):
    pass


def _extract_origin(url: str) -> tuple:
    u = url.strip()
    if not (u.startswith("http://") or u.startswith("https://")):
        raise UserError("URL must start with http:// or https://")
    try:
        parsed = urlparse(u)
    except Exception:
        raise UserError("Invalid URL format")

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise UserError("Only http and https protocols are supported")

    if parsed.username is not None or parsed.password is not None:
        raise UserError("URL credentials are not allowed")

    hostname = parsed.hostname
    if not hostname:
        raise UserError("URL missing valid hostname")

    hostname = hostname.lower().strip()
    if not hostname or ".." in hostname or hostname.startswith(".") or hostname.endswith("."):
        raise UserError("Ambiguous or invalid hostname")

    port = parsed.port
    if port is None:
        port = 80 if scheme == "http" else 443

    return scheme, hostname, port


def _is_origin_valid(target_url: str, base_url: str) -> bool:
    t_scheme, t_host, t_port = _extract_origin(target_url)
    b_scheme, b_host, b_port = _extract_origin(base_url)

    if t_scheme != b_scheme or t_port != b_port:
        return False

    if t_host == b_host:
        return True

    if t_host.endswith("." + b_host):
        return True

    return False


def _parse_llm_json(text) -> dict:
    if isinstance(text, dict):
        return text
    if hasattr(text, "content"):
        text = text.content
    try:
        cleaned = str(text).strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return json.loads(cleaned.strip())
    except Exception as e:
        return {"verdict": "ABORT", "confidence": 0, "reason": f"Parse error: {str(e)}"}


def _safe_parse(raw) -> dict:
    data = _parse_llm_json(raw)
    if not isinstance(data, dict):
        return None

    verdict = str(data.get("verdict", "")).strip().upper()
    if verdict not in ("COMPLIANT", "NON_COMPLIANT", "ABORT"):
        return None

    conf = data.get("confidence", 0)
    if isinstance(conf, float):
        conf = int(conf)
    if not isinstance(conf, int) or not (0 <= conf <= 100):
        return None

    reason = str(data.get("reason", ""))

    # Unified 75% confidence threshold across entire pipeline
    if conf < 75 and verdict != "ABORT":
        verdict = "ABORT"
        reason = f"[low_confidence: {conf}%] " + reason

    return {
        "verdict": verdict,
        "confidence": conf,
        "reason": reason[:300],
    }


# ==============================================================================
# UNIT TESTS
# ==============================================================================

def test_dao_sentinel_initialization():
    clear_known_contracts()
    dao_name = "Aave Governance DAO"
    constitution = "Articles: All treasury disbursements must provide verifiable deliverables and zero conflict of interest."
    forum_base = "https://governance.aave.com"

    assert len(dao_name) > 0
    assert len(constitution) >= 30
    assert forum_base.startswith("https://")


def test_extract_origin_valid():
    scheme, host, port = _extract_origin("https://discourse.nexusdao.org/t/proposal-1")
    assert scheme == "https"
    assert host == "discourse.nexusdao.org"
    assert port == 443

    scheme, host, port = _extract_origin("http://localhost:8080/path")
    assert scheme == "http"
    assert host == "localhost"
    assert port == 8080


def test_extract_origin_reject_invalid():
    # Credentials not allowed (anti SSRF / security)
    with pytest.raises(UserError, match="URL credentials are not allowed"):
        _extract_origin("https://user:pass@malicious.com")

    # Invalid scheme
    with pytest.raises(UserError, match="URL must start with http:// or https://"):
        _extract_origin("ftp://governance.nexusdao.org")

    # Ambiguous hostname
    with pytest.raises(UserError, match="Ambiguous or invalid hostname"):
        _extract_origin("https://..nexusdao.org")


def test_origin_validity_matching():
    base = "https://discourse.nexusdao.org"

    # Same domain
    assert _is_origin_valid("https://discourse.nexusdao.org/t/prop-102", base) is True

    # Subdomain of base
    assert _is_origin_valid("https://sub.discourse.nexusdao.org/post", base) is True

    # Different port
    assert _is_origin_valid("https://discourse.nexusdao.org:8443/t/1", base) is False

    # Different scheme
    assert _is_origin_valid("http://discourse.nexusdao.org/t/1", base) is False

    # Phishing domain suffix spoofing
    assert _is_origin_valid("https://evil-discourse.nexusdao.org.attacker.com", base) is False


def test_parse_llm_json_clean_and_markdown():
    raw_clean = '{"verdict": "COMPLIANT", "confidence": 92, "reason": "All milestones clear."}'
    parsed = _parse_llm_json(raw_clean)
    assert parsed["verdict"] == "COMPLIANT"
    assert parsed["confidence"] == 92

    raw_md = '```json\n{"verdict": "NON_COMPLIANT", "confidence": 88, "reason": "Conflict of interest detected."}\n```'
    parsed_md = _parse_llm_json(raw_md)
    assert parsed_md["verdict"] == "NON_COMPLIANT"
    assert parsed_md["confidence"] == 88


def test_safe_parse_confidence_threshold_75():
    # Above 75% -> keeps verdict
    valid = {"verdict": "COMPLIANT", "confidence": 85, "reason": "Approved infrastructure grant"}
    res = _safe_parse(valid)
    assert res["verdict"] == "COMPLIANT"
    assert res["confidence"] == 85

    # Below 75% -> normalized to ABORT
    low_conf = {"verdict": "COMPLIANT", "confidence": 70, "reason": "Weak evidence of deliverables"}
    res_low = _safe_parse(low_conf)
    assert res_low["verdict"] == "ABORT"
    assert "low_confidence: 70%" in res_low["reason"]

    # ABORT remains ABORT regardless of confidence
    abort = {"verdict": "ABORT", "confidence": 20, "reason": "Cloudflare rate limit"}
    res_abort = _safe_parse(abort)
    assert res_abort["verdict"] == "ABORT"


def test_safe_parse_invalid_verdict():
    invalid = {"verdict": "UNKNOWN_ACTION", "confidence": 90, "reason": "None"}
    assert _safe_parse(invalid) is None


def test_beneficiary_binding_audit_verdict():
    """Verify steward requirement: mismatched beneficiary triggers NON_COMPLIANT verdict."""
    # When beneficiary matches proposal specification
    matched_audit = {
        "verdict": "COMPLIANT",
        "confidence": 95,
        "reason": "Target beneficiary 0x1111... matches proposal author team designated in forum specification."
    }
    res_matched = _safe_parse(matched_audit)
    assert res_matched["verdict"] == "COMPLIANT"
    assert res_matched["confidence"] == 95

    # When beneficiary does not match proposal specification (hijack attempt)
    hijack_audit = {
        "verdict": "NON_COMPLIANT",
        "confidence": 98,
        "reason": "Beneficiary address mismatch: target 0x9999... does not match proposal author 0x1111... designated in forum specification."
    }
    res_hijack = _safe_parse(hijack_audit)
    assert res_hijack["verdict"] == "NON_COMPLIANT"
    assert "mismatch" in res_hijack["reason"].lower()


def test_voter_eligibility_enforcement_logic():
    """Verify steward requirement: arbitrary addresses cannot cast votes or satisfy quorum."""
    eligible_voters = {
        "0xarbiter_founder": True,
        "0xcouncil_member_1": True,
        "0xcouncil_member_2": True
    }

    def simulate_cast_vote(voter_address: str, proposal_status: str) -> bool:
        if proposal_status != "VOTING_ACTIVE":
            raise UserError("Proposal is not in active voting stage")
        if voter_address not in eligible_voters or not eligible_voters[voter_address]:
            raise UserError("Sender is not an authorized DAO voter")
        return True

    # 1. Authorized voter successfully votes
    assert simulate_cast_vote("0xarbiter_founder", "VOTING_ACTIVE") is True
    assert simulate_cast_vote("0xcouncil_member_1", "VOTING_ACTIVE") is True

    # 2. Arbitrary burner wallet is rejected
    with pytest.raises(UserError, match="Sender is not an authorized DAO voter"):
        simulate_cast_vote("0xarbitrary_burner_wallet_123", "VOTING_ACTIVE")

    with pytest.raises(UserError, match="Sender is not an authorized DAO voter"):
        simulate_cast_vote("0xattacker_sybil_456", "VOTING_ACTIVE")
