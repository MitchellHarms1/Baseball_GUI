import pygame.locals


class StateCollection:
    """Represents the current state of many common inputs

    This allows for quick and easy access and allows us to abstract
    away the event loop from the user.

    :Examples:

        ``state.keys.left or state.keys.a``

        ``state.mouse.pos``

        ``state.mouse.left``
    """

    def __init__(self):
        self.keys = KeyState()
        self.mouse = MouseState()
        self.scroll = ScrollState()

    def handle_event(self, event):
        """Handle an new event and update the state.

        This is called automatically by :class:`snäke.snäke.Game`.
        """
        if event.type == pygame.locals.KEYDOWN:
            self.keys[event.key] = True
        elif event.type == pygame.locals.KEYUP:
            self.keys[event.key] = False
        elif event.type == pygame.locals.MOUSEMOTION:
            self.mouse.x, self.mouse.y = event.pos
        elif event.type == pygame.locals.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.mouse.left = True
            elif event.button == 2:
                self.mouse.middle = True
            elif event.button == 3:
                self.mouse.right = True
            elif event.button == 4:
                self.scroll.up = True
            elif event.button == 5:
                self.scroll.down = True
        elif event.type == pygame.locals.MOUSEBUTTONUP:
            if event.button == 1:
                self.mouse.left = False
            elif event.button == 2:
                self.mouse.middle = False
            elif event.button == 3:
                self.mouse.right = False
            elif event.button == 4:
                self.scroll.up = False
            elif event.button == 5:
                self.scroll.down = False


class KeyState:
    _EXCLUDE = ['K_LAST']

    def __init__(self):
        self._state = {}
        self._keys = {}

        for i in dir(pygame.locals):
            if i.startswith('K_'):
                if i not in self._EXCLUDE:
                    name = i[2:].lower()
                    if name[0].isdigit():
                        name = '_' + name
                    self._keys[getattr(pygame.locals, i)] = name

        initial_state = list(pygame.key.get_pressed())
        for i in self._keys:
            self._state[self._keys[i]] = bool(initial_state[i])

    def __setitem__(self, key, value):
        if isinstance(key, str) and key[0].isdigit():
            key = '_' + key

        if key in self._keys:
            self._state[self._keys[key]] = value
        else:
            self._state[key] = value

    def __getitem__(self, item):
        if isinstance(item, str) and item[0].isdigit():
            item = '_' + item

        if item in self._keys:
            return self._state[self._keys[item]]
        return self._state[item]

    def __getattr__(self, item):
        return self[item]


class MouseState:
    def __init__(self):
        self.left, self.middle, self.right = pygame.mouse.get_pressed()
        self.x, self.y = pygame.mouse.get_pos()

    @property
    def pos(self):
        return self.x, self.y

    @property
    def buttons(self):
        return self.left, self.middle, self.right

    def __bool__(self):
        return self.left


class ScrollState:
    def __init__(self):
        self.up = self.down = False

    def __bool__(self):
        return self.up or self.down
