# Pikmin 1 Archipelago Setup Guide

## For Windows
### Required Software
- Dolphin Emulator: https://dolphin-emu.org/download/
- Archipelago: https://github.com/ArchipelagoMW/Archipelago/releases
- Pikmin 1 APWorld: https://github.com/TheLynk/Archipelago/releases
- A Pikmin 1 GameCube (USA) (Rev 1) .iso file | ID : GPIE01 | SHA-1 : 23a153cb225fef488f57073e76df0de26789c218
- Or A Pikmin 1 GameCube (PAL) .iso file | ID : GPIP01 | SHA-1 : 40c46bd6921e55558e9838930a9ffd2179802b4f
### Installing the APWorld
Put the pikmin2.apworld file in the ```custom_worlds``` folder of your Archipelago installation. You can also just double-click the file to automatically install it.
### Configuring the YAML file
#### What is a YAML file and why do I need one?
Your YAML file contains a set of configuration options which provide the generator with information about how it should generate your game. Each player of a multiworld will provide their own YAML file. This setup allows each player to enjoy an experience customized for their taste, and different players in the same multiworld can all have different options.
#### Where do I get a YAML file?
Once you've installed the apworld, you can generate a yaml using the ```Generate Template Options``` button in the ArchipelagoLauncher. It can be found in ```Players/Templates``` after you have done so. The name of the file will be ```Pikmin.yaml```.

If the .yaml file is missing in your ```Players/Templates``` folder, then please go through the apworld installation steps again, and double check that everything was done correctly.

**IMPORTANT NOTE: The .yaml file has multiple options under ```Item & Location Options```, these are all untested (except starting_items, which has been confirmed to work) and may not work as intended.**

### Generating a Multiworld Game
#### Step 1
Place all of the players' ```.yaml``` files into the ```Players``` folder of your Archipelago installation (NOT the ```Players/Templates``` folder).
#### Step 2
Open the Archipelago Launcher (```ArchipelagoLauncher.exe```) and click the "Generate Button". If the generation succeeds, this should create a ```.zip``` archive in the ```output``` directory of your Archipelago installation.
#### Step 3
Unzip the archive that was just generated. There should be an ```.appik1``` file inside called ```AP_<seed>_P<slot>_<name>.appik1```. This file will be referred to as the Pikmin 1 setup file for the rest of the guide.
#### Step 4
Open the Archipelago Launcher (```ArchipelagoLauncher.exe```) and click the "Open Patch". It will prompt you for the Pikmin 1 setup file (the ```.appik1``` file from Step 3) and the Pikmin USA .iso file or Pikmin PAL .iso file. It will output a patched version of the game to the same directory that the patch file is in, called ```AP_<seed>_P<slot>_<name>.iso```.
#### Step 5
Wait until you have the archipelago window which indicates that the patch is finished and normally the pikmin client is already opened automatically
#### Step 6
Open your dolphin and launch the patch version of pikmin 1 which will be called ```AP_<seed>_P<slot>_<name>.iso``` and connect to the server archipelago
#### Step 7
Normally everything will be good and the reception of the objects will be fine as long as you have loaded a party or started a new one.

## IMPORTANT NOTE: Be careful to have only one open dolphin

## Hosting a Multiworld Game
You can upload the generated ```.zip``` file [here](https://archipelago.gg/uploads) to launch a server.

## Playing the Game / FAQ
There are a few important quirks that must be observed when playing.
- Little information when you take over a party of archipelago on pikmin 1 do not hesitate to start a day and finish it straight away to update the list of accessible areas or any other object of progression

## Location Abbreviations

| Location | Abbreviation |  
| --- | --- |  
| The Impact Site | TIS |  
| The Forest of Hope | TFoH |  
| The Forest Navel | TFN |  
| The Distant Spring | TDS |  
| The Final Trial | TFT |  

## Troubleshooting

- Do not run the Archipelago Launcher or Dolphin as an administrator on Windows.
- Ensure that you do not have any Dolphin cheats or codes enabled. Some cheats or codes can unexpectedly interfere with emulation and make troubleshooting errors difficult.
- Ensure that Enable Emulated Memory Size Override in Dolphin (under Options > Configuration > Advanced) is disabled.
- If the client cannot connect to Dolphin, ensure Dolphin is on the same drive as Archipelago. Having Dolphin on an external drive has reportedly caused connection issues.

## Report Bugs
You can report any issues [here](https://github.com/TheLynk/Archipelago/issues) or to [the Pikmin 1 Archipelago server thread](https://discord.com/channels/731205301247803413/1397286080184844390).
