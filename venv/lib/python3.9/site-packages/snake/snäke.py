import inspect
import math

import pygame

try:
    import cPickle as pickle
except ImportError:
    import pickle
import time
import os

from .events import StateCollection

"""
[x] Window init
[x] Events
[x] Quit + Canceling quit
[-] Scene changing
[ ] Scene transitions
[x] Image loading
[x] Font loading
[ ] Audio loading
[ ] Audio managing
[x] State object
[x] Store active scene in state
[x] State save/load

Major profiling problems:

        756    2.547    0.003    2.547    0.003 :0(fill)
12024/11077    0.156    0.000    0.203    0.000 :0(len)
       4845    0.094    0.000    0.094    0.000 :0(round)

"""


class SnäkeError(BaseException):
    pass


class Font:
    """A cached font object.

    All method calls on instances of :class:`snäke.snäke.Font` will have their
    return values cached automatically.

    Methods from :class:`pygame.Font` are implicitly inherited.

    :param font: The font to use
    :param game: A refrence to the current game
    :type font: :class:`pygame.Font`
    :type game: :class:`snäke.snäke.Game`
    """
    def __init__(self, font, game):
        self._font = font
        self._game = game
        self._cache = {'render': {}}
        for i in dir(font):
            if i[0] != '_':
                if i != 'render':
                    setattr(self, i, self._curry(getattr(font, i), i))

    def _curry(self, method, name):
        self._cache[name] = {}

        # noinspection PyShadowingNames
        def wrapper(self, *args):
            if args not in self._cache[name]:
                self._cache[name][args] = method(*args)
            return self._cache[name][args]

        return wrapper

    def render(self, text, colour):
        """Return a :class:`snäke.snäke.Image` of the requested text.

        :param text: The text being rendered
        :param colour: The RGB tuple for the colour
        :type text: str
        :type colour: tuple
        :return: The rendered text
        :rtype: :class:`snäke.snäke.Image`
        """
        if (text, colour) not in self._cache['render']:
            text = self._font.render(text, 1, colour)

            return Image(text, self._game)
        return self._cache['render'][(text, colour)]


class FontCache:
    """A cache for :class:`pygame.Font` objects.

    Load a font using :func:`__call__`.

    :Examples:

        ::

            cache = FontCache('font.ttf', game)
            font = cache(14)  # Load the 14pt font

    :param path: The location of the font file
    :param game: The game this resource belongs to
    :type path: str
    :type game: :class:`snäke.snäke.Game`
    """
    def __init__(self, path, game):
        self.path = path
        self._game = game
        self._f_cache = {}

    def __call__(self, size):
        if size not in self._f_cache:
            self._f_cache[size] = Font(pygame.font.Font(self.path, size), self._game)
        return self._f_cache[size]


class Image:
    """This class represents any loaded texture.

    :param path: Either the location of an image or a loaded surface
    :param game: The game this resource belongs to
    :type path: str or :class:`pygame.Surface`
    :type game: :class:`snäke.snäke.Game`
    """
    def __init__(self, path, game):
        if isinstance(path, str):
            self._image = pygame.image.load(path).convert_alpha()
        else:
            self._image = path
        self._game = game
        self._rot_cache = {}

        self.size = self._image.get_size()
        self.width, self.height = self.size

    def stamp(self, pos, rot=0):
        """Stamp the texture onto the screen at a given position.

        :param pos: The position to stamp at
        :param rot: The rotation of the texture
        :type pos: tuple
        :type rot: int
        """
        if rot == 0:
            image = self._image
        else:
            if rot not in self._rot_cache:
                self._rot_cache[rot] = pygame.transform.rotate(self._image, rot)
            image = self._rot_cache[rot]

        x = pos[0] + round((self._game.width - image.get_width()) / 2)
        y = pos[1] + round((self._game.height - image.get_height()) / 2)

        # noinspection PyProtectedMember
        self._game._surface.blit(image, (x, y))


class Events:
    """This class represents all the events during the previous frame.

    :param events: The events
    :param state_collection: The global state collection
    :type events: list
    :type state_collection: :class:`snäke.events.StateCollection`

    This class implicitly inherits the global state collection, so all
    documentation for :class:`snäke.events.StateCollection` is true for this
    also.

    This class can also be iterated to access all events in the last frame.

    :Examples:

        ::

            events = game.next_frame()
            print(events.keys.up)

            if events(pygame.KEYDOWN, key=pygame.K_RIGHT):
                print('Right key pressed')
    """
    def __init__(self, events, state_collection):
        self.events = events
        self._state_collection = state_collection

    @staticmethod
    def match(event, kwargs):
        """Compare an event object with the given keywork arguments.

        Called when using :func:`__call__`. See above for an example."""
        for i in kwargs:
            if not hasattr(event, i):
                break
            if getattr(event, i) != kwargs[i]:
                break
        else:
            return True

        return False

    def __call__(self, e_type, **kwargs):
        return [
            i for i in self.events
            if i.type == e_type and self.match(i, kwargs)
        ]

    def __iter__(self):
        for i in self.events:
            yield i

    def __getattr__(self, item):
        return getattr(self._state_collection, item)


class State:
    """Represents the state of the game.

    This allows for the game to easilly be saved at any point and then
    re-loaded at a later point.
    """
    def __init__(self):
        self._active_scene = None

    def save(self, path):
        """Save the current state.

        :param path: The file to save to
        :type path: str
        """
        data = pickle.dumps(self)
        with open(path, 'wb') as file_:
            file_.write(data)

    def load_from(self, path):
        """Load the state from a given file.

        This will overwrite the existing state entirely.

        :param path: The file to load from
        :type path: str
        """
        if not os.path.exists(path):
            raise SnäkeError('Unable to load non-existing state file')
        with open(path, 'rb') as file_:
            dat = pickle.load(file_)

        # Become the loaded state file
        self.__class__ = dat.__class__
        self.__dict__ = dat.__dict__


class Resources:
    # TODO: Loading screen
    def __init__(self, path, game):
        self._path = path
        self._game = game

        self._resources = {}
        self._load()

    def _load_png(self, path):
        return Image(path, self._game)

    def _load_ttf(self, path):
        return FontCache(path, self._game)

    def _load(self):
        if not os.path.exists(self._path):
            raise SnäkeError('Resource location does not exists')

        self._resources = {}

        for i in os.listdir(self._path):
            full = os.path.join(self._path, i)
            if os.path.isdir(full):
                self._resources[i] = Resources(full, self._game)
            else:
                ext = i[::-1].split('.')[0][::-1]
                name = i[::-1].split('.')[-1][::-1]
                try:
                    # noinspection PyTypeChecker
                    self._resources[name] = getattr(self, '_load_' + ext)(full)
                except SnäkeError:
                    print('[WARNING] Skipping resource ' + full)

    def __getattr__(self, attr):
        attr = attr.split('.', 1)
        if attr[0] not in self._resources:
            raise SnäkeError('Resource ' + attr[0] + ' unknown')
        part = self._resources[attr[0]]
        if len(attr) > 1:
            part = getattr(part, attr[1])

        return part


class Sprite:
    def __init__(self, game, image, x, y, z, rot):
        self._game = game
        self.asset = image
        # TODO: Store this in `State`
        self.x = x
        self.y = y
        self._z = z
        self.z = z

        self.rot = rot

        self.stick = Game.CENTRE

        self.active = True
        self.scene = None

    def goto(self, other, z=False):
        self.x = other.x
        self.y = other.y
        if z:
            self.z = other.z

    @property
    def z(self):
        return self._z

    @z.setter
    def z(self, value):
        self._z = value
        # Re-sort the sprites list to represent the new z
        self._game.sprites.sort(key=lambda x: x.z)

    def hide(self):
        self.active = False

    def show(self):
        self.active = True

    def dist(self, other):
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def destroy(self):
        if self in self._game.sprites:
            self._game.sprites.remove(self)

    def _pos(self, texture):
        x, y = self.x, self.y

        if self.stick & Game.NORTH:
            y += (texture.height - self._game.height) / 2
        elif self.stick & Game.SOUTH:
            y = (self._game.height - texture.height) / 2 - y

        if self.stick & Game.WEST:
            x += (texture.width - self._game.width) / 2
        elif self.stick & Game.EAST:
            x = (self._game.width - texture.width) / 2 - x

        return x, y

    def render(self):
        self.asset.stamp(self._pos(self.asset), self.rot)

    @property
    def width(self):
        return self.asset.width

    @property
    def height(self):
        return self.asset.height

    def collide(self, other):
        me_rect = pygame.Rect(self.x - self.width / 2, self.y - self.height / 2,
                              self.width, self.height)

        return me_rect.colliderect(pygame.Rect(other.x - other.width / 2,
                                               other.y - other.height / 2,
                                               other.width, other.height))


class TextSprite(Sprite):
    def __init__(self, game, font, text, colour, x, y, z, rot):
        super().__init__(game, font, x, y, z, rot)
        self.text = text
        self.colour = colour

    @property
    def width(self):
        # This seems overkill, but because `.render` is fully cached, it's not
        # that bad at all. Likewise with `.height`.
        if not self.text:
            return 0
        return self.asset.render(self.text, self.colour).width

    @property
    def height(self):
        if not self.text:
            return 0
        return self.asset.render(self.text, self.colour).height

    def render(self):
        if not self.text:
            return

        text = self.asset.render(self.text, self.colour)
        text.stamp(self._pos(text), self.rot)


class Game:
    CENTRE = 0
    NORTH = 1
    SOUTH = 2
    EAST = 4
    WEST = 8

    # Nice aliases to hide the `|` operator
    NW = NORTH | WEST
    NE = NORTH | EAST
    SW = SOUTH | WEST
    SE = SOUTH | EAST

    def __init__(self, title=None, background=(0, 0, 0), resources='assets',
                 width=800, height=600, resize=False, fps=60, scale=1):
        self._title = title
        self.background = background
        self.width = width
        self.height = height
        self._scale = scale
        self._fps = fps

        self.scenes = {}
        self.state = State()
        self.state._active_scene = None

        self.sprites = []

        self.quit_handlers = []

        self._flags = pygame.RESIZABLE if resize else 0
        self._flags |= pygame.DOUBLEBUF | pygame.HWSURFACE

        self._clock = pygame.time.Clock()
        self._running = True

        # 0 errors when doing FPS calculation, so assume 30 FPS
        self.dt = 1 / 30.
        self._f_start = 0

        # We need to init first to allow for .convert()
        self._screen = None
        self._surface = None
        self.init_window()

        # Once pygame's inited, create the event state collection
        self._state_collection = StateCollection()

        if resources is not None:
            # In an ideal world, we would pass a pointer to self._surface so
            # that resources don't have to access the protected member
            # `Game._surface`, however python doesn't have pointers, and
            # self._surface gets overwritten whenever there's a change in window
            # size.
            self.assets = Resources(resources, self)

    def register(self, scene, **kwargs):
        self.scene(**kwargs)(scene)

    def scene(self, sprites=None, name=None):
        # TODO: Arguments
        def wrapper(func):
            name_ = name or func.__name__

            if sprites is not None:
                # Register sprites to scene
                for sprite in sprites:
                    sprite.scene = name_

            self.scenes[name_] = func
            if self.state._active_scene is None:
                self.state._active_scene = name_
            return func

        return wrapper

    def on_quit(self):
        def wrapper(func):
            self.quit_handlers.append(func)
            return func

        return wrapper

    def set_scene(self, scene):
        # Passing a string
        if scene in self.scenes:
            self.state._active_scene = scene
            return

        # Passing a function
        for key in self.scenes:
            if self.scenes[key] == scene:
                self.state._active_scene = key
                return

        raise SnäkeError('Unknown scene: ' + repr(scene))

    def _handle_quit(self):
        for i in self.quit_handlers:
            ret = i()
            if ret is not None and not ret:
                # A handler wants to abort.
                break
        else:
            self._running = False

    def end(self):
        self._running = False

    def sprite(self, asset, text=None, colour=None, x=0, y=0, z=0, rot=0):
        if isinstance(asset, Font):
            if colour is None:
                colour = (255 - self.background[0],
                          255 - self.background[1],
                          255 - self.background[2])
            s = TextSprite(self, asset, text or '', colour, x, y, z, rot)
        else:
            s = Sprite(self, asset, x, y, z, rot)
        self.sprites.append(s)
        self.sprites.sort(key=lambda sp: sp.z)

        return s

    # Pygame stuff
    @property
    def fps(self):
        return self._clock.get_fps()

    @property
    def size(self):
        return self.width, self.height

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, title):
        if title is None:
            title = ''
        self._title = str(title)
        pygame.display.set_caption(self._title)

    def rectangle(self, rect, colour, border=0):
        rect = pygame.Rect(rect)
        rect.x += self.width / 2
        rect.y += self.height / 2
        pygame.draw.rect(self._surface, colour, rect, border)

    def line(self, start, end, colour, width=1):
        start = (
            start[0] + self.width / 2,
            start[1] + self.height / 2
        )
        end = (
            end[0] + self.width / 2,
            end[1] + self.height / 2
        )
        pygame.draw.line(self._surface, colour, start, end, width)

    def pygame_init(self):
        # Linux has a bug where pygame.mixer.init() causes the process to hang
        # instead of stopping when closed.
        pygame.display.init()
        pygame.font.init()

    def init_window(self):
        self.pygame_init()

        if self._title:
            pygame.display.set_caption(self._title)
        self._screen = pygame.display.set_mode((self.width * self._scale,
                                                self.height * self._scale),
                                               self._flags)
        self._surface = pygame.Surface((self.width, self.height))

    def events(self):
        events = []
        for event in pygame.event.get():
            # Propagate events
            self._state_collection.handle_event(event)

            if event.type == pygame.QUIT:
                self._handle_quit()
            elif event.type == pygame.VIDEORESIZE:
                self.width = int(event.size[0] / self._scale)
                self.height = int(event.size[1] / self._scale)
                self.init_window()

            events.append(event)

        return Events(events, self._state_collection)

    def _pre_render(self):
        if self.background is not None:
            self._surface.fill(self.background)

    def draw_sprites(self):
        for sprite in self.sprites:
            if not sprite.active:
                continue

            if sprite.scene is None or sprite.scene == self.state._active_scene:
                sprite.render()

    def _post_render(self):
        if self._scale == 1:
            self._screen.blit(self._surface, (0, 0))
        else:
            scaled = pygame.transform.scale(
                self._surface, (self.width * self._scale,
                                self.height * self._scale)
            )
            self._screen.blit(scaled, (0, 0))

        pygame.display.flip()

    def next_frame(self):
        if not self._running:
            pygame.quit()
            exit(0)

        self._post_render()
        self._pre_render()

        if self.state._active_scene is not None:
            raise SnäkeError('next_frame cannot be used at the same time as scenes')

        if self._f_start != 0:
            self.dt = time.time() - self._f_start
        self._f_start = time.time()
        self._clock.tick(self._fps)

        return self.events()

    def play(self):
        """Run the mainloop"""

        if self.state._active_scene is None:
            raise SnäkeError('No scenes defined!')

        while self._running:
            self._f_start = time.time()

            self._pre_render()

            scene = self.scenes[self.state._active_scene]
            arg_count = len(inspect.signature(scene).parameters)
            if arg_count == 1:
                self.events()  # Make sure to still run the loop :)
                scene(self._surface)
            elif arg_count == 2:
                scene(self._surface, self.events())
            else:
                scene(self._surface, self.events(), self.dt)

            self._post_render()

            self._clock.tick(self._fps)
            self.dt = time.time() - self._f_start

        pygame.quit()
