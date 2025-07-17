from worlds.Generic import OptionDict, Choice

class PikminOptions(OptionDict):
    difficulty: Choice = Choice(0, {
        0: "Easy",
        1: "Normal",
        2: "Hard"
    })

    # Tu peux rajouter d'autres options ici si besoin
