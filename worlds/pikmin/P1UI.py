from kvui import GameManager, context_type, TooltipLabel
from kivy.metrics import sp
from kivy.uix.layout import Layout


def build_p1_ui(base: "type[GameManager]") -> "type[GameManager]":
    """Construit l'UI du client Pikmin au-dessus de `base`.

    #37 : quand Universal Tracker est installe, `base` est l'UI de UT (onglet
    Tracker inclus) ; sinon c'est le GameManager standard d'Archipelago.
    """

    class P1UI(base):

        base_title = "Pikmin Archipelago Client"

        def __init__(self, ctx: context_type):
            super().__init__(ctx)

        def build(self) -> Layout:
            container = super().build()
            # #2 : armer le chien de garde de fermeture DES le clic sur la croix.
            # Dans les logs du bug, Kivy sort de sa boucle ("Leaving application
            # in progress...") mais on_stop (qui leve exit_event) n'est jamais
            # atteint : le blocage a lieu pendant la fermeture Kivy/SDL elle-meme.
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
            return False  # ne pas bloquer la fermeture

        def update_texts(self, dt):
            super().update_texts(dt)
            self.dolphin_status_bar.text = "Dolphin Status: " + self.ctx.dolphin_status_text

    return P1UI


# UI sans Universal Tracker (compatibilite).
P1UI = build_p1_ui(GameManager)
