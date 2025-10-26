# validate_readytensor.py
import os
import sys
import re
import pathlib

def check_repo():
    root = pathlib.Path(".")
    issues = []

    # 1. README.md exists
    readme_path = root / "README.md"
    if not readme_path.exists():
        issues.append("README.md missing")
    else:
        # Check for license mention
        try:
            content = readme_path.read_text(encoding="utf-8", errors="ignore")
            if not re.search(r"license", content, re.IGNORECASE):
                issues.append("License not mentioned in README.md")
        except Exception as e:
            issues.append(f"Could not read README.md: {e}")

    # 2. Environment file
    env_files = ["requirements.txt", "environment.yml", "pyproject.toml"]
    if not any((root / f).exists() for f in env_files):
        issues.append("No environment file (requirements.txt, environment.yml, or pyproject.toml)")

    # 3. .gitignore
    if not (root / ".gitignore").exists():
        issues.append(".gitignore missing")

    # 4. docs/ folder (recommended)
    if not (root / "docs").exists() and not (root / "doc").exists():
        issues.append("docs/ folder missing (recommended for documentation)")

    # 5. Optional: Check for a license file
    license_files = ["LICENSE", "LICENSE.txt", "LICENSE.md"]
    if not any((root / f).exists() for f in license_files):
        issues.append("No LICENSE file found (recommended)")

    return issues

def main():
    print("ReadyTensor Publication Checklist")
    print("=" * 50)
    
    issues = check_repo()
    
    if issues:
        print("\nFailed items:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print(f"\nPlease fix the {len(issues)} issue(s) above before publishing.")
        sys.exit(1)
    else:
        print("\nAll checks PASSED!")
        print("Your repository meets ReadyTensor best practices.")
        print("Ready to link in the 'Models' section and publish!")
        sys.exit(0)

if __name__ == "__main__":
    main()