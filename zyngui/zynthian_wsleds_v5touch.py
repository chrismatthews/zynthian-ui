#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian WSLeds Class for LED emulation on touchscreen keypad V5
#
# Copyright (C) 2024 Pavel Vondřička <pavel.vondricka@ff.cuni.cz>
#
# ******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
# ******************************************************************************

import os

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_wsleds_v5 import zynthian_wsleds_v5

# ---------------------------------------------------------------------------
# Fake NeoPixel emulation for onscreen touch keypad "buttons"
# ---------------------------------------------------------------------------

class touchkeypad_button_colors:
    """
    Fake NeoPixel emulation to change colors of onscreen touch keypad
    """

    def __init__(self, wsleds):
        self.wsleds = wsleds
        self.zyngui = wsleds.zyngui
        # A wanna-be abstraction: derive a named "mode" from the requested colors
        self.mode_map = {}
        self.mode_map[wsleds.wscolor_default] = 'default'
        self.mode_map[wsleds.wscolor_alt] = 'alt'
        self.mode_map[wsleds.wscolor_active] = 'active'
        self.mode_map[wsleds.wscolor_active2] = 'active2'

    def __setitem__(self, index, color):
        mode = self.mode_map.get(color, None)
        # request color change on the onscreen touchkeypad
        if isinstance(color, int):
            color = f"#{color:06x}" # color conversion to hex cod
        # tkinter is not able to set RGBA/alpha color, 
        # so we need to blend the foreground color with the background color
        if zynthian_gui_config.zyngui:
            fgcolor = self.hex_to_rgb(color)
            bgcolor = self.hex_to_rgb(self.wsleds.wscolor_off)
            blended = self.ablend(1-self.wsleds.brightness, fgcolor, bgcolor)
            color = self.rgb_to_hex(blended)
        zynthian_gui_config.touch_keypad.set_button_color(index, color, mode)

    def show(self):
        # nothing to do here
        pass

    def ablend(self, a, fg, bg):
        """
        Blend foreground and background color to imitate alpha transparency
        """
        return (int((1-a)*fg[0]+a*bg[0]),
                int((1-a)*fg[1]+a*bg[1]),
                int((1-a)*fg[2]+a*bg[2]))

    def hex_to_rgb(self, hexstr):
        rgb = []
        hex = hexstr[1:]
        for i in (0, 2, 4):
            decimal = int(hex[i:i+2], 16)
            rgb.append(decimal)
        return tuple(rgb)

    def rgb_to_hex(self, rgb):
        r, g, b = rgb
        return '#{:02x}{:02x}{:02x}'.format(r, g, b)

# ---------------------------------------------------------------------------
# Zynthian WSLeds class for LED emulation on touchscreen keypad V5
# ---------------------------------------------------------------------------

class zynthian_wsleds_v5touch(zynthian_wsleds_v5):
    """
    Emulation of wsleds for onscreen touch keypad V5
    """

    def start(self):
        self.wsleds = touchkeypad_button_colors(self)
        self.light_on_all()

    def setup_colors(self):
        # Predefined colors
        self.wscolor_off = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_OFF', zynthian_gui_config.color_bg)
        self.wscolor_white = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_WHITE', "#FCFCFC")
        self.wscolor_red = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_RED', "#FE2C2F")
        self.wscolor_green = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_GREEN', "#00FA00")
        self.wscolor_yellow = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_YELLOW', "#F0EA00")
        self.wscolor_orange = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_ORANGE', "#FF6A00")
        self.wscolor_blue = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_BLUE', "#1070FE")
        self.wscolor_blue_light = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_LIGHTBLUE', "#05FDFF")
        self.wscolor_purple = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_PURPLE', "#D000E0")
        self.wscolor_default = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_DEFAULT', self.wscolor_blue)
        self.wscolor_alt = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_ALT', self.wscolor_purple)
        self.wscolor_active = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_ACTIVE', self.wscolor_green)
        self.wscolor_active2 = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_ACTIVE2', self.wscolor_orange)
        self.wscolor_admin = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_ADMIN', self.wscolor_red)
        self.wscolor_low = os.environ.get('ZYNTHIAN_TOUCH_KEYPAD_COLOR_LOW', "#D9EB37")
        # Color Codes
        self.wscolors_dict = {
            str(self.wscolor_off): "0",
            str(self.wscolor_blue): "B",
            str(self.wscolor_green): "G",
            str(self.wscolor_red): "R",
            str(self.wscolor_orange): "O",
            str(self.wscolor_yellow): "Y",
            str(self.wscolor_purple): "P"
}
