# -*- coding: utf-8 -*-
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

from gettext import gettext as _

from random import uniform

import traceback
import logging
_logger = logging.getLogger('turtle-in-a-pond-activity')

try:
    from sugar.graphics import style
    GRID_CELL_SIZE = style.GRID_CELL_SIZE
except ImportError:
    GRID_CELL_SIZE = 0

from sprites import Sprites, Sprite

FILL = 1
STROKE = 0
THIRTEEN = 13
DOT_SIZE = 20
CIRCLE = [[(0, -1), (1, 0), (0, 1), (-1, 1), (-1, 0), (-1, -1)],
          [(1, -1), (1, 0), (1, 1), (0, 1), (-1, 0), (0, -1)]]
''' Simple strategy: randomly check for an open dot
    turtle is the (col, row) of the current turtle position '''
STRATEGY = 'def _turtle_strategy(self, turtle):\n\
    c = turtle[1] % 2\n\
    n = int(uniform(0, 6))\n\
    for i in range(6):\n\
        col = turtle[0] + CIRCLE[c][(i + n) % 6][0]\n\
        row = turtle[1] + CIRCLE[c][(i + n) % 6][1]\n\
        if not self._dots[self._grid_to_dot((col, row))].type:\n\
            return [col, row]\n\
    return turtle\n\
'


class Game():

    def __init__(self, canvas, parent=None, colors=['#A0FFA0', '#FF8080']):
        self._activity = parent
        self._colors = colors

        self._canvas = canvas
        parent.show_all()

        self._canvas.set_flags(gtk.CAN_FOCUS)
        self._canvas.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self._canvas.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
        self._canvas.connect("expose-event", self._expose_cb)
        self._canvas.connect("button-press-event", self._button_press_cb)
        self._canvas.connect("button-release-event", self._button_release_cb)

        self._width = gtk.gdk.screen_width()
        self._height = gtk.gdk.screen_height() - (GRID_CELL_SIZE * 1.5)
        self._scale = self._height / (14.0 * DOT_SIZE * 1.5)
        self._dot_size = int(DOT_SIZE * self._scale)
        self._space = int(self._dot_size / 2.)
        self.strategy = STRATEGY

        # Generate the sprites we'll need...
        self._sprites = Sprites(self._canvas)
        self._dots = []
        for y in range(THIRTEEN):
            for x in range(THIRTEEN):
                xoffset = int((self._width - THIRTEEN * (self._dot_size + \
                                      self._space) - self._space) / 2.)
                if y % 2 == 1:
                    xoffset += int((self._dot_size + self._space) / 2.)
                if x == 0 or y == 0 or x == THIRTEEN - 1 or y == THIRTEEN - 1:
                    self._dots.append(
                        Sprite(self._sprites,
                               xoffset + x * (self._dot_size + self._space),
                               y * (self._dot_size + self._space),
                               self._new_dot('#C0C0C0')))
                else:
                    self._dots.append(
                        Sprite(self._sprites,
                               xoffset + x * (self._dot_size + self._space),
                               y * (self._dot_size + self._space),
                               self._new_dot(self._colors[FILL])))
                    self._dots[-1].type = False  # not set

        # Put a turtle at the center of the screen
        pos = self._dots[int(THIRTEEN * THIRTEEN / 2)].get_xy()
        self._turtle = Sprite(self._sprites, pos[0], pos[1], self._new_turtle())

        # and initialize a few variables we'll need.
        self._all_clear()

    def _all_clear(self):
        ''' Things to reinitialize when starting up a new game. '''
        self._press = None
        self._release = None
        self.last_spr_moved = None
        self.whos_turn = 0
        self._waiting_for_my_turn = False
        self.saw_game_over = False

        # Clear dots
        for dot in self._dots:
            if dot.type:
                dot.type = False
                dot.set_shape(self._new_dot(self._colors[FILL]))                

        # Recenter the turtle
        pos = self._dots[int(THIRTEEN * THIRTEEN / 2)].get_xy()
        self._turtle.move(pos)

    def _initiating(self):
        return self._activity.initiating

    def reset_strategy(self):
        ''' Reload default strategy '''
        self.strategy = STRATEGY

    def new_game(self, saved_state=None):
        ''' Start a new game. '''
        self._all_clear()

        for i in range(10):
            n = int(uniform(0, THIRTEEN * THIRTEEN))
            if self._dots[n].type is not None:
                self._dots[n].type = True
                self._dots[n].set_shape(self._new_dot(self._colors[STROKE]))

    def _set_label(self, string):
        ''' Set the label in the toolbar or the window frame. '''
        self._activity.status.set_label(string)

    def _button_press_cb(self, win, event):
        self._press = None
        win.grab_focus()
        x, y = map(int, event.get_coords())

        spr = self._sprites.find_sprite((x, y))
        if spr == None:
            return

        if spr.type is not None and not spr.type:
            self._press = spr
            spr.type = True
            spr.set_shape(self._new_dot(self._colors[STROKE]))
            self._test_game_over(self._move_the_turtle())

        self._release = None
        return True

    def _move_the_turtle(self):
        ''' Move the turtle after each click '''
        turtle_pos = self._turtle.get_xy()
        clicked_dot = self._dots.index(self._press)
        self._turtle_dot = None
        for dot in self._dots:
            pos = dot.get_xy()
            if pos[0] == turtle_pos[0] and pos[1] == turtle_pos[1]:
                self._turtle_dot = self._dots.index(dot)
                break
        if self._turtle_dot is None:
            _logger.debug('Cannot find the turtle...')
            return

        # Given the col and row of the turtle and the clicked dot, do something
        new_dot = self._grid_to_dot(
            self._my_strategy_import(self.strategy,
                                     self._dot_to_grid(self._turtle_dot)))
        pos = self._dots[new_dot].get_xy()
        self._turtle.move(pos)
        return new_dot

    def _test_game_over(self, new_dot):
        ''' Check to see if game is over '''
        if self._dots[new_dot].type is None:
            self._set_label(_('turtle wins'))
            return True
        c = int(self._turtle_dot / THIRTEEN) % 2
        if self._dots[
            new_dot + CIRCLE[c][0][0] + THIRTEEN * CIRCLE[c][0][1]].type and \
           self._dots[
            new_dot + CIRCLE[c][1][0] + THIRTEEN * CIRCLE[c][1][1]].type and \
           self._dots[
            new_dot + CIRCLE[c][2][0] + THIRTEEN * CIRCLE[c][2][1]].type and \
           self._dots[
            new_dot + CIRCLE[c][3][0] + THIRTEEN * CIRCLE[c][3][1]].type and \
           self._dots[
            new_dot + CIRCLE[c][4][0] + THIRTEEN * CIRCLE[c][4][1]].type and \
           self._dots[
            new_dot + CIRCLE[c][5][0] + THIRTEEN * CIRCLE[c][5][1]].type:
            self._set_label(_('you win'))
            return True
        return False

    def _grid_to_dot(self, pos):
        ''' calculate the dot index from a column and row in the grid '''
        return pos[0] + pos[1] * THIRTEEN

    def _dot_to_grid(self, dot):
        ''' calculate the grid column and row for a dot '''
        return [dot % THIRTEEN, int(dot / THIRTEEN)]

    def _button_release_cb(self, win, event):
        win.grab_focus()

        if self._press is None:
            return

        x, y = map(int, event.get_coords())
        spr = self._sprites.find_sprite((x, y))
        self._release = spr
        self._press = None
        self._release = None
        return True

    def game_over(self, msg=_('Game over')):
        ''' Nothing left to do except show the results. '''
        self._set_label(msg)
        self.saw_game_over = True

    def _expose_cb(self, win, event):
        ''' Callback to handle window expose events '''
        self.do_expose_event(event)
        return True

    def do_expose_event(self, event):
        ''' Handle the expose-event by drawing '''
        # Restrict Cairo to the exposed area
        cr = self._canvas.window.cairo_create()
        cr.rectangle(event.area.x, event.area.y,
                event.area.width, event.area.height)
        cr.clip()
        # Refresh sprite list
        self._sprites.redraw_sprites(cr=cr)

    def _destroy_cb(self, win, event):
        gtk.main_quit()

    def _new_dot(self, color):
        ''' generate a dot of a color color '''
        self._stroke = color
        self._fill = color
        self._svg_width = self._dot_size
        self._svg_height = self._dot_size
        return svg_str_to_pixbuf(
            self._header() + \
            self._circle(self._dot_size / 2., self._dot_size / 2.,
                         self._dot_size / 2.) + \
            self._footer())

    def _new_turtle(self):
        ''' generate a turtle '''
        self._svg_width = self._dot_size
        self._svg_height = self._dot_size
        return svg_str_to_pixbuf(
            self._header() + \
            self._turtle(self._dot_size / 2., self._dot_size / 2.,
                         self._dot_size / 2.) + \
            self._footer())

    def _header(self):
        return '<svg\n' + 'xmlns:svg="http://www.w3.org/2000/svg"\n' + \
            'xmlns="http://www.w3.org/2000/svg"\n' + \
            'xmlns:xlink="http://www.w3.org/1999/xlink"\n' + \
            'version="1.1"\n' +  'width="' + str(self._svg_width) +  '"\n' + \
            'height="' + str(self._svg_height) + '">\n'

    def _circle(self, r, cx, cy):
        return '<circle style="fill:' + str(self._fill) + ';stroke:' + \
            str(self._stroke) +  ';" r="' + str(r - 0.5) +  '" cx="' + \
            str(cx) + '" cy="' + str(cy) + '" />\n'

    def _turtle(self, r, cx, cy):
        return '<circle style="fill:#000000;stroke:#999999;" r="' + \
            str(r - 0.5) +  '" cx="' + \
            str(cx) + '" cy="' + str(cy) + '" />\n'

    def _footer(self):
        return '</svg>\n'

    def _my_strategy_import(self, f, arg):
        ''' Run Python code passed as argument '''
        userdefined = {}
        try:
            exec f in globals(), userdefined
            return userdefined['_turtle_strategy'](self, arg)
        except:
            traceback.print_exc()
            return None


def svg_str_to_pixbuf(svg_string):
    """ Load pixbuf from SVG string """
    pl = gtk.gdk.PixbufLoader('svg')
    pl.write(svg_string)
    pl.close()
    pixbuf = pl.get_pixbuf()
    return pixbuf
