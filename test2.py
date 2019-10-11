import pyglet

arr = []
class TestGame(pyglet.window.Window):
    def __init__(self):
        super().__init__()

    def setup(self):
        global arr
        image = pyglet.image.load('sprites/base.png')
        for _ in range(5):
            arr.append(pyglet.sprite.Sprite(image, 0, 0))
        for im in arr:
            im.delete()
            print('1')

    def on_draw(self):
        self.clear()



    def update(self, delta_time):
        pass


def main():
    game_window = TestGame()
    game_window.setup()
    pyglet.clock.schedule_interval(game_window.update, 1 / 60)
    pyglet.app.run()


if __name__ == "__main__":
    main()