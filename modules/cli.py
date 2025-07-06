# modules/cli.py
import argparse
import yaml
from pathlib import Path

def list_modules(profile):
    modules = set(check.get("module", "core") for check in profile.get("checks", []))
    for m in sorted(modules):
        print(m)

def list_checks(profile, module=None):
    for check in profile.get("checks", []):
        if module and check.get("module") != module:
            continue
        print(f"{check['id']}: {check['name']} [{check.get('severity','-')}]")

def describe_check(profile, check_id):
    for check in profile.get("checks", []):
        if check["id"] == check_id:
            print(f"ID: {check['id']}")
            print(f"Name: {check['name']}")
            print(f"Module: {check.get('module', 'core')}")
            print(f"Severity: {check.get('severity', 'low')}")
            print(f"Command: {check['command']}")
            print(f"Expected: {check.get('expect', '')}")
            print(f"Assert Type: {check.get('assert_type', 'exact')}")
            print("Tags:")
            for k, v in check.get("tags", {}).items():
                print(f"  {k}: {v}")
            return
    print(f"Check ID {check_id} not found.")

def parse_args():
    parser = argparse.ArgumentParser(description="SecAudit++ CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list-modules", help="List all modules")

    parser_checks = subparsers.add_parser("list-checks", help="List checks")
    parser_checks.add_argument("--module", help="Filter by module")

    parser_desc = subparsers.add_parser("describe-check", help="Describe a check")
    parser_desc.add_argument("check_id", help="Check ID to describe")

    parser.add_argument("--profile", default="profiles/common/baseline.yml", help="Path to profile")

    return parser.parse_args()

def main():
    args = parse_args()
    profile_path = Path(args.profile)
    if not profile_path.exists():
        print(f"Profile not found: {args.profile}")
        return
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))

    if args.command == "list-modules":
        list_modules(profile)
    elif args.command == "list-checks":
        list_checks(profile, args.module)
    elif args.command == "describe-check":
        describe_check(profile, args.check_id)
    else:
        print("No command specified")

if __name__ == "__main__":
    main()
