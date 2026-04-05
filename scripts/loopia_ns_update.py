#!/usr/bin/env python3
"""
Loopia XML-RPC NS updater.
Updates nameservers for all domains in Loopia account to Cloudflare NS.

Usage:
  python3 loopia_ns_update.py --user YOUR_LOOPIA_USERNAME --pass YOUR_API_PASSWORD
  python3 loopia_ns_update.py --user YOUR_LOOPIA_USERNAME --pass YOUR_API_PASSWORD --list
  python3 loopia_ns_update.py --user YOUR_LOOPIA_USERNAME --pass YOUR_API_PASSWORD --domain example.se
"""

import xmlrpc.client
import argparse
import sys
import json

LOOPIA_API_URL = "https://api.loopia.se/RPCSERV"
CF_NS = ["ada.ns.cloudflare.com", "kianchau.ns.cloudflare.com"]

# Domains we want to point to Cloudflare
TARGET_DOMAINS = [
    # Worker domains (already have CF zones, just need NS to propagate)
    "shopifyexperter.se",
    "shopifybyrå.se",
    "shopifykonsulter.se",
    "magentoexperten.se",
    "magento-konsulter.se",
    "adobecommerce.se",
    "ehandelkonsult.se",
    "klaviyo.se",
    "punchout.nu",
    # Pages domains (need CF zone + custom domain configured)
    "ehandelinstitutet.se",
    "wunderwerk-b2b.se",
    "pimsystem.se",
    "magento-pwa.se",
    "orionheadless.se",
    "ecomeagency.se",
    "e-handelsystem.se",
    "digitalhandel.se",
    "magentocommerce.se",
    "magento-webshop.se",
    "magento-sverige.se",
    "shopifypro.se",
    "shopifyexperts.com",
    "shopifyb2b.se",
    "inline-ehandel.se",
    "x-konsult.se",
    "b2b-today.se",
    # Missing CF zones (need to be added to CF first, then worker)
    "centrumhandel.se",
    "b2behandel.se",
    "starta-ehandel.se",
    "shopify-sverige.se",
    "magento-ehandel.se",
    "shopifyseo.se",
]


def get_client(user, password):
    return xmlrpc.client.ServerProxy(
        LOOPIA_API_URL,
        encoding="utf-8",
        allow_none=True,
    ), user, password


def list_domains(client, user, password):
    """List all domains in the Loopia account."""
    result = client.getDomains(user, password)
    return result


def get_ns_records(client, user, password, domain):
    """Get current NS records for a domain."""
    try:
        records = client.getZoneRecords(user, password, domain, "@")
        ns_records = [r for r in records if isinstance(r, dict) and r.get("type") == "NS"]
        return ns_records
    except Exception as e:
        return []


def set_ns_records(client, user, password, domain):
    """
    Loopia doesn't expose NS record editing via API for the domain apex.
    Use updateNameservers instead.
    """
    try:
        result = client.updateNameservers(user, password, domain, CF_NS)
        return result
    except Exception as e:
        return f"ERROR: {e}"


def check_current_ns(client, user, password, domain):
    """Check if domain already uses Cloudflare NS."""
    try:
        ns_list = client.getNameservers(user, password, domain)
        return ns_list
    except Exception as e:
        return f"ERROR: {e}"


def main():
    parser = argparse.ArgumentParser(description="Update Loopia domain NS to Cloudflare")
    parser.add_argument("--user", required=True, help="Loopia API username (e.g. niklas@dahlquist.se)")
    parser.add_argument("--pass", dest="password", required=True, help="Loopia API password")
    parser.add_argument("--list", action="store_true", help="List all domains in account")
    parser.add_argument("--domain", help="Update only this specific domain")
    parser.add_argument("--check", action="store_true", help="Only check current NS, don't update")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without doing it")
    args = parser.parse_args()

    client = xmlrpc.client.ServerProxy(LOOPIA_API_URL, encoding="utf-8", allow_none=True)

    if args.list:
        print("Fetching all domains from Loopia account...")
        domains = list_domains(client, args.user, args.password)
        print(f"\nDomains in account ({len(domains)}):")
        for d in domains:
            print(f"  {d}")
        return

    domains_to_update = [args.domain] if args.domain else TARGET_DOMAINS

    print(f"{'DRY RUN — ' if args.dry_run else ''}Checking {len(domains_to_update)} domains...\n")

    results = {"updated": [], "already_cf": [], "not_found": [], "error": []}

    for domain in domains_to_update:
        current_ns = check_current_ns(client, args.user, args.password, domain)

        if isinstance(current_ns, str) and "ERROR" in current_ns:
            # Domain not in account
            print(f"  SKIP  {domain:40} (not in Loopia account or error: {current_ns})")
            results["not_found"].append(domain)
            continue

        cf_ns_set = set(ns.lower().rstrip(".") for ns in CF_NS)
        current_ns_set = set(ns.lower().rstrip(".") for ns in (current_ns or []))

        if cf_ns_set == current_ns_set:
            print(f"  OK    {domain:40} already on Cloudflare NS")
            results["already_cf"].append(domain)
            continue

        print(f"  UPDATE {domain:40} {current_ns} -> {CF_NS}")

        if not args.dry_run and not args.check:
            result = set_ns_records(client, args.user, args.password, domain)
            if result == "OK":
                print(f"         -> SUCCESS")
                results["updated"].append(domain)
            else:
                print(f"         -> FAILED: {result}")
                results["error"].append(domain)
        else:
            results["updated"].append(domain)

    print(f"""
Summary:
  Already on Cloudflare NS : {len(results['already_cf'])}
  Updated to Cloudflare NS  : {len(results['updated'])}
  Not in Loopia account     : {len(results['not_found'])}
  Errors                    : {len(results['error'])}
""")

    if results["updated"] and not args.dry_run:
        print("NS propagation takes 1-48 hours. After propagation:")
        print("  1. CF zones will become 'active'")
        print("  2. Run: python3 cf_add_custom_domains.py to add custom domains to Pages projects")


if __name__ == "__main__":
    main()
