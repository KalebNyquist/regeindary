"""Interactive command-line interface for Regeindary operations.

This module provides the main menu system for retrieving registry data,
checking database status, matching filings to entities, and other administrative tasks.
"""
import sys
import os
import utils
import logging

logger = logging.getLogger(__name__)

# Add the project root directory to sys.path if it's not already there
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    logger.debug(f"Adding project root to sys.path: {parent_dir}")
    sys.path.append(parent_dir)


def retrieve_registries():
    """Interactive menu for selecting and retrieving data from available registries.

    Prompts user to select one or more registries to download and import data from.
    Supports individual selection, multiple selections (comma-separated), or 'A' for all registries.

    Options:
        [1] Australia
        [2] England and Wales
        [3] New Zealand
        [4] United States
        [A] Run All
        [X] Exit
    """
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
        logger.info(f"Running all registry imports: {selection}")
    elif selection == "X":
        logger.info("User exited registry selection")
        return
    else:
        selection = selection.split(",")

    for s in selection:
        if s not in all_options:
            logger.warning(f"Invalid registry option selected: {s}")
            print(f"⚠️  '{s}' is not a valid option")
            continue

        if s == "1":
            logger.info("Starting Australia registry import")
            import scripts.Australia.retrieve as aussie
            aussie.run_everything("Australia/")
        elif s == "2":
            logger.info("Starting England & Wales registry import")
            import scripts.EnglandWales.retrieve as engwal
            engwal.run_everything("EnglandWales/")
        elif s == "3":
            logger.info("Starting New Zealand registry import")
            import scripts.NewZealand.retrieve as newzee
            newzee.run_everything("NewZealand/")
        elif s == "4":
            logger.info("Starting United States registry import")
            import scripts.UnitedStates.retrieve as ustates
            ustates.run_everything("United States/")

    logger.info("✔ All selected registry imports completed")
    print("✔ All Selected Registries Retrieved")


def menu_select():
    """Main interactive menu for Regeindary operations.

    Displays a menu of available operations and processes user selections in a loop
    until the user chooses to quit. Handles UnicodeDecodeError gracefully.

    Menu Options:
        [1] Run Status Check - Display database statistics
        [2] Retrieve Registries - Download and import registry data
        [3] Keyword Match Assist - Check field mapping coverage
        [4] Match Filings with Entities - Link filings to organizations
        [5] Display Random Entity - Inspect a random organization record
        [H] Hello World - Test function
        [x] Quit - Exit the program
    """
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
            logger.error("UnicodeDecodeError encountered during input")
            print("\n⚠️  Previous operation was interrupted. Please restart interface to choose another operation.")
            break

        if selection == "1":
            logger.info("User selected: Status Check")
            utils.status_check()
        elif selection == "2":
            logger.info("User selected: Retrieve Registries")
            retrieve_registries()
        elif selection == "3":
            logger.info("User selected: Keyword Match Assist")
            utils.keyword_match_assist()
        elif selection == "4":
            logger.info("User selected: Match Filings with Entities")
            batch_size = input("How many matches to make? (Use `!` for all) ")
            if batch_size == "!":
                logger.info("Matching all unmatched filings")
                utils.run_all_match_filings()
            else:
                try:
                    batch_count = int(batch_size)
                    logger.info(f"Matching {batch_count:,} filings")
                    utils.run_all_match_filings(batch_count)
                except ValueError:
                    logger.warning(f"Invalid batch size entered: {batch_size}")
                    print(f"⚠️  '{batch_size}' is not a valid integer. Cannot execute.")
        elif selection == "5":
            logger.info("User selected: Display Random Entity")
            utils.get_random_entity(display="No Original", hard_limit=5000)
        elif selection == "H":
            logger.debug("Hello World test function called")
            print("Hello world!")
        elif selection.lower() == "x":
            logger.info("User exited application")
            break
        else:
            logger.warning(f"Invalid menu selection: {selection}")
            print("⚠️  Invalid selection.")
        print("\n", end="")


if __name__ == "__main__":
    menu_select()
    print("Terminating.")
