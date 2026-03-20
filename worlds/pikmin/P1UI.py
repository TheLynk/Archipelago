from kvui import GameManager, context_type, TooltipLabel
from kivy.metrics import sp
from kivy.uix.layout import Layout


class P1UI(GameManager):

    base_title = "Pikmin Archipelago Client"

    def __init__(self, ctx: context_type):
        super().__init__(ctx)

    def build(self) -> Layout:
        super().build()
        for c in self.grid.children:
            print(type(c))

        self.dolphin_status_bar = TooltipLabel(text="Dolphin Status: Disconnected", pos_hint={"center_x": 0.5, "center_y": 0.5},
                                     font_size=sp(15))
        self.grid.add_widget(self.dolphin_status_bar, index=3)
        return self.container

    def update_texts(self, dt):
        super().update_texts(dt)
        self.dolphin_status_bar.text = "Dolphin Status: " + self.ctx.dolphin_status_text