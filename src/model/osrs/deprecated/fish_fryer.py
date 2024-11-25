import time
from pathlib import Path
from typing import Union

import pyautogui as pag

from model.osrs.osrs_bot import OSRSBot
from utilities import img_search as imsearch
from utilities.api import animation_ids as a_ids
from utilities.api import item_ids as i_ids
from utilities.api.deprecated.morg_http_client import MorgHTTPClient
from utilities.api.deprecated.status_socket import StatusSocket
from utilities.color_util import ColorPalette


class OSRSFishFryer(OSRSBot):
    # Deprecated due to the loss of StatusSocket.
    raw_fish = [i_ids.RAW_SALMON, i_ids.RAW_TROUT]
    cooked_fish = [i_ids.SALMON, i_ids.TROUT] + i_ids.burned_fish
    cooking_styles = [a_ids.COOKING_FIRE, a_ids.COOKING_RANGE]
    fishing_styles = a_ids.fishing_animations

    def __init__(self):
        bot_title = "Fish Fryer"
        description = (
            "Catch salmon and trout at the Barbarian Village, cook them at the nearby"
            " permanent fire, then resume fishing."
        )
        super().__init__(bot_title=bot_title, description=description)
        # We can set default option values here if we'd like, and potentially override
        # needing to open the options panel.
        self.run_time = 600
        self.take_breaks = False
        self.options_set = True

        self.api_m = None
        self.api_s = StatusSocket()  # StatusSocket is better at detecting cooking.
        self.cp = ColorPalette()  # Access a variety of custom RGB and HSV color tuples.
        self.fish_dropped = 0  # Number of fish dropped.

    def create_options(self):
        """Add bot options.

        Use an `OptionsBuilder` to define the options for the bot. For each function call below, we define the type of option we want to create, its key, a label for the option that the user will see, and the possible values the user can select. The key is used in the `save_options` method to unpack the dictionary of options after the user has selected them.
        """
        self.options_builder.add_slider_option("run_time", "Runtime (minutes):", 1, 600)
        self.options_builder.add_checkbox_option("take_breaks", "Take breaks?", [" "])

    def save_options(self, options: dict):
        """Load options into the bot object.

        For each option in the dictionary, if it is an expected option, save the value as a property of the bot. If any unexpected options are found, log a warning. If an option is missing, set the `self.options_set` flag to False.
        """
        for option in options:
            if option == "run_time":
                self.run_time = int(options[option])
            elif option == "take_breaks":
                self.take_breaks = options[option] != []
            else:
                self.log_msg(f"unknown option: {option}")
                self.options_set = False
                return
        self.log_msg(f"[RUN TIME] {self.run_time} MIN", overwrite=True)
        break_time_str = f"(MAX {self.break_max}s)" if self.take_breaks else ""
        self.log_msg(f"  [BREAKS] {str(self.take_breaks).upper()} {break_time_str}")
        self.options_set = True
        self.log_msg("Options set successfully.")

    def main_loop(self):
        """Execute the main logic loop of the bot.

        Run the main game loop of
            1. Fly fish at the Barbarian village for trout and salmon.
            2. Travel to the permanent fire to cook the fish.
            3. Drop the cooked salmon, cooked trout, and burned fish.
            4. Travel back to a nearby fishing spot and resume fishing.

        For this to work as intended:
            1. Our character must begin near the fishing spots next to the Barbarian
                Village.
            2. The permanent fire must be marked as a specific color
                (e.g. `self.cp.hsv.PURPLE_MARK`) as defined in
                `utilities.api.colors_hsv`. Objects are intended to be marked with the
                Object Markers RuneLite plug-in.
            3. Screen dimmers like F.lux or Night Light on Windows should be disabled
                since the bot is sensitive to changes in color.
        """
        run_time_str = f"{self.run_time // 60}h {self.run_time % 60}m"  # e.g. 6h 0m
        self.log_msg(f"[START] ({run_time_str})", overwrite=True)
        start_time = time.time()
        self.pitch_down_and_align_camera("west")
        self.zoom_everything_out_completely()
        self.toggle_run_on_if_enough_energy()
        self.zoom(out=False, percent_zoom=0.2)
        self.open_control_panel_tab("inventory")
        end_time = int(self.run_time) * 60  # Measured in seconds.
        while time.time() - start_time < end_time:
            if self.take_breaks:
                self.potentially_take_a_break()
            if self.inv_is_full():
                if self.has_raw_fish():
                    self.resume_cooking()
                if self.has_cooked_fish():
                    self.drop_all_cooked_fish()
            if self.inv_has_space():
                self.resume_fishing()
            if not self.has_feathers():
                self.logout_and_stop_script()
            msg_time_left = f"Time left: {(end_time - (time.time() - start_time)):.2f}s"
            self.log_msg(msg_time_left, overwrite=True)
            self.update_progress((time.time() - start_time) / end_time)
        self.update_progress(1)
        self.log_msg("[END]")
        self.stop()

    def find_and_mouse_to_fishing_spot(self):
        if spot := self.find_sprite(png="fishing-spot.png", folder="fish_fryer"):
            self.mouse.move_to(spot.get_center())

    def resume_fishing(self):
        self.log_msg("Searching for fishing spot...")
        self.find_and_mouse_to_fishing_spot()
        self.mouse.click()
        self.log_msg("Found fishing spot. Moving toward it...", overwrite=True)
        timeout = 60  # Define a timeout period in seconds.
        start = time.time()
        while (
            not self.is_fishing()
            and (time.time() - start < timeout)
            and not self.is_idling()
        ):
            time.sleep(0.5)
        self.log_msg("Arrived at fishing spot.", overwrite=True)
        self.take_break(lo=5, hi=6)
        if self.is_fishing() and self.inv_has_space():
            self.log_msg("Fishing resumed.")
            while self.is_fishing():
                time.sleep(0.5)
                if self.inv_is_full():
                    break
        if self.inv_is_full() and self.has_raw_fish():
            self.log_msg("Inventory is full. Heading off to cook.", overwrite=True)
            self.resume_cooking()
        if not self.is_fishing() and self.inv_has_space():
            self.log_msg("Unexpectedly idling. Resuming fishing...")
            self.sleep()
            self.resume_fishing()

    def find_and_mouse_to_fire(self, num_retries: int = 10) -> bool:
        """After traveling within range, mouse to the color-tagged fire.

        Note that this is a simple wrapper for `find_and_mouse_to_marked_object`.

        Args:
            num_retries (int, optional): The number of times to retry searching if the
                first search failed. Defaults to 10.

        Returns:
            bool: True if we found the fire and moused to it, or False otherwise.
        """
        return self.find_and_mouse_to_marked_object(
            color=self.cp.hsv.PURPLE_MARK,
            req_txt_colors=[self.cp.bgr.OFF_WHITE_TEXT, self.cp.bgr.OFF_CYAN_TEXT],
            req_txt=["Cook", "Fire"],
            num_retries=num_retries,
        )

    def resume_cooking(self) -> bool:
        self.find_and_mouse_to_fire()
        self.mouse.click()
        self.log_msg("Traveling to fire...")
        timeout = 60
        start = time.time()
        while (
            not self.cooking_window_is_open()
            and (time.time() - start < timeout)
            and not self.is_idling()
        ):
            self.take_break(lo=4, hi=5)
            self.find_and_mouse_to_fire()
            self.mouse.click()
        if self.cooking_window_is_open():
            self.cook_fish()
        if self.is_idling() and self.has_raw_fish():
            self.resume_cooking()
        if self.inv_is_full() and self.has_cooked_fish() and not self.has_raw_fish():
            return True
        return False

    def cook_fish(self):
        self.log_msg("Arrived at fire and opened cooking window.", overwrite=True)
        # if self.take_breaks:
        #     self.potentially_take_a_break()
        self.sleep()
        pag.keyDown("space")
        self.sleep()
        pag.keyUp("space")
        time.sleep(1)
        if not self.is_cooking():
            self.sleep()
            pag.keyDown("space")
            self.sleep()
            pag.keyUp("space")
            time.sleep(1)
        self.log_msg("Cooking fish...")
        self.sleep(0.7, 0.9)
        while self.has_raw_fish() and self.is_cooking():
            self.sleep()

    def has_raw_fish(self) -> bool:
        return self.api_m.get_inv_item_indices(self.raw_fish) != []

    def has_cooked_fish(self) -> bool:
        return self.api_m.get_inv_item_indices(self.cooked_fish) != []

    def is_cooking(self) -> bool:
        return self.api_s.get_animation_id() in self.cooking_styles

    def is_fishing(self) -> bool:
        return self.is_player_doing_action("Fishing")

    def inv_has_space(self) -> bool:
        return not self.api_m.is_inv_full()

    def inv_is_full(self) -> bool:
        return self.api_m.is_inv_full()

    def cooking_window_is_open(
        self,
        png: Union[Path, str] = "cooking-window-open.png",
        folder: Union[Path, str] = "fish_fryer",
        verbose=False,
    ) -> bool:
        """Return whether the cooking window is open by checking the chat window.

        Args:
            png (Union[Path, str]): The PNG filename of the sprite. The PNG should have
                no iCCP profile.
            folder (Union[Path, str], optional): The subfolder within the
                "./src/images/bot" directory that contains `png`.
            verbose (bool, optional): Whether to print a log message. Defaults to False.

        Returns:
            bool: True if the cooking window is open, False if it isn't.
        """
        folder = Path(folder) if isinstance(folder, str) else folder
        png_path = folder / png if folder else png
        sprite = imsearch.search_img_in_rect(
            imsearch.BOT_IMAGES.joinpath(png_path), self.win.chat
        )
        Not = "" if sprite else "Not"
        msg = f"{Not} found: {png_path.name}".lstrip().capitalize()
        if verbose:
            self.log_msg(msg)
        return sprite is not None

    def is_idling(self) -> bool:
        return self.api_m.is_player_idle()

    def drop_all_cooked_fish(self) -> bool:
        """Drop all cooked fish from our character's inventory.

        This function relies on the Left Click Drop RuneLite plug-in being configured
        correctly for the corresponding variety of cooked fish we're harvesting.

        Returns:
            bool: True if the cooked fish were successfully dropped, False otherwise.
        """
        traversal = self.get_inv_drop_traversal_path()
        fish_slots = self.api_m.get_inv_item_indices(self.cooked_fish)
        fish_slots = [slot for slot in traversal if slot in fish_slots]
        self.log_msg(f"Dropping {len(fish_slots)} fish...")
        if fish_slots:
            self.drop_items(slots=fish_slots, verbose=False)
            self.log_msg(f"Dropped {len(fish_slots)} fish.", overwrite=True)
            self.fish_dropped += len(fish_slots)
            self.log_msg(f"Total fish dropped: {self.fish_dropped}")
            return True
        self.log_msg("Failed to drop fish.", overwrite=True)
        return False

    def has_feathers(self) -> bool:
        return self.api_m.get_inv_item_indices(i_ids.FEATHER) != []
