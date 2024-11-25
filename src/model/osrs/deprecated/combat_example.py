import shutil
import time
from pathlib import Path

import utilities.api.item_ids as item_ids
import utilities.game_launcher as launcher
from model.bot import BotStatus
from model.osrs.osrs_bot import OSRSBot
from utilities.api.deprecated.morg_http_client import MorgHTTPClient
from utilities.api.deprecated.status_socket import StatusSocket


class OSRSCombat(OSRSBot):
    def __init__(self):
        bot_title = "Combat"
        description = (
            "This bot kills NPCs. Position your character near some NPCs and highlight"
            " them.\nTHIS SCRIPT IS AN EXAMPLE, DO NOT USE LONGTERM."
        )
        super().__init__(bot_title=bot_title, description=description)
        self.running_time: int = 1
        self.loot_items: str = ""
        self.hp_threshold: int = 0

    def create_options(self):
        self.options_builder.add_slider_option(
            "running_time", "How long to run (minutes)?", 1, 600
        )
        self.options_builder.add_text_edit_option(
            "loot_items",
            "Loot items (requires re-launch):",
            "E.g., Coins, Dragon bones",
        )
        self.options_builder.add_slider_option(
            "hp_threshold", "Low HP threshold (0-100)?", 0, 100
        )

    def save_options(self, options: dict):
        for option in options:
            if option == "running_time":
                self.running_time = options[option]
            elif option == "loot_items":
                self.loot_items = options[option]
            elif option == "hp_threshold":
                self.hp_threshold = options[option]
            else:
                self.log_msg(f"Unknown option: {option}")
                print(
                    "Developer: ensure that the option keys are correct, and that"
                    " options are being unpacked correctly."
                )
                self.options_set = False
                return

        self.log_msg(f"Running time: {self.running_time} minutes.")
        self.log_msg(f'Loot items: {self.loot_items or "None"}.')
        self.log_msg(f"Bot will eat when HP is below: {self.hp_threshold}.")
        self.log_msg(
            "Options set successfully. Please launch RuneLite with the button on the"
            " right to apply settings."
        )

        self.options_set = True
        self.log_msg("Options set successfully.")

    def main_loop(self):
        self.log_msg(
            "WARNING: This script is for testing and may not be safe for personal use."
            " Please modify it to suit your needs."
        )

        # Setup API
        api_morg = None
        api_status = StatusSocket()

        self.toggle_auto_retaliate(True)

        self.log_msg("Selecting inventory...")
        self.open_control_panel_tab("inventory")

        failed_searches = 0

        # Main loop
        start_time = time.time()
        end_time = self.running_time * 60
        while time.time() - start_time < end_time:
            # If inventory is full...
            if api_status.is_inv_full():
                self.log_msg("Inventory is full. Idk what to do.")
                self.set_status(BotStatus.STOPPED)
                return

            # While not in combat
            while not api_morg.is_in_combat():
                # Find a target
                target = self.get_nearest_tagged_NPC()
                if target is None:
                    failed_searches += 1
                    if failed_searches % 10 == 0:
                        self.log_msg("Searching for targets...")
                    if failed_searches > 60:
                        # If we've been searching for a whole minute...
                        self.__logout("No tagged targets found. Logging out.")
                        return
                    time.sleep(1)
                    continue
                failed_searches = 0

                # Click target if mouse is actually hovering over it, else recalculate
                self.mouse.move_to(target.random_point)
                if not self.get_mouseover_text(
                    contains="Attack", colors=self.cp.bgr.OFF_WHITE_TEXT
                ):
                    continue
                self.mouse.click()
                time.sleep(0.5)

            # While in combat
            while api_morg.is_in_combat():
                # Check to eat food
                if self.get_hp() < self.hp_threshold:
                    self.__eat(api_status)
                time.sleep(1)

            # Loot all highlighted items on the ground
            if self.loot_items:
                self.__loot(api_status)

            self.update_progress((time.time() - start_time) / end_time)

        self.update_progress(1)
        self.__logout("Finished.")

    def __eat(self, api: StatusSocket):
        self.log_msg("HP is low.")
        food_slots = api.get_inv_item_indices(item_ids.all_food)
        if len(food_slots) == 0:
            self.log_msg("No food found. Pls tell me what to do...")
            self.set_status(BotStatus.STOPPED)
            return
        self.log_msg("Eating food...")
        self.mouse.move_to(self.win.inventory_slots[food_slots[0]].random_point())
        self.mouse.click()

    def __loot(self, api: StatusSocket):
        """Picks up loot while there is loot on the ground"""
        while self.pick_up_loot(self.loot_items):
            if api.is_inv_full():
                self.__logout("Inventory full. Cannot loot.")
                return
            curr_inv = len(api.get_inv())
            self.log_msg("Picking up loot...")
            for _ in range(5):  # give the bot 5 seconds to pick up the loot
                if len(api.get_inv()) != curr_inv:
                    self.log_msg("Loot picked up.")
                    time.sleep(1)
                    break
                time.sleep(1)

    def __logout(self, msg):
        self.log_msg(msg)
        self.logout()
        self.stop()
