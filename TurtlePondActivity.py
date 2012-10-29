#Copyright (c) 2011 Walter Bender
# Port To GTK3:
# Ignacio Rodriguez <ignaciorodriguez@sugarlabs.org>
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this library; if not, write to the Free Software
# Foundation, 51 Franklin Street, Suite 500 Boston, MA 02110-1335 USA

from gi.repository import Gtk, GObject, Gdk

import sugar3
from sugar3.activity import activity
from sugar3 import profile
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.bundle.activitybundle import ActivityBundle
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.activity.widgets import StopButton
from sugar3.graphics.toolbarbox import ToolbarButton

from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.menuitem import MenuItem
from sugar3.graphics.icon import Icon
from sugar3.datastore import datastore
from sugar3.graphics.objectchooser import ObjectChooser

from toolbar_utils import button_factory, image_factory, label_factory, \
    separator_factory, radio_factory

from gettext import gettext as _
import locale
import os.path

from game import Game
from genxo import generate_xo
from utils import svg_str_to_pixbuf

import logging
_logger = logging.getLogger('turtle-in-a-pond-activity')

BEGINNER = 0
INTERMEDIATE = 1
EXPERT = 2
CUSTOM = 3
LEVEL_LABELS = [_('Beginner'), _('Intermediate'), _('Expert'),
                _('My strategy')]


class TurtlePondActivity(activity.Activity):
    """ Turtle in a Pond puzzle game """

    def __init__(self, handle):
        """ Initialize the toolbars and the game board """
        super(TurtlePondActivity, self).__init__(handle)
        self.nick = profile.get_nick_name()
        if profile.get_color() is not None:
            self.colors = profile.get_color().to_string().split(',')
        else:
            self.colors = ['#A0FFA0', '#FF8080']

        self._setup_toolbars()

        # Create a canvas
        canvas = Gtk.DrawingArea()
        canvas.set_size_request(Gdk.Screen.width(), \
                                Gdk.Screen.height())
        self.set_canvas(canvas)
        canvas.show()
        self.show_all()

        self._game = Game(canvas, parent=self, colors=self.colors)

        # TODO: Restore game state from Journal or start new game
        self._game.new_game()

    def _setup_toolbars(self):
        """ Setup the toolbars. """

        self.max_participants = 1

        toolbox = ToolbarBox()

        # Activity toolbar
        activity_button = ActivityToolbarButton(self)

        toolbox.toolbar.insert(activity_button, 0)
        activity_button.show()

        self.set_toolbar_box(toolbox)
        toolbox.show()
        self.toolbar = toolbox.toolbar

        self._new_game_button = button_factory(
            'new-game', self.toolbar, self._new_game_cb,
            tooltip=_('Start a new game.'))

        separator_factory(self.toolbar, False, True)

        self.beginner_button = radio_factory(
            'beginner',
            self.toolbar,
            self._level_cb,
            cb_arg=BEGINNER,
            tooltip=LEVEL_LABELS[BEGINNER],
            group=None)
        self.intermediate_button = radio_factory(
            'intermediate',
            self.toolbar,
            self._level_cb,
            cb_arg=INTERMEDIATE,
            tooltip=LEVEL_LABELS[INTERMEDIATE],
            group=self.beginner_button)
        self.expert_button = radio_factory(
            'expert',
            self.toolbar,
            self._level_cb,
            cb_arg=EXPERT,
            tooltip=LEVEL_LABELS[EXPERT],
            group=self.beginner_button)
        self.custom_button = radio_factory(
            'view-source',
            self.toolbar,
            self._level_cb,
            cb_arg=CUSTOM,
            tooltip=LEVEL_LABELS[CUSTOM],
            group=self.beginner_button)

        self.status = label_factory(self.toolbar, '')

        separator_factory(toolbox.toolbar, True, False)

        self.load_python = button_factory(
            'pippy-openoff', self.toolbar,
            self._do_load_python_cb,
            tooltip=_('Load strategy from Journal'))

        stop_button = StopButton(self)
        stop_button.props.accelerator = '<Ctrl>q'
        toolbox.toolbar.insert(stop_button, -1)
        stop_button.show()

    def _level_cb(self, button, level):
        if level == CUSTOM and self._game.strategies[CUSTOM] is None:
            level = EXPERT
            self.expert_button.set_active(True)
        self._game.level = level
        self._game.new_game()

    def _new_game_cb(self, button=None):
        ''' Start a new game. '''
        self._game.new_game()

    def write_file(self, file_path):
        """ Write the grid status to the Journal """
        return

    def _restore(self):
        """ Restore the game state from metadata """
        return

    def _do_load_python_cb(self, button):
        ''' Load Python code from the Journal. '''
        self._chooser('org.laptop.Pippy',
                self._load_python_code_from_journal)
        if self._game.strategies[CUSTOM] is not None:
            self.custom_button.set_active(True)
        self._game.level = CUSTOM
        self._game.new_game()

    def _load_python_code_from_journal(self, dsobject):
        """ Read the Python code from the Journal object """
        python_code = None
        try:
            _logger.debug("opening %s " % dsobject.file_path)
            file_handle = open(dsobject.file_path, "r")
            python_code = file_handle.read()
            file_handle.close()
        except IOError:
            _logger.debug("couldn't open %s" % dsobject.file_path)
        self._game.strategies[CUSTOM] = python_code

    def _chooser(self, filter, action):
        ''' Choose an object from the datastore and take some action '''
        chooser = None
        try:
            chooser = ObjectChooser(parent=self, what_filter=filter)
        except TypeError:
            chooser = ObjectChooser(
                None, self,
                Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT)
        if chooser is not None:
            try:
                result = chooser.run()
                if result == Gtk.ResponseType.ACCEPT:
                    dsobject = chooser.get_selected_object()
                    action(dsobject)
                    dsobject.destroy()
            finally:
                chooser.destroy()
                del chooser
