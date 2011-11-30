#Copyright (c) 2011 Walter Bender

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this library; if not, write to the Free Software
# Foundation, 51 Franklin Street, Suite 500 Boston, MA 02110-1335 USA


import gtk
import gobject

import sugar
from sugar.activity import activity
from sugar import profile
try:
    from sugar.graphics.toolbarbox import ToolbarBox
    _have_toolbox = True
except ImportError:
    _have_toolbox = False

if _have_toolbox:
    from sugar.bundle.activitybundle import ActivityBundle
    from sugar.activity.widgets import ActivityToolbarButton
    from sugar.activity.widgets import StopButton
    from sugar.graphics.toolbarbox import ToolbarButton

from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.menuitem import MenuItem
from sugar.graphics.icon import Icon
from sugar.datastore import datastore
from sugar.graphics.objectchooser import ObjectChooser

from toolbar_utils import button_factory, image_factory, label_factory, \
    separator_factory

from gettext import gettext as _
import locale
import os.path

from game import Game
from genxo import generate_xo
from utils import svg_str_to_pixbuf

import logging
_logger = logging.getLogger('turtle-in-a-pond-activity')


SERVICE = 'org.sugarlabs.TurtlePondActivity'
IFACE = SERVICE
PATH = '/org/augarlabs/TurtlePondActivity'


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

        self._setup_toolbars(_have_toolbox)

        # Create a canvas
        canvas = gtk.DrawingArea()
        canvas.set_size_request(gtk.gdk.screen_width(), \
                                gtk.gdk.screen_height())
        self.set_canvas(canvas)
        canvas.show()
        self.show_all()

        self._game = Game(canvas, parent=self, colors=self.colors)

        # TODO: Restore game state from Journal or start new game
        self._game.new_game()

    def _setup_toolbars(self, have_toolbox):
        """ Setup the toolbars. """

        self.max_participants = 1

        if have_toolbox:
            toolbox = ToolbarBox()

            # Activity toolbar
            activity_button = ActivityToolbarButton(self)

            toolbox.toolbar.insert(activity_button, 0)
            activity_button.show()

            self.set_toolbar_box(toolbox)
            toolbox.show()
            self.toolbar = toolbox.toolbar

        else:
            # Use pre-0.86 toolbar design
            games_toolbar = gtk.Toolbar()
            toolbox = activity.ActivityToolbox(self)
            self.set_toolbox(toolbox)
            toolbox.add_toolbar(_('Game'), games_toolbar)
            toolbox.show()
            toolbox.set_current_toolbar(1)
            self.toolbar = games_toolbar

        self._new_game_button = button_factory(
            'new-game', self.toolbar, self._new_game_cb,
            tooltip=_('Start a new game.'))

        self.status = label_factory(self.toolbar, '')

        separator_factory(toolbox.toolbar, True, False)

        self.load_python = button_factory(
            'pippy-openoff', self.toolbar,
            self._do_load_python_cb,
            tooltip=_('Load strategy from Journal'))

        self.reload_strategy = button_factory(
            'system-restart', self.toolbar,
            self._do_reset_strategy_cb,
            tooltip=_('Load default strategy'))

        if _have_toolbox:
            stop_button = StopButton(self)
            stop_button.props.accelerator = '<Ctrl>q'
            toolbox.toolbar.insert(stop_button, -1)
            stop_button.show()

    def _new_game_cb(self, button=None):
        ''' Start a new game. '''
        self._game.new_game()

    def write_file(self, file_path):
        """ Write the grid status to the Journal """
        return

    def _restore(self):
        """ Restore the game state from metadata """
        return

    def _do_reset_strategy_cb(self, button):
        ''' Reset the strategy to default '''
        self._game.reset_strategy()

    def _do_load_python_cb(self, button):
        ''' Load Python code from the Journal. '''
        self._chooser('org.laptop.Pippy',
                self._load_python_code_from_journal)

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
        self._game.strategy = python_code

    def _chooser(self, filter, action):
        ''' Choose an object from the datastore and take some action '''
        chooser = None
        try:
            chooser = ObjectChooser(parent=self, what_filter=filter)
        except TypeError:
            chooser = ObjectChooser(
                None, self,
                gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
        if chooser is not None:
            try:
                result = chooser.run()
                if result == gtk.RESPONSE_ACCEPT:
                    dsobject = chooser.get_selected_object()
                    action(dsobject)
                    dsobject.destroy()
            finally:
                chooser.destroy()
                del chooser
