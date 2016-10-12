import pyglet
from pyglet.window import key
from speechlight import Speech
import math
from collections import namedtuple
import Queue

from .constants import TERRAIN_COLORS
from .vec2d import Vec2d

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


class grPointSize(pyglet.graphics.Group):
	"""
	This pyglet rendering group sets a specific point size.
	"""
	def __init__(self, size=1.0):
		super(grPointSize, self).__init__()
		self.size = size
	def set_state(self):
		pyglet.gl.glPointSize(self.size)
	def unset_state(self):
		pyglet.gl.glPointSize(1.0)

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
		pyglet.clock.schedule_interval(self.queue_observer, 0.005)
		self.vl=None
		self.size=100.0

	def queue_observer(self, dt):
		with self._gui_queue_lock:
			while not self._gui_queue.empty():
				try:
					e = self._gui_queue.get_nowait()
					if e is None:
						self.close()
						break
					self.dispatch_event(e[0], *e[1:])
				except Queue.Empty:
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

	def draw_circle(self, pos, angle, radius, outline_color, fill_color):
		circle_center = Vec2d(pos)
		
		#http://slabode.exofire.net/circle_draw.shtml
		num_segments = int(4 * math.sqrt(radius))
		theta = 2 * math.pi / num_segments
		c = math.cos(theta)
		s = math.sin(theta)
		
		x = radius # we start at angle 0
		y = 0
		
		ps = []
		
		for i in range(num_segments):
			ps += [Vec2d(circle_center.x + x, circle_center.y + y)]
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
			
		c = circle_center + Vec2d(radius, 0).rotated(angle)
		cvs = [circle_center.x, circle_center.y, c.x, c.y]
			
		bg = pyglet.graphics.OrderedGroup(0)
		fg = pyglet.graphics.OrderedGroup(1)
			
		l = len(vs)//2
	   

		self.batch.add(len(vs)//2, mode, bg,
				('v2f', vs),
				('c4B', fill_color.as_int()*l))
		return self.batch.add(2, pyglet.gl.GL_LINES, fg,
				('v2f', cvs),
				('c4B', outline_color.as_int()*2))


	def draw_segment(self, a, b, color):
		pv1 = Vec2d(a)
		pv2 = Vec2d(b)
		line = (int(pv1.x), int(pv1.y), int(pv2.x), int(pv2.y))
		
		return self.batch.add(2, pyglet.gl.GL_LINES, None,
					('v2i', line),
					('c4B', color.as_int() * 2))

	def draw_fat_segment(self, a, b, radius, outline_color, fill_color):
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
		return self.batch.add(l,pyglet.gl.GL_TRIANGLES, None,
					('v2f', vs),
					('c4B', fill_color.as_int() * l))

	def draw_polygon(self, verts, color):
		ps = verts
		mode = pyglet.gl.GL_TRIANGLE_STRIP
		ps = [ps[1],ps[2], ps[0]] + ps[3:]
		vs = []
		for p in [ps[0]] + ps + [ps[-1]]:
				vs += [p.x, p.y]
		l = len(vs)//2
		return self.batch.add(l, mode, None,
					('v2f', vs),
					('c4B', color.as_int()*l))

	def draw_dot(self, size, pos, color):
		# todo: optimize this functions
		return self.batch.add(1, pyglet.gl.GL_POINTS, grPointSize(size), 
					('v2f', pos),
					('c4B', color.as_int()*1))

	@property
	def cx(self):
		return self.width/2.0
	@property
	def cy(self):
		return self.height/2.0
	@property
	def cp(self):
		return Vec2d(self.cx,self.cy)


	def draw_room(self, room, cp):
		color=Color(*TERRAIN_COLORS[room.terrain])
		d=self.size/2.0
		vs=[cp-d, cp-(d,d*-1), cp+d, cp+(d,d*-1)]
		self.draw_polygon(vs,color)


	def num_rooms_to_draw(self):
		rooms_w=(self.width//self.size)//2
		rooms_h=(self.height//self.size)//2
		return (int(rooms_w),int(rooms_h),1)

	def draw_rooms(self, currentRoom):
		self.draw_room(currentRoom, self.cp)
		for r in self.world.getVisibleNeighbors(roomObj=currentRoom, radius=self.num_rooms_to_draw()):
			if r[4] is 0:
				room=r[1]
				d=Vec2d(r[2],r[3])*(self.size*1.2)
				self.draw_room(room,self.cp+d)

Window.register_event_type('on_map_sync')
