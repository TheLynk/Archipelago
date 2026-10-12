from kvui import GameManager, context_type, TooltipLabel
from kivy.metrics import sp
from kivy.uix.layout import Layout


def build_p1_ui(base: "type[GameManager]") -> "type[GameManager]":
    """Build the Pikmin client UI on top of `base`.

    When Universal Tracker is installed, `base` is the UT UI (Tracker tab
    included); otherwise it is the standard Archipelago GameManager.
    """

    class P1UI(base):

        base_title = "Pikmin Archipelago Client"

        def __init__(self, ctx: context_type):
            super().__init__(ctx)

        def build(self) -> Layout:
            container = super().build()
            # Arm the exit watchdog as soon as the window close button is clicked:
            # on_stop may never be reached if shutdown hangs inside Kivy/SDL itself.
            from kivy.core.window import Window
            Window.bind(on_request_close=self._p1_on_request_close)

            self.dolphin_status_bar = TooltipLabel(text="Dolphin Status: Disconnected",
                                                   pos_hint={"center_x": 0.5, "center_y": 0.5},
                                                   font_size=sp(15))
            self.grid.add_widget(self.dolphin_status_bar, index=3)
            return container if container is not None else self.container

        def _p1_on_request_close(self, *args, **kwargs):
            from .P1Client import _arm_exit_watchdog
            _arm_exit_watchdog()
            return False  # do not block window close

        def update_texts(self, dt):
            super().update_texts(dt)
            self.dolphin_status_bar.text = "Dolphin Status: " + self.ctx.dolphin_status_text

    return P1UI


# UI without Universal Tracker (compatibility).
P1UI = build_p1_ui(GameManager)
