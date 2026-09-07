#!/usr/bin/env python3
"""
Deployment script for DAOComplianceSentinel Intelligent Contract on GenLayer Studionet.
RPC: https://studio.genlayer.com/api (Chain ID: 61999)
"""

import os
import sys
import json
from pathlib import Path
from genlayer_py import create_client, create_account, generate_private_key, studionet

def deploy():
    print("=================================================================", flush=True)
    print("   Deploying DAOComplianceSentinel to GenLayer Studionet        ", flush=True)
    print("=================================================================\n", flush=True)

    client = create_client(studionet)

    # Use environment private key or generate an ephemeral deployer account
    pk = os.environ.get("DEPLOYER_PRIVATE_KEY", "").strip()
    if pk:
        account = create_account(pk)
        print(f"[+] Deployer Account (from ENV): {account.address}", flush=True)
    else:
        account = create_account(generate_private_key())
        print(f"[+] Deployer Account (Generated): {account.address}", flush=True)
        print("[+] Requesting faucet funds from Studionet...", flush=True)
        try:
            client.fund_account(address=account.address, amount=1000)
            print("[+] Account funded successfully!", flush=True)
        except Exception as e:
            print(f"[!] Funding notification: {e}", flush=True)

    contract_path = Path(__file__).parent.parent / "contracts" / "Contract.py"
    with open(contract_path, "r", encoding="utf-8") as f:
        contract_code = f.read()

    # GenVM wasm runner requires the runner comment (`# { "Depends": ... }`) on line 1 for raw RPC transactions
    deploy_code = contract_code
    if deploy_code.startswith("# v"):
        lines = deploy_code.splitlines(keepends=True)
        deploy_code = "".join(lines[1:])

    # Constructor Parameters:
    dao_name = "Nexus Protocol DAO"
    dao_constitution = (
        "Article 1: Treasury grants must directly fund protocol infrastructure. "
        "Article 2: Any proposal lacking milestone breakdown or exhibiting conflict of interest is strictly forbidden."
    )
    max_single_grant_limit = 1000000000000000000000  # 1000 GEN (in wei: 10^21)
    governance_forum_base = "https://discourse.nexusdao.org"

    print("[+] Constructor Parameters:", flush=True)
    print(f"    - dao_name               : {dao_name}", flush=True)
    print(f"    - dao_constitution       : {dao_constitution[:60]}...", flush=True)
    print(f"    - max_single_grant_limit : {max_single_grant_limit} (1000 GEN)", flush=True)
    print(f"    - governance_forum_base  : {governance_forum_base}", flush=True)
    print("\n[+] Sending deploy_contract transaction to Studionet...", flush=True)

    args = [
        dao_name,
        dao_constitution,
        max_single_grant_limit,
        governance_forum_base
    ]

    tx_hash = client.deploy_contract(
        code=deploy_code,
        account=account,
        args=args,
        leader_only=False
    )
    print(f"[+] Deployment Transaction Hash: {tx_hash}", flush=True)
    print("[+] Waiting for transaction finality and validator consensus on Studionet...", flush=True)

    receipt = client.wait_for_transaction_receipt(tx_hash)
    contract_address = receipt.get("contract_address") or receipt.get("recipient")
    status = receipt.get("status") or receipt.get("result")

    print("\n=================================================================")
    print("               DEPLOYMENT CONFIRMED ON STUDIONET                ")
    print("=================================================================")
    print(f"Contract Address : {contract_address}")
    print(f"Transaction Hash : {tx_hash}")
    print(f"Deployer Address : {account.address}")
    print(f"Receipt Status   : {status}")
    print("=================================================================\n")

    output_info = {
        "network": "studionet",
        "chainId": 61999,
        "rpcUrl": "https://studio.genlayer.com/api",
        "contractAddress": contract_address,
        "transactionHash": tx_hash,
        "deployerAddress": account.address,
        "status": str(status),
        "constructorArgs": {
            "dao_name": dao_name,
            "dao_constitution": dao_constitution,
            "max_single_grant_limit": str(max_single_grant_limit),
            "governance_forum_base": governance_forum_base
        },
        "receipt": {k: str(v) for k, v in receipt.items() if k != "code"}
    }

    dep_file = Path(__file__).parent.parent / "deployment.json"
    with open(dep_file, "w", encoding="utf-8") as f:
        json.dump(output_info, f, indent=2)
    print(f"[+] Saved deployment details to {dep_file}")

    return output_info

if __name__ == "__main__":
    deploy()
