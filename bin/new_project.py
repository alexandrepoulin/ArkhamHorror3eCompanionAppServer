#!/usr/bin/env python3
import argparse
import os
import sys


def validate_name(name: str) -> None:
    if "-" in name:
        print(f"{name} cannot have a '-' character.")
        sys.exit(1)
    if " " in name:
        print(f"{name} cannot have a ' ' character.")
        sys.exit(1)
    if os.path.isdir(name):
        print(f"{name} already exists!")
        sys.exit(1)


def create_project(name: str) -> None:
    os.system(f"git clone https://github.com/alexandrepoulin/python_project_starter {name}")
    os.chdir(name)
    os.system("git remote remove origin")
    os.system(f"sed -i 's/$MYPROJECT/{name}/g' pyproject.toml")
    os.system(f"sed -i 's/$MYPROJECT/{name}/g' rust/Cargo.toml")
    os.system(f"sed -i 's/$MYPROJECT/{name}/g' tests/test_all.py")
    os.system(f"sed -i 's/$MYPROJECT/{name}/g' src/project_starter/__main__.py")
    os.rename("src/project_starter", f"src/{name}")


def main():
    parser = argparse.ArgumentParser(
        prog="new_project",
        description="Create a new project with from the template project_name in the current directory",
    )
    parser.add_argument("project_name", type=str, help="Name of the project")
    args = parser.parse_args()
    name = args.project_name
    validate_name(name)
    create_project(name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
