# DAOComplianceSentinel: Autonomous AI Constitution & Governance Gatekeeper

> **An Intelligent Contract deployed on GenLayer StudioNet acting as an automated on-chain constitutional supreme court and gatekeeper for DAO governance and treasury disbursements.**

[![Network: GenLayer StudioNet](https://img.shields.io/badge/Network-GenLayer%20StudioNet%20(61999)-4F46E5.svg)](https://studio.genlayer.com)
[![Consensus: Optimistic Democracy](https://img.shields.io/badge/Consensus-Optimistic%20Democracy-10B981.svg)](https://docs.genlayer.com)
[![GenVM: Python v0.2.16](https://img.shields.io/badge/GenVM-Python%20v0.2.16-F59E0B.svg)](https://docs.genlayer.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 🏛️ Executive Summary & Problem Statement

Decentralized Autonomous Organizations (DAOs) manage billions of dollars in digital asset treasuries. However, existing on-chain governance mechanisms suffer from critical vulnerabilities:
1. **Governance Exploits & Treasury Drains**: Malicious actors use flash loans, bribe cartels, or voter apathy to pass proposals that siphon treasury funds into obscure accounts under vague pretenses.
2. **Constitutional Disconnect**: A DAO's mission and constitution (e.g., articles prohibiting conflict of interest, requiring milestones, or mandating protocol infrastructure focus) exist purely as off-chain text documents or forum posts. Smart contracts in EVM/Solidity cannot read natural language or evaluate whether a proposal satisfies constitutional criteria.
3. **Escrow / Bounty Paradigm Limits**: Traditional escrow contracts can hold funds, but they cannot evaluate qualitative governance proposals before community voting begins.

### The DAOComplianceSentinel Solution
**DAOComplianceSentinel** replaces manual, gameable governance with an **Autonomous On-Chain Governance Gatekeeper**:
- **Zero-Escrow Constitutional Gatekeeping**: The contract does not operate as an escrow; instead, it serves as a non-bypassable constitutional filter for the DAO's proposal lifecycle.
- **On-Chain Constitution & Policy Rules**: The DAO's constitution is stored directly on-chain and enforced programmatically.
- **Autonomous Web Extraction & AI Judicial Audit**: Independent GenLayer validator nodes scrape proposal specifications and milestone roadmaps directly from governance forums (Discourse, Snapshot, Commonwealth) without relying on centralized oracles.
- **Autonomous Veto vs. Democratic Voting**: If a proposal breaches constitutional clauses (e.g., direct treasury drain, ambiguous deliverables, conflict of interest, or exceeding budget caps), the contract immediately executes an autonomous **`VETOED_UNCONSTITUTIONAL`**. Only proposals receiving AI consensus endorsement (**`COMPLIANT`**) unlock the on-chain community voting gate (**`VOTING_ACTIVE`**).

---

## 🛡️ Steward Corrections & Enhanced Governance Security

In response to GenLayer steward review, the contract implements two critical security enhancements:

### 1. Target Beneficiary Binding & Corroboration
* **The Vulnerability**: In naive implementations, an attacker could supply a valid, compliant proposal URL from a legitimate team, but substitute their own wallet address as the `target_beneficiary`.
* **The Correction**: The stored `target_beneficiary` is explicitly bound into the non-deterministic audit prompt. The validator AI nodes are required to corroborate that the requested beneficiary address matches the designated team, author, or recipient in the fetched forum text. If an arbitrary or mismatched address is attached to a compliant proposal, the AI consensus forces a **`NON_COMPLIANT`** verdict (*"Beneficiary address mismatch or unauthorized recipient"*).

### 2. Strict DAO Voter Eligibility Enforcement
* **The Vulnerability**: Allowing arbitrary addresses to call `cast_vote` enables Sybil attacks where an attacker creates burner accounts to meet quorum requirements.
* **The Correction**: `cast_vote` strictly enforces that `gl.message.sender_address` is an authorized DAO voting member registered in `eligible_voters`. Unregistered addresses are immediately reverted with `UserError("Sender is not an authorized DAO voter")`.

---

## 🌐 Deployed Contract & Verification on StudioNet

| Parameter | Deployment Details |
|---|---|
| **Contract Name** | `DAOComplianceSentinel` (`Contract.py`) |
| **Network** | **GenLayer StudioNet** |
| **RPC Endpoint** | `https://studio.genlayer.com/api` |
| **Chain ID** | `61999` |
| **Contract Address** | `0x9Fe797ed9622d9988b26291fE2972dBBed87f821` |
| **Explorer URL** | [https://explorer-studio.genlayer.com/address/0x9Fe797ed9622d9988b26291fE2972dBBed87f821](https://explorer-studio.genlayer.com/address/0x9Fe797ed9622d9988b26291fE2972dBBed87f821) |
| **Deployment Transaction Hash** | `0xe5d901c42fa12f1acbe7b2eb90242c098574d5e9d83c5cd64f26293965b54628` |
| **Deployer Address** | `0xb15CF3Ce17B312Ce1e61566c4F69eF6395d55763` |
| **Transaction Status** | `ACCEPTED` / `FINALIZED` (Result: `SUCCESS`) |
| **Consensus Result** | `MAJORITY_AGREE` (4/5 Validators voted Agree) |

### Initial Constructor Configuration
- **`dao_name`**: `"Nexus Protocol DAO"`
- **`dao_constitution`**: `"Article 1: Treasury grants must directly fund protocol infrastructure. Article 2: Any proposal lacking milestone breakdown or exhibiting conflict of interest is strictly forbidden."`
- **`max_single_grant_limit`**: `1000000000000000000000` (1,000 GEN)
- **`governance_forum_base`**: `"https://discourse.nexusdao.org"`

---

## 🔬 Architectural Deep Dive: Optimistic Democracy & GenVM

```
                    +-------------------------------------------------------------+
                    |                   DAO Member / Proposer                     |
                    +-------------------------------------------------------------+
                                                   |
                                                   | submit_and_audit_proposal(...)
                                                   v
                    +-------------------------------------------------------------+
                    |                DAOComplianceSentinel Contract               |
                    |    (Hard-Cap Check: amount <= max_single_grant_limit)       |
                    +-------------------------------------------------------------+
                                                   |
                                                   | Deterministic limit passed
                                                   v
                         [ gl.vm.run_nondet(leader_fn, validator_fn) ]
                                                   |
             +-------------------------------------+-------------------------------------+
             |                                                                           |
             v (Leader Node)                                                             v (Validator Nodes)
+------------------------------------------+                               +------------------------------------------+
| 1. gl.nondet.web.render(spec_url)        |                               | 1. Re-render spec URL                    |
|    - Fetch Discourse / Snapshot spec     |                               | 2. Re-prompt local LLM                   |
| 2. Dual-sample LLM prompt execution:     |                               | 3. Compare semantic VERDICT:             |
|    - Audits budget, milestones, goals    |                               |    mine['verdict'] == leader['verdict']  |
|    - Binds & verifies target_beneficiary |                               |    & (mine['conf'] >= 75) == (leader>=75)|
|    - Requires confidence >= 75%          |                               +------------------------------------------+
+------------------------------------------+                                             |
             |                                                                           |
             +-------------------------------------+-------------------------------------+
                                                   |
                                                   v
                              [ Optimistic Democracy Consensus Vote ]
                                                   |
                    +------------------------------+------------------------------+
                    |                                                             |
            COMPLIANT (conf >= 75%)                                   NON_COMPLIANT (conf >= 75%)
                    |                                                             |
                    v                                                             v
       +-------------------------+                                   +-------------------------+
       |   Status: VOTING_ACTIVE |                                   | Status: VETOED_UNCONST. |
       | (Only Eligible Voters)  |                                   |  (Proposal Terminated)  |
       +-------------------------+                                   +-------------------------+
                    |
                    v cast_vote(support: bool) [Enforces eligible_voters]
       +-------------------------+
       |   finalize_vote(...)    |
       |  -> PASSED / REJECTED   |
       +-------------------------+
```

### 1. Semantic Equivalence Principle
Unlike trivial smart contracts that perform exact string comparisons on unpredictable LLM outputs, `DAOComplianceSentinel` implements **custom semantic validation**:
```python
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

    # Validator verifies the core constitutional decision and confidence threshold,
    # ignoring superficial variations in the natural language reasoning text.
    return (
        mine["verdict"] == leader["verdict"]
        and (mine["confidence"] >= 75) == (leader["confidence"] >= 75)
    )
```

### 2. Multi-Sampling Stability Guard
Inside `leader_fn()`, the leader executes two independent prompt evaluations (`raw1` and `raw2`). If the verdicts diverge between the two internal samples, the leader immediately self-quarantines the result to `ABORT` (`multi_sample_divergence`), preventing erratic prompts from reaching the validator network.

### 3. Unified 75% Confidence Threshold
A strict 75% confidence threshold is enforced across all pipeline stages:
- The LLM prompt instructions require `confidence >= 75`.
- Parser normalization converts any low-confidence verdict (< 75%) into `ABORT`.
- Validator nodes verify confidence parity.
- Post-consensus normalization provides a deterministic fallback.

### 4. Anti-SSRF & Forum Origin Verification
To prevent proposers from injecting arbitrary phishing or malicious web targets, `_extract_origin` and `_is_origin_valid` strictly parse URLs using `urllib.parse.urlparse`:
- Rejects embedded URL credentials (`http://user:pass@host`).
- Enforces strict scheme matching (`http` / `https`) and port binding.
- Disallows relative hostname traversals (`..`) and ambiguous prefixes.
- Enforces origin matching against `governance_forum_base`.

---

## 📦 Project Structure

```
DAOcomplianceSentinel/
├── contracts/
│   └── Contract.py               # Complete GenLayer Intelligent Contract (v0.2.16)
├── tests/
│   └── test_dao_sentinel.py      # Pytest unit test suite (URL parsing, voter eligibility, binding)
├── scripts/
│   └── deploy_studionet.py       # Automated deployment script targeting GenLayer StudioNet
├── gltest.config.yaml            # GenLayer test & network configuration
├── deployment.json               # Recorded deployment receipt, hashes, and validator votes
├── LICENSE                       # MIT License
└── README.md                     # Comprehensive documentation & architectural report
```

---

## 🛠️ Public Contract Methods

### Write Methods (`@gl.public.write`)
- **`submit_and_audit_proposal(title: str, requested_grant_amount: bigint, target_beneficiary: str, proposal_spec_url: str) -> str`**
  Submits a treasury grant proposal. Automatically checks deterministic caps, binds `target_beneficiary` into the audit prompt, and launches non-deterministic decentralized web retrieval and AI constitutional adjudication.
- **`register_voter(voter_address: str) -> None`**
  Authorizes an address as an eligible DAO voting member (restricted to platform arbiter).
- **`batch_register_voters(voter_addresses: DynArray[str]) -> None`**
  Batch authorizes multiple DAO voting members.
- **`revoke_voter(voter_address: str) -> None`**
  Revokes voting eligibility from a designated address.
- **`cast_vote(proposal_id: str, support: bool) -> None`**
  Allows authorized DAO community members to cast their vote (`for` or `against`) on proposals in `VOTING_ACTIVE` status. Reverts if sender is not registered.
- **`finalize_vote(proposal_id: str) -> str`**
  Concludes the voting process once quorum (minimum 3 votes from eligible voters) is reached. Transitions status to `PASSED` or `REJECTED`.
- **`resolve_escalated_proposal(proposal_id: str, approve_voting: bool) -> None`**
  Allows the designated platform arbiter to manually resolve an `ESCALATED` proposal caused by network timeouts or anti-bot Cloudflare captchas on the forum host.

### View Methods (`@gl.public.view`)
- **`is_eligible_voter(voter_address: str) -> bool`**
  Returns whether a given address is an authorized DAO voting member.
- **`get_proposal(proposal_id: str) -> str`**
  Returns serialized JSON containing complete proposal metadata, AI audit verdict, confidence score, constitutional reason, and vote tally.
- **`get_dao_info() -> str`**
  Returns serialized JSON describing the DAO's name, on-chain constitution, grant caps, forum URL, total proposals, and total eligible voters.

---

## 🧪 Testing & Verification

### Running Automated Unit Tests
The repository includes a comprehensive unit test suite covering initialization, URL origin extraction, anti-SSRF protections, markdown JSON stripping, confidence threshold normalization, beneficiary binding, and voter eligibility:

```bash
# Execute unit tests
pytest tests/test_dao_sentinel.py -v
```

**Test Output:**
```
tests/test_dao_sentinel.py::test_dao_sentinel_initialization PASSED      [ 11%]
tests/test_dao_sentinel.py::test_extract_origin_valid PASSED             [ 22%]
tests/test_dao_sentinel.py::test_extract_origin_reject_invalid PASSED    [ 33%]
tests/test_dao_sentinel.py::test_origin_validity_matching PASSED         [ 44%]
tests/test_dao_sentinel.py::test_parse_llm_json_clean_and_markdown PASSED [ 55%]
tests/test_dao_sentinel.py::test_safe_parse_confidence_threshold_75 PASSED [ 66%]
tests/test_dao_sentinel.py::test_safe_parse_invalid_verdict PASSED       [ 77%]
tests/test_dao_sentinel.py::test_beneficiary_binding_audit_verdict PASSED [ 88%]
tests/test_dao_sentinel.py::test_voter_eligibility_enforcement_logic PASSED [100%]
============================== 9 passed in 0.09s ==============================
```

---

## 🚀 How to Deploy & Interact on GenLayer StudioNet

### Prerequisites
1. Python 3.11+
2. Install `genlayer_py` SDK:
   ```bash
   pip install genlayer-py pytest
   ```

### Deploying via Script
```bash
python scripts/deploy_studionet.py
```

### Verifying on StudioNet via Python
```python
from genlayer_py import create_client, create_account, generate_private_key, studionet

client = create_client(studionet, account=create_account(generate_private_key()))
contract_address = "0x9Fe797ed9622d9988b26291fE2972dBBed87f821"

# Read live DAO information
dao_info = client.read_contract(
    address=contract_address,
    function_name="get_dao_info",
    args=[]
)
print("Live DAO Info:", dao_info)
```

---

## 📜 License
This project is open-source and licensed under the [MIT License](LICENSE).
