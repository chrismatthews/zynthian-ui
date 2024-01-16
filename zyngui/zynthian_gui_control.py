#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Instrument-Control Class
# 
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
#
#******************************************************************************
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
#******************************************************************************

import logging
import importlib
from pathlib import Path
from datetime import datetime

# Zynthian specific modules
from zyngine import zynthian_controller
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_controller import zynthian_gui_controller
from zyngui.zynthian_gui_selector import zynthian_gui_selector

#------------------------------------------------------------------------------
# Zynthian Instrument Controller GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_control(zynthian_gui_selector):

	def __init__(self, selcap='Controllers'):
		self.mode = None

		self.screen_info = None
		self.screen_title = None
		self.screen_layer = None

		self.widgets = {}
		self.current_widget = None
		self.cuia_toggle_record = None
		self.cuia_stop = None
		self.cuia_toggle_play = None

		self.ctrl_screens = {}
		self.zcontrollers = []
		self.screen_name = None
		self.zgui_controllers = []
		self.midi_learning = False

		self.buttonbar_config = [
			(1, 'PRESETS\n[mixer]'),
			(0, 'NEXT CHAIN\n[menu]'),
			(2, 'LEARN\n[snapshot]'),
			(3, 'PAGE\n[options]')
		]

		if zynthian_gui_config.layout['columns'] == 3:
			super().__init__(selcap, False, False)
		else:
			super().__init__(selcap, True, False)

		# xyselect mode vars
		self.xyselect_mode = False
		self.x_zctrl = None
		self.y_zctrl = None

		# Configure layout
		for ctrl_pos in zynthian_gui_config.layout['ctrl_pos']:
			self.main_frame.columnconfigure(ctrl_pos[1], weight=1, uniform='ctrl_col')
			self.main_frame.rowconfigure(ctrl_pos[0], weight=1, uniform='ctrl_row')
		self.main_frame.columnconfigure(zynthian_gui_config.layout['list_pos'][1], weight=2)


	def update_layout(self):
		super().update_layout()
		for pos in zynthian_gui_config.layout['ctrl_pos']:
			self.main_frame.columnconfigure(pos[1], minsize=int((self.width * 0.25 - 1) * self.sidebar_shown), weight=self.sidebar_shown)
		

	def build_view(self):
		if self.zyngui.curlayer:
			super().build_view()
			self.click_listbox()
		else:
			self.zyngui.close_screen()


	def hide(self):
		self.zyngui.exit_midi_learn()
		super().hide()
		#if self.shown:
		#	for zc in self.zgui_controllers: zc.hide()
		#	if self.zselector: self.zselector.hide()


	def show_sidebar(self, show):
		self.sidebar_shown = show
		for zctrl in self.zgui_controllers:
			if self.sidebar_shown:
				zctrl.grid()
			else:
				zctrl.grid_remove()
		self.update_layout()


	def fill_list(self):
		self.list_data = []

		if not self.zyngui.curlayer:
			logging.error("Can't fill control screen list for None layer!")
			return

		if self.zyngui.curlayer.engine.nickname == "MX":
			self.layers = [self.zyngui.curlayer]
		else:
			# Get MIDI effects not including root
			self.layers = self.zyngui.screens['layer'].get_midichain_layers()
			# Get root
			self.layers.append(self.zyngui.curlayer)
			# Get audio effects not including root
			self.layers += self.zyngui.screens['layer'].get_fxchain_layers()

		# Remove duplicates, e.g. root layer in MIDI only chains
		self.layers = list(dict.fromkeys(self.layers))

		i = 0
		for layer in self.layers:
			j = 0
			screen_list = layer.get_ctrl_screens()
			if len(screen_list) > 0:
				if len(self.layers) > 1:
					self.list_data.append((None, None, "> {}".format(layer.engine.name.split("/")[-1])))
				for cscr in screen_list:
					self.list_data.append((cscr, i, cscr, layer, j))
					i += 1
					j += 1

		self.index = self.zyngui.curlayer.get_current_screen_index()
		self.get_screen_info()

		super().fill_list()


	def get_screen_info(self):
		if 0 <= self.index < len(self.list_data):
			self.screen_info = self.list_data[self.index]
			if len(self.screen_info) < 5:
				if self.index + 1 < len(self.list_data):
					self.index += 1
					self.screen_info = self.list_data[self.index]
				else:
					self.screen_info = None
			if self.screen_info and len(self.screen_info) == 5:
				self.screen_title = self.screen_info[2]
				self.screen_layer = self.screen_info[3]
				return True
			else:
				logging.error("Can't get screen info!!")

		self.screen_title = ""
		self.screen_layer = self.zyngui.curlayer
		return False


	def fill_listbox(self):
		super().fill_listbox()
		for i, val in enumerate(self.list_data):
			if val[0] == None:
				#self.listbox.itemconfig(i, {'bg':zynthian_gui_config.color_off,'fg':zynthian_gui_config.color_tx_off})
				self.listbox.itemconfig(i, {'bg':zynthian_gui_config.color_panel_hl, 'fg':zynthian_gui_config.color_tx_off})


	def set_selector(self, zs_hiden=True):
		if self.mode == 'select':
			super().set_selector(zs_hiden)


	def show_widget(self, layer):
		module_path = layer.engine.custom_gui_fpath
		if module_path:
			module_name = Path(module_path).stem
			if module_name.startswith("zynthian_widget_"):
				widget_name = module_name[len("zynthian_widget_"):]
				if widget_name not in self.widgets:
					try:
						spec = importlib.util.spec_from_file_location(module_name, module_path)
						module = importlib.util.module_from_spec(spec)
						spec.loader.exec_module(module)
						class_ = getattr(module, module_name)
						self.widgets[widget_name] = class_(self.main_frame)
					except Exception as e:
						logging.error("Can't load custom widget {} => {}".format(widget_name, e))

				if widget_name in self.widgets:
					self.widgets[widget_name].set_layer(layer)
				else:
					widget_name = None

				if self.wide:
					padx = (0,2)
				else:
					padx = (2,2)
				for k, widget in self.widgets.items():
					if k == widget_name:
						self.listbox.grid_remove()
						widget.grid(row=zynthian_gui_config.layout['list_pos'][0], column=zynthian_gui_config.layout['list_pos'][1], rowspan=4, padx=padx, sticky="news")
						widget.show()
						self.set_current_widget(widget)
					else:
						widget.grid_remove()
						widget.hide()
				return
		self.hide_widgets()


	def hide_widgets(self):
		for k, widget in self.widgets.items():
			widget.grid_remove()
			widget.hide()
		self.set_current_widget(None)
		self.listbox.grid()


	def set_current_widget(self, widget):
		self.current_widget = widget
		if self.current_widget is not None:
			func = getattr(self.current_widget, "cuia_toggle_record", None)
			if callable(func):
				self.cuia_toggle_record = func
			func = getattr(self.current_widget, "cuia_stop", None)
			if callable(func):
				self.cuia_stop = func
			func = getattr(self.current_widget, "cuia_toggle_play", None)
			if callable(func):
				self.cuia_toggle_play = func
			func = getattr(self.current_widget, "update_wsleds", None)
			if callable(func):
				self.update_wsleds = func
		else:
			self.cuia_toggle_record = None
			self.cuia_stop = None
			self.cuia_toggle_play = None
			self.update_wsleds = None


	def set_controller_screen(self):
		# Get screen info
		if self.get_screen_info():
			# Show the widget for the current sublayer
			if self.mode == 'control':
				self.show_widget(self.screen_layer)

			# Get controllers for the current screen
			self.zyngui.curlayer.set_current_screen_index(self.index)
			self.zcontrollers = self.screen_layer.get_ctrl_screen(self.screen_title)

		else:
			self.zcontrollers = []
			self.screen_title = ""
			self.hide_widgets()

		# Setup GUI Controllers
		logging.debug("SET CONTROLLER SCREEN {}".format(self.screen_title))
		# Configure zgui_controllers
		for i in range(4):
			if i < len(self.zcontrollers):
				try:
					ctrl = self.zcontrollers[i]
					#logging.debug("CONTROLLER ARRAY {} => {} ({})".format(i, ctrl.symbol, ctrl.short_name))
					self.set_zcontroller(i, ctrl)
				except Exception as e:
					logging.exception("Controller %s (%d) => %s" % (ctrl.short_name, i, e))
					self.zgui_controllers[i].hide()
			else:
				self.set_zcontroller(i, None)
			pos = zynthian_gui_config.layout['ctrl_pos'][i]
			self.zgui_controllers[i].grid(row=pos[0], column=pos[1], pady=(0,1), sticky='news')

		# Set/Restore XY controllers highlight
		if self.mode == 'control':
			self.set_xyselect_controllers()

		self.update_layout()


	def set_zcontroller(self, i, ctrl):
		if i < len(self.zgui_controllers):
			self.zgui_controllers[i].config(ctrl)
			self.zgui_controllers[i].show()
		else:
			self.zgui_controllers.append(zynthian_gui_controller(i, self.main_frame, ctrl))


	def get_zcontroller(self, i):
		if i < len(self.zgui_controllers):
			return self.zgui_controllers[i].zctrl
		else:
			return None

	def set_xyselect_controllers(self):
		for i in range(0, len(self.zgui_controllers)):
			try:
				if self.xyselect_mode:
					zctrl = self.zgui_controllers[i].zctrl
					if zctrl == self.x_zctrl or zctrl == self.y_zctrl:
						self.zgui_controllers[i].set_hl()
						continue
				self.zgui_controllers[i].unset_hl()
			except:
				pass


	def set_selector_screen(self): 
		for i in range(0, len(self.zgui_controllers)):
			self.zgui_controllers[i].set_hl(zynthian_gui_config.color_ctrl_bg_off)
		self.set_selector()


	def set_mode_select(self):
		self.mode = 'select'
		self.hide_widgets()
		self.set_selector_screen()
		self.listbox.config(selectbackground=zynthian_gui_config.color_ctrl_bg_off,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			fg=zynthian_gui_config.color_ctrl_tx_off)
		self.select(self.index)
		self.set_select_path()


	def set_mode_control(self):
		self.mode = 'control'
		if self.zselector: self.zselector.hide()
		self.set_controller_screen()
		self.listbox.config(selectbackground=zynthian_gui_config.color_ctrl_bg_on,
			selectforeground=zynthian_gui_config.color_ctrl_tx,
			fg=zynthian_gui_config.color_ctrl_tx)
		self.set_select_path()


	def set_xyselect_mode(self, xctrl_i, yctrl_i):
		self.xyselect_mode = True
		self.xyselect_zread_axis = 'X'
		self.xyselect_zread_counter = 0
		self.xyselect_zread_last_zctrl = None
		self.x_zctrl = self.zgui_controllers[xctrl_i].zctrl
		self.y_zctrl = self.zgui_controllers[yctrl_i].zctrl
		#Set XY controllers highlight
		self.set_xyselect_controllers()
		
		
	def unset_xyselect_mode(self):
		self.xyselect_mode = False
		#Set XY controllers highlight
		self.set_xyselect_controllers()


	def set_xyselect_x(self, xctrl_i):
		zctrl = self.zgui_controllers[xctrl_i].zctrl
		if self.x_zctrl != zctrl and self.y_zctrl != zctrl:
			self.x_zctrl = zctrl
			#Set XY controllers highlight
			self.set_xyselect_controllers()
			return True


	def set_xyselect_y(self, yctrl_i):
		zctrl = self.zgui_controllers[yctrl_i].zctrl
		if self.y_zctrl != zctrl and self.x_zctrl != zctrl:
			self.y_zctrl = zctrl
			#Set XY controllers highlight
			self.set_xyselect_controllers()
			return True


	def previous_page(self, wrap=False):
		i = self.index - 1
		if i < 0:
			i = 0
		self.select(i)
		self.click_listbox()


	def next_page(self, wrap=False):
		i = self.index + 1
		if i >= len(self.list_data):
			if wrap:
				i = 0
			else:
				i = len(self.list_data) - 1
		self.select(i)
		self.click_listbox()


	def select_action(self, i, t='S'):
		self.set_mode_control()


	def back_action(self):
		if self.mode == 'select':
			self.set_mode_control()
			return True
		# If control xyselect mode active, disable xyselect mode
		elif self.xyselect_mode:
			logging.debug("DISABLE XYSELECT MODE")
			if self.zyngui.screens['control_xy'].shown:
				self.zyngui.screens['control_xy'].hide()
			else:
				self.unset_xyselect_mode()
			self.build_view()
			self.show()
			return True
		# If in MIDI-learn mode, back to instrument control
		elif self.zyngui.midi_learn_mode or self.zyngui.midi_learn_zctrl:
			self.zyngui.exit_midi_learn()
			return True
		else:
			return False


	def arrow_up(self):
		self.previous_page()
		return True


	def arrow_down(self):
		self.next_page()
		return True


	def arrow_right(self):
		if self.zyngui.screens['layer'].get_num_root_layers() > 1:
			self.zyngui.screens['layer'].next(True)


	def arrow_left(self):
		if self.zyngui.screens['layer'].get_num_root_layers() > 1:
			self.zyngui.screens['layer'].prev(True)


	# Function to handle *all* switch presses.
	#	swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, swi, t='S'):
		if swi == 0:
			if t == 'S':
				self.arrow_right()
				return True

		elif swi == 1:
			if t == 'S':
				if self.back_action():
					return True
				elif not self.zyngui.is_shown_alsa_mixer():
					self.zyngui.cuia_bank_preset()
					return True
			elif t == 'B':
				self.back_action()
				return False

		elif swi == 2:
			if t == 'S':
				if self.mode == 'control':
					self.zyngui.toggle_midi_learn()
				return True
			elif t == 'B':
				if self.midi_learning:
					self.midi_unlearn_action()
					return True


	def switch_select(self, t):
		if t == 'S':
			if self.mode in ('control', 'xyselect'):
				if len(self.list_data) > 3:
					self.set_mode_select()
				else:
					self.next_page(True)
			elif self.mode == 'select':
				self.click_listbox()
		elif t == 'B':
			self.zyngui.cuia_chain_options()

		return True


	def select(self, index=None):
		super().select(index)
		if self.mode == 'select':
			self.set_controller_screen()
			self.set_selector_screen()


	def zynpot_cb(self, i, dval):
		if self.mode == 'control' and self.zcontrollers:
			if self.zgui_controllers[i].zynpot_cb(dval):
				self.midi_learn_zctrl(i)
				if self.xyselect_mode:
					self.zynpot_read_xyselect(i)
		elif self.mode == 'select':
			super().zynpot_cb(i, dval)


	def zynpot_read_xyselect(self, i):
		#Detect a serie of changes in the same controller
		if self.zgui_controllers[i].zctrl == self.xyselect_zread_last_zctrl:
			self.xyselect_zread_counter += 1
		else:
			self.xyselect_zread_last_zctrl = self.zgui_controllers[i].zctrl
			self.xyselect_zread_counter = 0

		#If the change counter is major of ...
		if self.xyselect_zread_counter > 5:
			if self.xyselect_zread_axis == 'X' and self.set_xyselect_x(i):
				self.xyselect_zread_axis = 'Y'
				self.xyselect_zread_counter = 0
			elif self.xyselect_zread_axis == 'Y' and self.set_xyselect_y(i):
				self.xyselect_zread_axis = 'X'
				self.xyselect_zread_counter = 0


	def get_zgui_controller(self, zctrl):
		for zgui_controller in self.zgui_controllers:
			if zgui_controller.zctrl == zctrl:
				return zgui_controller


	def get_zgui_controller_by_index(self, i):
		return self.zgui_controllers[i]


	def refresh_midi_bind(self):
		for zgui_controller in self.zgui_controllers:
			zgui_controller.set_midi_bind()


	def plot_zctrls(self, force=False):
		if self.mode == 'select':
			super().plot_zctrls()
		elif self.zgui_controllers:
			self.swipe_update()
			for zgui_ctrl in self.zgui_controllers:
				if zgui_ctrl.zctrl and zgui_ctrl.zctrl.is_dirty or force:
					zgui_ctrl.calculate_plot_values()
				zgui_ctrl.plot_value()
		for k, widget in self.widgets.items():
			widget.update()


	#--------------------------------------------------------------------------
	# Options Menu
	#--------------------------------------------------------------------------

	def show_menu(self):
		self.zyngui.cuia_chain_options()


	def toggle_menu(self):
		if self.shown:
			self.show_menu()
		elif self.zyngui.current_screen.endswith("_options"):
			self.close_screen()


	#--------------------------------------------------------------------------
	# MIDI learn management
	#--------------------------------------------------------------------------

	def enter_midi_learn(self):
		self.midi_learning = True
		self.set_buttonbar_label(0, "CANCEL")
		self.refresh_midi_bind()
		self.set_select_path()


	def exit_midi_learn(self):
		self.midi_learning = False
		self.refresh_midi_bind()
		self.set_select_path()
		self.set_buttonbar_label(0, "PRESETS\n[mixer]")


	def toggle_midi_learn(self):
		if self.zyngui.midi_learn_mode:
			self.zyngui.exit_midi_learn()
			if zynthian_gui_config.midi_prog_change_zs3 and not self.zyngui.is_shown_alsa_mixer():
				self.zyngui.screens['zs3'].index = 0
				self.zyngui.show_screen("zs3")
		else:
			self.zyngui.enter_midi_learn()


	def midi_learn_zctrl(self, i):
		if self.shown and self.zyngui.midi_learn_mode:
			logging.debug("MIDI-learn ZController {}".format(i))
			self.zyngui.midi_learn_mode = False
			self.midi_learn(i)


	def midi_learn(self, i):
		if self.mode == 'control' and self.zgui_controllers[i].zctrl:
			self.zgui_controllers[i].zctrl.init_midi_learn()
			self.refresh_midi_bind()
			self.set_select_path()


	def midi_unlearn(self, zctrl=None):
		if isinstance(zctrl, zynthian_controller):
			zctrl.midi_unlearn()
		elif isinstance(zctrl, int):
			try:
				self.zgui_controllers[zctrl].zctrl.midi_unlearn()
			except Exception as e:
				logging.error("Can't unlearn control {} => {}".format(zctrl, e))
		elif self.zyngui.curlayer:
			self.zyngui.screens['layer'].midi_unlearn()
		self.zyngui.exit_midi_learn()


	def midi_unlearn_action(self):
		if self.zyngui.midi_learn_zctrl and self.zyngui.midi_learn_zctrl.midi_learn_cc:
			self.zyngui.show_confirm("Do you want to clean MIDI-learn for '{}' control?".format(self.zyngui.midi_learn_zctrl.name), self.midi_unlearn, self.zyngui.midi_learn_zctrl)
		elif self.zyngui.curlayer and self.zyngui.curlayer.engine:
			if self.zyngui.curlayer.midi_chan == 256:
				chain_label = "MAIN"
			else:
				chain_label = "CH#{}".format(self.zyngui.curlayer.midi_chan + 1)
			self.zyngui.show_confirm("Do you want to clean MIDI-learn for ALL controls in {} at {}?".format(self.zyngui.curlayer.engine.name, chain_label), self.midi_unlearn)
		self.exit_midi_learn()

	def midi_learn_options(self, i, unlearn_only=False):
		try:
			options = {}
			zctrl = self.zgui_controllers[i].zctrl
			if not unlearn_only:
				options["Learn '{}'...".format(zctrl.name)] = i
				title = "Control MIDI-learn"
			else:
				title = "Control MIDI-unlearn"
			if zctrl.midi_learn_cc:
				options["Unlearn '{}'".format(zctrl.name)] = i
			options["Unlearn All"] = ""
			self.zyngui.screens['option'].config(title, options, self.midi_learn_options_cb)
			self.zyngui.show_screen('option')
		except Exception as e:
			logging.error("Can't show Control MIDI-learn options => {}".format(e))


	def midi_learn_options_cb(self, option, param):
		parts = option.split(" ")
		if parts[0] == "Learn":
			self.midi_learn(param)
		elif parts[0] == "Unlearn":
			if isinstance(param, int):
				self.midi_unlearn(param)
			else:
				self.midi_unlearn_action()


	#--------------------------------------------------------------------------
	# GUI Callback function
	#--------------------------------------------------------------------------

	def cb_listbox_push(self, event):
		if self.xyselect_mode:
			logging.debug("XY-Controller Mode ...")
			self.zyngui.show_control_xy(self.x_zctrl, self.y_zctrl)
		else:
			return super().cb_listbox_push(event)


	def cb_listbox_release(self, event):
		if self.zyngui.cb_touch_release(event):
			return "break"

		if self.xyselect_mode:
			return
		else:
			now = datetime.now()
			dts = (now - self.listbox_push_ts).total_seconds()
			rdts = (now - self.last_release).total_seconds()
			self.last_release = now
			if self.swiping:
				self.swipe_nudge(dts)
			else:
				if rdts < 0.03:
					return  # Debounce
				cursel = self.listbox.nearest(event.y)
				if self.index != cursel:
					self.select(cursel)
				self.select_listbox(self.get_cursel(), False)
				self.click_listbox()
				return "break"


	def cb_listbox_motion(self, event):
		if self.xyselect_mode:
			return
		return super().cb_listbox_motion(event)


	def cb_listbox_wheel(self, event):
		# Override with default listbox behaviour to allow scrolling of listbox without selection (expected UX)
		return


	def set_select_path(self):
		if self.zyngui.curlayer:
			path_layer = None
			if self.zyngui.curlayer.engine.nickname == "AI":
				try:
					path_layer = self.zyngui.screens['layer'].get_fxchain_downstream(self.zyngui.curlayer)[0]
				except:
					pass
			if not path_layer:
				path_layer = self.zyngui.curlayer
			if self.mode == 'control' and self.zyngui.midi_learn_mode:
				self.select_path.set(path_layer.get_basepath() + "/CTRL MIDI-Learn")
			else:
				self.select_path.set(path_layer.get_presetpath())


#------------------------------------------------------------------------------
