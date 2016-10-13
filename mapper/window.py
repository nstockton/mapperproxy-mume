# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

###Some code borrowed from pymunk's debug drawing functions###

import pyglet
pyglet.options['debug_gl'] = False
from pyglet.window import key
from speechlight import Speech
import math
from collections import namedtuple
try:
	from Queue import Empty as QueueEmpty
except ImportError:
	from queue import Empty as QueueEmpty

from .constants import TERRAIN_COLORS
from .vec2d import Vec2d

# Monkey patch range with xrange in Python2.
_range = range
try:
	range = xrange
except NameError:
	pass

FPS=1.0/60
KEYS={
(key.F11,0):'toggle_fullscreen'
}

class Color(namedtuple("Color", ["r","g","b","a"])):
	"""Color tuple used by the debug drawing API.
	"""
	__slots__ = ()	

	def as_int(self):
		return int(self[0]), int(self[1]), int(self[2]), int(self[3])

	def as_float(self):
		return self[0]/255., self[1]/255., self[2]/255., self[3]/255.


class Window(pyglet.window.Window):
	def __init__(self, world):
		caption='MPM'
		super(Window, self).__init__(caption=caption, resizable=True, fullscreen=True)
		self.speech=Speech()
		self.say=self.speech.say
		self.maximize()
		self.world=world
		self._gui_queue = world._gui_queue
		self._gui_queue_lock = world._gui_queue_lock
		self.batch=pyglet.graphics.Batch()
		self.visible_rooms={}
		pyglet.clock.schedule_interval(self.queue_observer, FPS)
		self.size=100.0
		self.spacer=0.7
		self.current_room_border1=0.1
		self.current_room_border2=0.5
		self.current_room_border_color=Color(255,255,255,255)
		self.current_room_border_vl = self._draw_current_room_border()

	@property
	def cx(self):
		return self.width/2.0

	@property
	def cy(self):
		return self.height/2.0

	@property
	def cp(self):
		return Vec2d(self.cx,self.cy)

	def queue_observer(self, dt):
		with self._gui_queue_lock:
			while not self._gui_queue.empty():
				try:
					e = self._gui_queue.get_nowait()
					if e is None:
						self.close()
						break
					self.dispatch_event(e[0], *e[1:])
				except QueueEmpty:
					break

	def on_draw(self):
		pyglet.gl.glClearColor(0,0,0,0)
		self.clear()
		self.batch.draw()

	def on_map_sync(self, currentRoom):
		self.draw_rooms(currentRoom)

	def on_key_press(self, sym, mod):
		k=(sym, mod)
		if k in KEYS:
			funcname='do_'+KEYS[k]
			try:
				func=getattr(self, funcname)
				try:
					func(sym, mod)
				except Exception as e:
					self.say(e.message)
			except AttributeError:
				self.say('Invalid key assignment for key {}. No such function {}.'.format(k, funcname))

	def do_toggle_fullscreen(self, sym, mod):
		self.set_fullscreen(not self.fullscreen)

	def draw_circle(self, cp, radius, color, line_color=None, angle=0.0):
		cp = Vec2d(cp)
		#http://slabode.exofire.net/circle_draw.shtml
		num_segments = int(4 * math.sqrt(radius))
		theta = 2 * math.pi / num_segments
		c = math.cos(theta)
		s = math.sin(theta)
		x = radius # we start at angle 0
		y = 0
		ps = []
		for i in range(num_segments):
			ps += [Vec2d(cp.x + x, cp.y + y)]
			t = x
			x = c * x - s * y
			y = s * t + c * y
		mode = pyglet.gl.GL_TRIANGLE_STRIP
		ps2 = [ps[0]]
		for i in range(1, int(len(ps)+1/2)):
			ps2.append(ps[i])
			ps2.append(ps[-i])
		ps = ps2
		vs = []
		for p in [ps[0]] + ps + [ps[-1]]:
				vs += [p.x, p.y]
		c = cp + Vec2d(radius, 0).rotated(angle)
		cvs = [cp.x, cp.y, c.x, c.y]
		bg = pyglet.graphics.OrderedGroup(0)
		fg = pyglet.graphics.OrderedGroup(1)
		l = len(vs)//2
		if line_color is None:
			line_color=color
		return (self.batch.add(len(vs)//2, mode, bg,
				('v2f', vs),
				('c4B', color.as_int()*l)), \
		self.batch.add(2, pyglet.gl.GL_LINES, fg,
				('v2f', cvs),
				('c4B', line_color.as_int()*2)))

	def draw_segment(self, a, b, color, group=None):
		pv1 = Vec2d(a)
		pv2 = Vec2d(b)
		line = (int(pv1.x), int(pv1.y), int(pv2.x), int(pv2.y))
		return self.batch.add(2, pyglet.gl.GL_LINES, group,
					('v2i', line),
					('c4B', color.as_int() * 2))

	def draw_fat_segment(self, a, b, radius, color, group=None):
		pv1 = Vec2d(a)
		pv2 = Vec2d(b)
		d = pv2 - pv1
		a = -math.atan2(d.x, d.y)
		radius = max(radius, 1)
		dx = radius * math.cos(a)
		dy = radius * math.sin(a)
		p1 = pv1 + Vec2d(dx,dy)
		p2 = pv1 - Vec2d(dx,dy)
		p3 = pv2 + Vec2d(dx,dy)
		p4 = pv2 - Vec2d(dx,dy)
		vs = [i for xy in [p1,p2,p3]+[p2,p3,p4] for i in xy]
		l = len(vs)//2
		return self.batch.add(l,pyglet.gl.GL_TRIANGLES, group,
					('v2f', vs),
					('c4B', color.as_int() * l))

	def corners_2_vertices(self,ps):
		ps = [ps[1],ps[2], ps[0]] + ps[3:]
		vs = []
		for p in [ps[0]] + ps + [ps[-1]]:
			vs += [p.x, p.y]
		return vs

	def draw_polygon(self, verts, color, group=None):
		mode = pyglet.gl.GL_TRIANGLE_STRIP
		vs=self.corners_2_vertices(verts)
		l = len(vs)//2
		vl=self.batch.add(l, mode, group,
					('v2f', vs),
					('c4B', color.as_int()*l))
		return vl

	@property
	def cx(self):
		return self.width/2.0
	@property
	def cy(self):
		return self.height/2.0
	@property
	def cp(self):
		return Vec2d(self.cx,self.cy)

	def num_rooms_to_draw(self):
		rooms_w=(self.width//self.size)//2
		rooms_h=(self.height//self.size)//2
		return (int(rooms_w),int(rooms_h),1)

	def _draw_current_room_border(self):
		d = (self.size/2.0) * (1.0+self.current_room_border1)
		cp=self.cp
		vs=[cp-d, cp-(d,d*-1), cp+d, cp+(d,d*-1)]
		vl1 = self.draw_polygon(vs, Color(0,0,0,255), group=pyglet.graphics.OrderedGroup(1))
		d *= 1.0+self.current_room_border2
		vs=[cp-d, cp-(d,d*-1), cp+d, cp+(d,d*-1)]
		vl2 = self.draw_polygon(vs, self.current_room_border_color, group=pyglet.graphics.OrderedGroup(0))
		return (vl1, vl2)

	def draw_room(self, room, cp):
		try:
			color=Color(*TERRAIN_COLORS[room.terrain])
		except KeyError as e:
			print 'Unknown terrain type "{}" @{}!'.format(e.message, room.vnum)
			color=Color(0,0,0,0)
		d=self.size/2.0
		vs=[cp-d, cp-(d,d*-1), cp+d, cp+(d,d*-1)]
		if room.vnum not in self.visible_rooms:
			vl = self.draw_polygon(vs, color, group=pyglet.graphics.OrderedGroup(2))
			self.visible_rooms[room.vnum] = vl
		else:
			vl=self.visible_rooms[room.vnum]
			vl.vertices=self.corners_2_vertices(vs)

	def draw_rooms(self, currentRoom):
		self.draw_room(currentRoom, self.cp)
		newrooms=set([currentRoom.vnum])
		for vnum, room, x, y, z in self.world.getVisibleNeighbors(roomObj=currentRoom, radius=self.num_rooms_to_draw()):
			if z == 0:
				newrooms.add(vnum)
				d=Vec2d(x, y)*(self.size*(self.spacer+1.0))
				self.draw_room(room, self.cp + d)
		s=set(self.visible_rooms.keys())
		if not s: return
		for dead in s^newrooms:
			self.visible_rooms[dead].delete()
			del self.visible_rooms[dead]

Window.register_event_type('on_map_sync')
