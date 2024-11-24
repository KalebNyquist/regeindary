import sys
import os
import utils
from pprint import pp

# Add the project root directory to sys.path if it's not already there
# This allows for same functionality in Anaconda Powershell as in Pycharm
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    print("Adding root")
    sys.path.append(parent_dir)
pp(sys.path)


def retrieve_registries():
    retrieval_options = """[1] Australia
[2] England and Wales
[3] New Zealand
[A] Run All
[X] Exit"""

    print(retrieval_options)

    selection = input("Choose option(s), comma separate if multiple: ")
    all_options = [str(x) for x in range(1, 4)]
    if selection == "A":
        selection = all_options
        print("Running all options:", selection)
    elif selection == "X":
        return
    else:
        selection = selection.split(",")

    for s in selection:
        if s not in all_options:
            print(s, "not a valid option")
            continue

        if s == "1":
            import scripts.Australia.retrieve as aussie
            aussie.run_everything("Australia/")
        elif s == "2":
            import scripts.EnglandWales.retrieve as engwal
            engwal.run_everything("EnglandWales/")
        elif s == "3":
            import scripts.NewZealand.retrieve as newzee
            newzee.run_everything("NewZealand/")

    print("✔ All Selected Registries Retrieved")


def menu_select():
    print("Welcome to Regeindary")
    print("=====================")
    print("[1] Run Status Check")
    print("[2] Retrieve Registries")
    print("[3] Keyword Match Assist")
    print("[4] Match Filings with Entities")
    print("[5] Display Random Entity")
    print("[H] Hello World")
    print("[x] Quit")

    while True:
        selection = input("Choose operation: ")
        if selection == "1":
            utils.status_check()
        elif selection == "2":
            retrieve_registries()
        elif selection == "3":
            utils.keyword_match_assist()
        elif selection == "4":
            utils.run_all_match_filings()
        elif selection == "5":
            utils.print_random_entity()
        elif selection == "H":
            print("Hello world!")
        elif selection.lower() == "x":
            break
        else:
            "Invalid selection."
        print("\n", end="")


if __name__ == "__main__":
    menu_select()
    print("Terminating.")
