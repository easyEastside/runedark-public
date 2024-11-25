import time

import pytweening

import utilities.color as clr
import utilities.ocr as ocr
from model.osrs.osrs_bot import OSRSBot
from utilities import img_search as imsearch
from utilities.geometry import Rectangle

PATH_NMZ = imsearch.BOT_IMAGES / "nmz"


class NMZ_xpFarming(OSRSBot):
    def __init__(self):
        bot_title = "NMZ XP Farming"
        description = (
            "Holds right arrow key on the keyboard to prevent logout and clicks on"
            " absorbtion potions when below threshold."
        )
        super().__init__(bot_title=bot_title, description=description)
        # Set option variables below (initial value is only used during headless testing)
        self.absorb4_img = PATH_NMZ / "absorption4.png"
        self.absorb3_img = PATH_NMZ / "absorption3.png"
        self.absorb2_img = PATH_NMZ / "absorption2.png"
        self.absorb1_img = PATH_NMZ / "absorption1.png"
        self.running_time = 1

    def create_options(self):
        """
        Use the OptionsBuilder to define the options for the bot. For each function call below,
        we define the type of option we want to create, its key, a label for the option that the user will
        see, and the possible values the user can select. The key is used in the save_options function to
        unpack the dictionary of options after the user has selected them.
        """
        self.options_builder.add_slider_option(
            "running_time", "How long to run (minutes)?", 1, 500
        )

    def save_options(self, options: dict):
        """
        For each option in the dictionary, if it is an expected option, save the value as a property of the bot.
        If any unexpected options are found, log a warning. If an option is missing, set the options_set flag to
        False.
        """
        for option in options:
            if option == "running_time":
                self.running_time = options[option]
            else:
                self.log_msg(f"Unknown option: {option}")
                print(
                    "Developer: ensure that the option keys are correct, and that"
                    " options are being unpacked correctly."
                )
                self.options_set = False
                return
        self.log_msg(f"Running time: {self.running_time} minutes.")
        self.log_msg("Options set successfully.")
        self.options_set = True

    def main_loop(self):
        """
        When implementing this function, you have the following responsibilities:
        1. If you need to halt the bot from within this function, call `self.stop()`. You'll want to do this
           when the bot has made a mistake, gets stuck, or a condition is met that requires the bot to stop.
        2. Frequently call self.update_progress() and self.log_msg() to send information to the UI.
        3. At the end of the main loop, make sure to call `self.stop()`.

        Additional notes:
        - Make use of Bot/RuneLiteBot member functions. There are many functions to simplify various actions.
          Visit the Wiki for more.
        - Using the available APIs is highly recommended. Some of all of the API tools may be unavailable for
          select private servers. For usage, uncomment the `api_m` and/or `api_s` lines below, and use the `.`
          operator to access their functions.
        """

        start_time = time.time()
        end_time = self.running_time * 60
        while time.time() - start_time < end_time:
            zorb_x, zorb_y = self.win.game_view.top_left
            zorbrect = Rectangle(left=zorb_x, top=zorb_y, width=100, height=200)
            fonts = [ocr.PLAIN_11, ocr.PLAIN_12]
            for font in fonts:
                if match := ocr.extract_text(zorbrect, font, [clr.RED]) != "":
                    for _ in range(4):  # This means we're taking 16 doses.
                        self.click_full_pot_4_times()
            if not match:
                self.log_msg("Points are not below threshold.")
            self.take_break(lo=30, hi=40, fancy=True)
            self.update_progress((time.time() - start_time) / end_time)
        self.update_progress(1)
        self.log_msg("Finished.")
        self.stop()

    def click_full_pot_4_times(self):
        """Find and mouse to a full absorption potion, then click it four times."""
        if absorb := imsearch.search_img_in_rect(
            self.absorb4_img, self.win.control_panel
        ):
            self.mouse.move_to(
                absorb.random_point(), mouseSpeed="fast", tween=pytweening.easeInOutQuad
            )
            self.log_msg("Absorb pot found.")
            for _ in range(4):
                self.mouse.click()
                self.sleep()
        else:
            self.log_msg("Absorb pot not found")
            self.logout_and_stop_script()
