# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from genlayer.gl.vm import UserError
from dataclasses import dataclass
import json
from urllib.parse import urlparse


def _addr_str(addr: Address) -> str:
    try:
        return addr.as_hex.lower()
    except Exception:
        return str(addr).lower()


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


@allow_storage
@dataclass
class Proposal:
    id: str
    proposer: str
    title: str
    requested_grant_amount: bigint
    target_beneficiary: str
    proposal_spec_url: str
    status: str       # AUDITING | VOTING_ACTIVE | VETOED_UNCONSTITUTIONAL | PASSED | REJECTED | ESCALATED
    compliance_verdict: str  # COMPLIANT | NON_COMPLIANT | ABORT
    confidence: bigint
    audit_reason: str
    votes_for: bigint
    votes_against: bigint


class Contract(gl.Contract):
    proposals: TreeMap[str, Proposal]
    has_voted: TreeMap[str, bool]
    eligible_voters: TreeMap[str, bool]
    total_eligible_voters: bigint
    proposal_counter: bigint
    dao_name: str
    dao_constitution: str
    max_single_grant_limit: bigint
    governance_forum_base: str
    platform_arbiter: str

    def __init__(
        self,
        dao_name: str,
        dao_constitution: str,
        max_single_grant_limit: bigint,
        governance_forum_base: str,
    ):
        dao_name = dao_name.strip()
        dao_constitution = dao_constitution.strip()
        governance_forum_base = governance_forum_base.strip()

        if len(dao_name) < 3:
            raise UserError("DAO name too short")
        if len(dao_constitution) < 30:
            raise UserError("DAO constitution specification too short")
        if max_single_grant_limit <= bigint(0):
            raise UserError("Max grant limit must be greater than 0")

        _extract_origin(governance_forum_base)

        self.proposal_counter = bigint(0)
        self.dao_name = dao_name
        self.dao_constitution = dao_constitution
        self.max_single_grant_limit = max_single_grant_limit
        self.governance_forum_base = governance_forum_base
        self.platform_arbiter = _addr_str(gl.message.sender_address)

        # Enforce initial DAO voter eligibility (deployer is first eligible voter)
        self.eligible_voters[self.platform_arbiter] = True
        self.total_eligible_voters = bigint(1)

    @gl.public.write
    def register_voter(self, voter_address: str) -> None:
        """Designates an authorized DAO member eligible to participate in governance voting."""
        sender = _addr_str(gl.message.sender_address)
        if sender != self.platform_arbiter:
            raise UserError("Only platform arbiter can register eligible DAO voters")

        voter_address = voter_address.strip()
        try:
            addr = Address(voter_address)
        except Exception:
            raise UserError("Invalid voter address format")

        addr_str = addr.as_hex.lower()
        if addr_str not in self.eligible_voters or not self.eligible_voters[addr_str]:
            self.eligible_voters[addr_str] = True
            self.total_eligible_voters += bigint(1)

    @gl.public.write
    def batch_register_voters(self, voter_addresses: DynArray[str]) -> None:
        """Batch registers multiple authorized DAO voting council members."""
        sender = _addr_str(gl.message.sender_address)
        if sender != self.platform_arbiter:
            raise UserError("Only platform arbiter can register eligible DAO voters")

        for raw_addr in voter_addresses:
            clean_addr = raw_addr.strip()
            try:
                addr = Address(clean_addr)
            except Exception:
                continue
            addr_str = addr.as_hex.lower()
            if addr_str not in self.eligible_voters or not self.eligible_voters[addr_str]:
                self.eligible_voters[addr_str] = True
                self.total_eligible_voters += bigint(1)

    @gl.public.write
    def revoke_voter(self, voter_address: str) -> None:
        """Revokes voting eligibility from a designated address."""
        sender = _addr_str(gl.message.sender_address)
        if sender != self.platform_arbiter:
            raise UserError("Only platform arbiter can revoke eligible DAO voters")

        voter_address = voter_address.strip()
        try:
            addr = Address(voter_address)
        except Exception:
            raise UserError("Invalid voter address format")

        addr_str = addr.as_hex.lower()
        if addr_str in self.eligible_voters and self.eligible_voters[addr_str]:
            self.eligible_voters[addr_str] = False
            if self.total_eligible_voters > bigint(0):
                self.total_eligible_voters -= bigint(1)

    @gl.public.view
    def is_eligible_voter(self, voter_address: str) -> bool:
        """Checks whether a given address is an authorized DAO voting member."""
        try:
            addr = Address(voter_address.strip())
            addr_str = addr.as_hex.lower()
        except Exception:
            return False
        return addr_str in self.eligible_voters and self.eligible_voters[addr_str]

    @gl.public.write
    def submit_and_audit_proposal(
        self,
        title: str,
        requested_grant_amount: bigint,
        target_beneficiary: str,
        proposal_spec_url: str,
    ) -> str:
        """DAO member submits a treasury spend proposal, triggering autonomous constitutional audit."""
        title = title.strip()
        target_beneficiary = target_beneficiary.strip()
        proposal_spec_url = proposal_spec_url.strip()

        if len(title) < 5:
            raise UserError("Proposal title too short")
        if requested_grant_amount < bigint(0):
            raise UserError("Grant amount cannot be negative")

        try:
            beneficiary_addr = Address(target_beneficiary)
        except Exception:
            raise UserError("Invalid target beneficiary address format")

        if not _is_origin_valid(proposal_spec_url, self.governance_forum_base):
            raise UserError("Proposal specification URL must belong to registered governance forum")

        self.proposal_counter += bigint(1)
        pid = str(self.proposal_counter)

        # Deterministic hard-cap constitutional rule check
        if requested_grant_amount > self.max_single_grant_limit:
            self.proposals[pid] = Proposal(
                id=pid,
                proposer=_addr_str(gl.message.sender_address),
                title=title,
                requested_grant_amount=requested_grant_amount,
                target_beneficiary=beneficiary_addr.as_hex.lower(),
                proposal_spec_url=proposal_spec_url,
                status="VETOED_UNCONSTITUTIONAL",
                compliance_verdict="NON_COMPLIANT",
                confidence=bigint(100),
                audit_reason=f"Exceeds max single grant limit of {str(self.max_single_grant_limit)}",
                votes_for=bigint(0),
                votes_against=bigint(0),
            )
            return pid

        self.proposals[pid] = Proposal(
            id=pid,
            proposer=_addr_str(gl.message.sender_address),
            title=title,
            requested_grant_amount=requested_grant_amount,
            target_beneficiary=beneficiary_addr.as_hex.lower(),
            proposal_spec_url=proposal_spec_url,
            status="AUDITING",
            compliance_verdict="",
            confidence=bigint(0),
            audit_reason="",
            votes_for=bigint(0),
            votes_against=bigint(0),
        )

        dao_name_str = str(self.dao_name)
        constitution_str = str(self.dao_constitution)
        u_spec = str(proposal_spec_url)
        p_title = str(title)
        p_amount = str(requested_grant_amount)
        p_beneficiary = beneficiary_addr.as_hex.lower()

        def leader_fn():
            try:
                res = gl.nondet.web.render(u_spec, mode="text")
                spec_text = res.content if hasattr(res, "content") else str(res)
                if not spec_text or len(spec_text.strip()) < 30:
                    return {"verdict": "ABORT", "confidence": 0, "reason": "Proposal page empty"}
                if any(err in spec_text[:400].lower() for err in ["404 not found", "error 404"]):
                    return {"verdict": "ABORT", "confidence": 0, "reason": "Proposal page 404"}
            except Exception as e:
                return {"verdict": "ABORT", "confidence": 0, "reason": f"Web fetch failed: {str(e)}"}

            prompt = f"""
SYSTEM: You are the Autonomous Constitutional Sentinel for {dao_name_str}.
Audit whether the proposed treasury expenditure adheres strictly to the DAO Constitution and verifies beneficiary alignment.

DAO CONSTITUTION & GOVERNANCE RULES:
{constitution_str}

SUBMITTED PROPOSAL DETAILS:
- Title: {p_title}
- Requested Budget: {p_amount} wei
- Target Beneficiary Address: {p_beneficiary}

PROPOSAL TEXT & SPECIFICATION (FROM GOVERNANCE FORUM):
{spec_text[:4000]}

Rules:
- BENEFICIARY BINDING MANDATE: The fetched proposal specification MUST designate, authorize, or corroborate that the funds are intended for {p_beneficiary} (or team/proposer affiliated with {p_beneficiary}). If the proposal specifies a different recipient address, or if an arbitrary beneficiary address is attached to an otherwise compliant page, verdict MUST be NON_COMPLIANT with reason 'Beneficiary address mismatch or unauthorized recipient'.
- COMPLIANT (conf >= 75): The proposal explicitly details deliverables, verifiable milestones, aligns with DAO mission, exhibits zero conflict of interest or treasury draining, AND the target beneficiary ({p_beneficiary}) matches the proposal's authorized recipient/team.
- NON_COMPLIANT (conf >= 75): Violates constitution guidelines, vague/fraudulent deliverables, unbudgeted expenditure, malicious incentive alignment, direct treasury drain, OR beneficiary address mismatch.
- ABORT: Proposal page is password-protected, rate-limited, captcha-blocked, or unreadable.

OUTPUT ONLY STRICT JSON:
{{
  "verdict": "COMPLIANT" | "NON_COMPLIANT" | "ABORT",
  "confidence": 0-100,
  "reason": "max 300 chars technical constitutional justification"
}}
"""
            try:
                raw1 = gl.nondet.exec_prompt(prompt, response_format="json")
                raw2 = gl.nondet.exec_prompt(prompt, response_format="json")

                p1 = _safe_parse(raw1)
                p2 = _safe_parse(raw2)

                if p1 is None or p2 is None:
                    return {"verdict": "ABORT", "confidence": 0, "reason": "parse_failed"}

                if p1["verdict"] != p2["verdict"]:
                    return {"verdict": "ABORT", "confidence": 0, "reason": "multi_sample_divergence"}

                p1["confidence"] = (p1["confidence"] + p2["confidence"]) // 2
                return p1
            except Exception as e:
                return {"verdict": "ABORT", "confidence": 0, "reason": f"LLM error: {str(e)}"}

        def validator_fn(leader_res) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return False

            leader_data = leader_res.calldata if hasattr(leader_res, "calldata") else leader_res
            leader = _safe_parse(leader_data)
            if leader is None:
                return False

            mine = _safe_parse(leader_fn())
            if mine is None:
                return False

            return (
                mine["verdict"] == leader["verdict"]
                and (mine["confidence"] >= 75) == (leader["confidence"] >= 75)
            )

        result_raw = gl.vm.run_nondet(leader_fn, validator_fn)
        result = _safe_parse(result_raw)

        if result is None:
            result = {"verdict": "ABORT", "confidence": 0, "reason": "adjudication_failed"}

        verdict = result["verdict"]
        confidence = result["confidence"]
        reason = result["reason"]

        if confidence < 75 and verdict != "ABORT":
            verdict = "ABORT"

        prop = self.proposals[pid]
        prop.compliance_verdict = verdict
        prop.confidence = bigint(confidence)
        prop.audit_reason = reason

        if verdict == "COMPLIANT":
            # Passed AI audit: unlocked into active community voting stage
            prop.status = "VOTING_ACTIVE"
        elif verdict == "NON_COMPLIANT":
            # Failed constitutional compliance: immediately vetoed
            prop.status = "VETOED_UNCONSTITUTIONAL"
        else:
            prop.status = "ESCALATED"

        self.proposals[pid] = prop
        return pid

    @gl.public.write
    def cast_vote(self, proposal_id: str, support: bool) -> None:
        """Authorized DAO community members vote on proposals that passed constitutional audit."""
        if proposal_id not in self.proposals:
            raise UserError("Proposal not found")
        prop = self.proposals[proposal_id]

        if prop.status != "VOTING_ACTIVE":
            raise UserError("Proposal is not in active voting stage")

        voter = _addr_str(gl.message.sender_address)

        # Enforce DAO voter eligibility: prevent arbitrary burner wallets from voting or satisfying quorum
        if voter not in self.eligible_voters or not self.eligible_voters[voter]:
            raise UserError("Sender is not an authorized DAO voter")

        vote_key = proposal_id + "_" + voter
        if vote_key in self.has_voted and self.has_voted[vote_key]:
            raise UserError("Voter has already cast a vote on this proposal")

        self.has_voted[vote_key] = True

        if support:
            prop.votes_for += bigint(1)
        else:
            prop.votes_against += bigint(1)

        self.proposals[proposal_id] = prop

    @gl.public.write
    def finalize_vote(self, proposal_id: str) -> str:
        """Concludes the voting process once quorum/votes are cast by authorized DAO voters."""
        if proposal_id not in self.proposals:
            raise UserError("Proposal not found")
        prop = self.proposals[proposal_id]

        if prop.status != "VOTING_ACTIVE":
            raise UserError("Proposal is not in active voting status")

        total_votes = prop.votes_for + prop.votes_against
        if total_votes < bigint(3):
            raise UserError("Quorum not reached: minimum 3 votes required to finalize")

        if prop.votes_for > prop.votes_against:
            prop.status = "PASSED"
        else:
            prop.status = "REJECTED"

        self.proposals[proposal_id] = prop
        return prop.status

    @gl.public.write
    def resolve_escalated_proposal(self, proposal_id: str, approve_voting: bool) -> None:
        """Governance arbiter manually resolves an ESCALATED audit due to web rate limits."""
        if proposal_id not in self.proposals:
            raise UserError("Proposal not found")
        prop = self.proposals[proposal_id]

        if prop.status != "ESCALATED":
            raise UserError("Proposal is not escalated")

        sender = _addr_str(gl.message.sender_address)
        if sender != self.platform_arbiter:
            raise UserError("Only platform arbiter can resolve escalated proposals")

        if approve_voting:
            prop.status = "VOTING_ACTIVE"
            prop.compliance_verdict = "RESOLVED_MANUAL_COMPLIANT"
            prop.audit_reason = f"Manual override to voting active by {sender}"
        else:
            prop.status = "VETOED_UNCONSTITUTIONAL"
            prop.compliance_verdict = "RESOLVED_MANUAL_NON_COMPLIANT"
            prop.audit_reason = f"Manual veto override by {sender}"

        self.proposals[proposal_id] = prop

    @gl.public.view
    def get_proposal(self, proposal_id: str) -> str:
        if proposal_id not in self.proposals:
            raise UserError("Proposal not found")
        p = self.proposals[proposal_id]
        return json.dumps({
            "id": p.id,
            "proposer": p.proposer,
            "title": p.title,
            "requested_grant_amount": str(p.requested_grant_amount),
            "target_beneficiary": p.target_beneficiary,
            "proposal_spec_url": p.proposal_spec_url,
            "status": p.status,
            "compliance_verdict": p.compliance_verdict,
            "confidence": str(p.confidence),
            "audit_reason": p.audit_reason,
            "votes_for": str(p.votes_for),
            "votes_against": str(p.votes_against),
        })

    @gl.public.view
    def get_dao_info(self) -> str:
        return json.dumps({
            "dao_name": self.dao_name,
            "dao_constitution": self.dao_constitution,
            "max_single_grant_limit": str(self.max_single_grant_limit),
            "governance_forum_base": self.governance_forum_base,
            "total_proposals": str(self.proposal_counter),
            "total_eligible_voters": str(self.total_eligible_voters),
        })
