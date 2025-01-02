import sys
import os
import utils

# Add the project root directory to sys.path if it's not already there
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    print("Adding root")
    sys.path.append(parent_dir)


def retrieve_registries():
    retrieval_options = """[1] Australia
[2] England and Wales
[3] New Zealand
[4] United States
[A] Run All
[X] Exit"""

    print(retrieval_options)

    selection = input("Choose option(s), comma separate if multiple: ")
    all_options = [str(x) for x in range(1, 5)] # - [ ] make sure this updates when adding a country
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
        elif s == "4":
            import scripts.UnitedStates.retrieve as ustates
            ustates.run_everything("United States/")


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
        try:
            selection = input("Choose operation: ")
        except UnicodeDecodeError:
            print("\nIt appears that the previous operation was interrupted. Please restart interface to choose another operation.")
            break

        if selection == "1":
            utils.status_check()
        elif selection == "2":
            retrieve_registries()
        elif selection == "3":
            utils.keyword_match_assist()
        elif selection == "4":
            batch_size = input("How many matches to make? (Use `!` for all) ")
            if batch_size == "!":
                utils.run_all_match_filings()
            try:
                utils.run_all_match_filings(int(batch_size))
            except ValueError:
                print(f"⚠️ {batch_size} is not an integer. Cannot execute.")
        elif selection == "5":
            utils.get_random_entity(display="No Original", hard_limit=5000)
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
