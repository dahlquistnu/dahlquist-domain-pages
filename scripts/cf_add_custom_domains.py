#!/usr/bin/env python3
"""
Adds custom domains to Cloudflare Pages projects.
Run after NS has propagated and CF zones are active.

Usage:
  python3 cf_add_custom_domains.py
  python3 cf_add_custom_domains.py --check   # just show status
"""

import subprocess
import json
import sys
import argparse

ACCOUNT_ID = "b1bff745b75f466e258f2df9b4c2e1fb"

# Pages project -> custom domain mappings
PAGES_CUSTOM_DOMAINS = {
    "ehandelinstitutet":              "ehandelinstitutet.se",
    "wunderwerk-b2b":                 "wunderwerk-b2b.se",
    "pimsystem":                      "pimsystem.se",
    "magento-pwa":                    "magento-pwa.se",
    "orionheadless":                  "orionheadless.se",
    "ecomeagency":                    "ecomeagency.se",
    "e-handelsystem":                 "e-handelsystem.se",
    "digitalhandel":                  "digitalhandel.se",
    "magentocommerce":                "magentocommerce.se",
    "magento-webshop":                "magento-webshop.se",
    "magento-sverige":                "magento-sverige.se",
    "shopifypro":                     "shopifypro.se",
    "shopifyexperts":                 "shopifyexperts.com",
    "shopifyb2b":                     "shopifyb2b.se",
    "inline-ehandel":                 "inline-ehandel.se",
    "x-konsult":                      "x-konsult.se",
    "b2b-today":                      "b2b-today.se",
}


def get_token():
    result = subprocess.run(
        ["grep", "oauth_token", "/Users/niklasdahlquist/Library/Preferences/.wrangler/config/default.toml"],
        capture_output=True, text=True
    )
    for line in result.stdout.splitlines():
        if "oauth_token" in line:
            return line.split('"')[1]
    sys.exit("Could not find wrangler oauth_token")


def cf_api(token, method, path, body=None):
    import urllib.request
    url = f"https://api.cloudflare.com/client/v4{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_active_zones(token):
    resp = cf_api(token, "GET", f"/zones?account.id={ACCOUNT_ID}&status=active")
    return {z["name"]: z["id"] for z in resp.get("result", [])}


def get_pages_project_domains(token, project_name):
    resp = cf_api(token, "GET", f"/accounts/{ACCOUNT_ID}/pages/projects/{project_name}")
    return resp.get("result", {}).get("domains", [])


def add_custom_domain(token, project_name, domain):
    """Add custom domain to a Pages project."""
    return cf_api(
        token, "POST",
        f"/accounts/{ACCOUNT_ID}/pages/projects/{project_name}/domains",
        {"name": domain}
    )


def main():
    parser = argparse.ArgumentParser(description="Add custom domains to CF Pages projects")
    parser.add_argument("--check", action="store_true", help="Only check status, no changes")
    args = parser.parse_args()

    token = get_token()

    print("Fetching active CF zones...")
    active_zones = get_active_zones(token)
    print(f"Active zones: {list(active_zones.keys())}\n")

    results = {"added": [], "already_set": [], "no_zone": [], "error": []}

    for project, domain in PAGES_CUSTOM_DOMAINS.items():
        # Check if zone is active
        if domain not in active_zones:
            print(f"  SKIP  {project:30} {domain} (CF zone not active yet)")
            results["no_zone"].append(domain)
            continue

        # Check if already set
        current_domains = get_pages_project_domains(token, project)
        if domain in current_domains:
            print(f"  OK    {project:30} {domain} already configured")
            results["already_set"].append(domain)
            continue

        print(f"  ADD   {project:30} {domain}")
        if not args.check:
            try:
                result = add_custom_domain(token, project, domain)
                if result.get("success"):
                    print(f"         -> SUCCESS")
                    results["added"].append(domain)
                else:
                    errs = result.get("errors", [])
                    print(f"         -> FAILED: {errs}")
                    results["error"].append(domain)
            except Exception as e:
                print(f"         -> ERROR: {e}")
                results["error"].append(domain)

    print(f"""
Summary:
  Custom domains added      : {len(results['added'])}
  Already configured        : {len(results['already_set'])}
  CF zone not active yet    : {len(results['no_zone'])}
  Errors                    : {len(results['error'])}
""")
    if results["no_zone"]:
        print("Domains waiting for NS propagation:")
        for d in results["no_zone"]:
            print(f"  {d}")


if __name__ == "__main__":
    main()
