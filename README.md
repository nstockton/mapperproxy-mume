# Mapper Proxy

A mapper proxy for playing [MUME,](https://mume.org "MUME Official Site") targeted towards the needs of blind players. It is entirely controlled by plain text commands, and offers some facilities such as pathfinding and room finding. It also comes with a high contrast GUI for visually impaired players, and a tiled one for sighted players.

---

![screenshot of the sighted GUI](https://github.com/nstockton/mapperproxy-mume/raw/master/src/mapper_data/tiles/screenshot-multi.png?raw=true "screenshot of the sighted GUI")

---

## License And Credits

Mapper Proxy is licensed under the terms of the [Mozilla Public License, version 2.0.](https://nstockton.github.io/mapperproxy-mume/license "License Page")

The tiles of the GUI for sighted players are distributed under the [CC-BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/legalcode "CC-BY-SA 3.0 official site") license.
They are a modified version of [fantasy-tileset.png](https://opengameart.org/content/32x32-fantasy-tileset "fantasy-tileset page on OpenGameArt") originally created by [Jerome.](http://jerom-bd.blogspot.fr/ "Jerome old site")

This project created and maintained by [Nick Stockton.](https://github.com/nstockton)
Numerous features and bug fixes contributed by [Ted Cooke.](https://github.com/BeastlyTheos)
High contrast GUI contributed by Katalina Durden.
Sighted GUI and various additions contributed by Lindisse.

## Documentation

Please see the [API reference](https://nstockton.github.io/mapperproxy-mume/api "Mapper Proxy API Reference") for more information.

## Installation

### As Part of Mud Clients

Mapper Proxy is distributed as part of [MUSHclient-MUME](https://github.com/nstockton/mushclient-mume) which also provides scripts for playing the game.

### Running From Source

Install the [Python interpreter,](https://python.org "Python Home Page") and make sure it's in your path before running this package.

After Python is installed, execute the following commands from the top level directory of this repository to install the module dependencies.
```
python -m venv .venv
source .venv/bin/activate
pip install --upgrade --require-hashes --requirement requirements-poetry.txt
poetry install --no-ansi
```

If you wish to contribute to this project, install the development dependencies with the following commands.
```
source .venv/bin/activate
pre-commit install -t pre-commit
pre-commit install -t pre-push
```

## Mapper Proxy Usage

### Manual Startup

To start Mapper Proxy, activate the virtual environment by running `source .venv/bin/activate`, and then run `mapper` from the root directory of this project. It accepts the following arguments:

- `-h`, `--help` Show program's help and exit.
- `-v`, `--version` Show program's version number and exit.
- `-e`, `--emulation` Start in emulation mode. The mapper will not connect to MUME.
- `-i [text|hc|sighted]`, `--interface [text|hc|sighted]` Select an interface. Text-only mode, high contrast GUI, or sighted GUI. The high contrast GUI is a high contrast one for visually impaired players. The sighted GUI uses png tiles. Default is "_text_" mode (no GUI).
- `-f [normal|tintin|raw]`, `--format [normal|tintin|raw]` Select how the data from the server is transformed before being sent to the client. Normal mode filters out XML tags from the data received by the mud before sending it to the user's mud client, TinTin sends certain tags to the client in a special format for the mud client to trigger on, and raw sends the data from the mud to the mud client unmodified. Default is "_normal_".
- `-lh address`, `--local_host address` The local host address to bind to. Default is "_127.0.0.1_".
- `-lp port`, `--local_port port` The local port to bind to. Default is "_4000_".
- `-rh address`, `--remote_host address` The remote host address to connect to. Default is "_mume.org_".
- `-rp port`, `--remote_port port` The remote port to connect to. Default is "_4242_".
- `-nssl`, `--no_ssl` Disable encrypted communication between the local and remote hosts. Don't do this unless you know what you're doing.
- `-ptlf`, `--prompt_terminator_lf` Terminate game prompts with new line characters (IAC + GA is default).
- `-gp`, `--gag_prompts` gag emulated prompts.
- `-ff text`, `--find_format text` The format string for controlling output of the find commands. Accepts the following placeholders in braces: `{attribute}`, `{direction}`, `{clockPosition}`, `{distance}`, `{name}`, `{vnum}`. Where `{attribute}` represents the attribute on which the search is performed. The default is `"{vnum}, {name}, {attribute}"`.

Once done, connect your client to `127.0.0.1`, port `4000`.

### Starting From a Client

It is possible to start Mapper Proxy directly from the client. Here is, for example, how to start it from a tintin+++ script, from the root directory of this project:

```
#run {mapper} {python -B}
from mapper.main import main
#action {^MPICOMMAND:%1:MPICOMMAND$} {#mume {#system %1;#mapper continue}}
#gts
#mapper main(outputFormat="tintin", interface="sighted")
```

## Mapper Proxy Command Reference

### Auto Mapping Commands

Auto mapping mode must be on for these commands to have any effect.

* `autolink`  --  Toggle Auto linking on or off. If on, the mapper will attempt to link undefined exits in newly added rooms.
* `automap`  --  Toggle automatic mapping mode on or off.
* `automerge`  --  Toggle automatic merging of duplicate rooms on or off.
* `autoupdate`  --  Toggle Automatic updating of room name/descriptions/dynamic descriptions on or off.

### Map Editing Commands

* `doorflags [add|remove] [hidden|need_key|no_block|no_break|no_pick|delayed|callable|knockable|magic|action|no_bash] [north|east|south|west|up|down]`  --  Modify door flags for a given direction.
* `exitflags [add|remove] [exit|door|road|climb|random|special|avoid|no_match] [north|east|south|west|up|down]`  --  Modify exit flags for a given direction.
* `ralign [good|neutral|evil|undefined]`  --  Modify the alignment flag of the current room.
* `ravoid [+|-]`  --  Set or clear the avoid flag for the current room. If the avoid flag is set, the mapper will try to avoid the room when path finding.
* `rdelete [vnum]`  --  Delete the room with vnum. If the mapper is synced and no vnum is given, delete the current room.
* `rlabel [add|delete|info|search] [label] [vnum]`  --  Manage room labels. Vnum is only used when adding a room. Leave it blank to use the current room's vnum. Use rlabel info all to get a list of all labels.
* `rlight [lit|dark|undefined]`  --  Modify the light flag of the current room.
* `rlink [add|remove] [oneway] [vnum] [north|east|south|west|up|down]`  --  Manually manage links from the current room to room with vnum. If oneway is given, treat the link as unidirectional.
* `rloadflags [add|remove] [treasure|armour|weapon|water|food|herb|key|mule|horse|pack_horse|trained_horse|rohirrim|warg|boat|attention|tower|clock|mail|stable|white_word|dark_word|equipment|coach]`  --  Modify the load flags of the current room.
* `rmobflags [add|remove] [rent|shop|weapon_shop|armour_shop|food_shop|pet_shop|guild|scout_guild|mage_guild|cleric_guild|warrior_guild|ranger_guild|aggressive_mob|quest_mob|passive_mob|elite_mob|super_mob|milkable]`  --  Modify the mob flags of the current room.
* `rnote [-a|-r] [text]`  --  Modify the note for the current room. If '-a' is given, append text to the current note. If '-r' is given, remove the note.
* `rportable [portable|not_portable|undefined]`  --  Modify the portable flag of the current room.
* `rridable [ridable|not_ridable|undefined]`  --  Modify the ridable flag of the current room.
* `rsundeath [sundeath|no_sundeath|undefined]`  --  Modify the sundeath flag of the current room.
* `rterrain [brush|building|cavern|city|field|forest|hills|mountains|rapids|road|shallows|tunnel|undefined|underwater|water]`  --  Modify the terrain of the current room.
* `rx [number]`  --  Modify the X coordinate of the current room.
* `ry [number]`  --  Modify the Y coordinate of the current room.
* `rz [number]`  --  Modify the Z coordinate of the current room.
* `savemap`  --  Save modifications to the map to disk.
* `secret [add|remove] [name] [north|east|south|west|up|down]`  --  Add or remove a secret door in the current room.

### Searching Commands

* `fdoor [text]`  --  Search the map for rooms with doors matching text. Returns the nearest 20 rooms to you (furthest to closest) based on the [Manhattan Distance.](https://en.wikipedia.org/wiki/Taxicab_geometry "Wikipedia Page On Taxicab Geometry")
* `fdynamic [text]`  --  Search the map for rooms with dynamic descriptions matching text. Returns the nearest 20 rooms to you (furthest to closest) based on the [Manhattan Distance.](https://en.wikipedia.org/wiki/Taxicab_geometry "Wikipedia Page On Taxicab Geometry")
* `flabel [text]`  --  Search the map for rooms with labels matching text. Returns the nearest 20 rooms to you (furthest to closest) based on the [Manhattan Distance.](https://en.wikipedia.org/wiki/Taxicab_geometry "Wikipedia Page On Taxicab Geometry") If no text is given, will show the 20 closest labeled rooms.
* `fname [text]`  --  Search the map for rooms with names matching text. Returns the nearest 20 rooms to you (furthest to closest) based on the [Manhattan Distance.](https://en.wikipedia.org/wiki/Taxicab_geometry "Wikipedia Page On Taxicab Geometry")
* `fnote [text]`  --  Search the map for rooms with notes matching text. Returns the nearest 20 rooms to you (furthest to closest) based on the [Manhattan Distance.](https://en.wikipedia.org/wiki/Taxicab_geometry "Wikipedia Page On Taxicab Geometry")

### Path Commands

* `path [vnum|label] [nodeath|nocity|noshallowwater|noforest|nohills|noroad|nocavern|nofield|nowater|nounderwater|norapids|noindoors|nobrush|notunnel|nomountains|norandom|noundefined]`  --  Print speed walk directions from the current room to the room with vnum or label. If one or more avoid terrain flags are given after the destination, the mapper will try to avoid all rooms with that terrain type. Multiple avoid terrains can be ringed together with the '|' character, for example, path ingrove noroad|nobrush.
* `run [c|t] [vnum|label] [nodeath|nocity|noshallowwater|noforest|nohills|noroad|nocavern|nofield|nowater|nounderwater|norapids|noindoors|nobrush|notunnel|nomountains|norandom|noundefined]`  --  Automatically walk from the current room to the room with vnum or label. If 'c' is provided instead of a vnum or label, the mapper will recalculate the path from the current room to the previously provided destination. If t (short for target) is given before the vnum or label, the mapper will store the destination, but won't start auto walking until the user enters 'run c'. If one or more avoid terrain flags are given after the destination, the mapper will try to avoid all rooms with that terrain type. Multiple avoid terrains can be ringed together with the '|' character, for example, run ingrove noroad|nobrush.
* `step [label|vnum]`  --  Move 1 room towards the destination room matching label or vnum.
* `stop`  --  Stop auto walking.

### Door Commands

* `secretaction [action] [north|east|south|west|up|down]`  --  Perform an action on a secret door in a given direction. This command is meant to be called from an alias. For example, secretaction open east.

### Miscellaneous Commands

* `clock [action]`  --  If no action is given, print the output from the mapper's clock. If the action is 'pull', send the appropriate commands to the game for opening the exit in mystical. If any other action is given, send a line with the current game time to the game, prefixed by the action. Example: `clock narrate` to narrate the current game time.
* `emu [command]`  --  If not in emulation mode (I.E. connected to the game), execute an emulation command.
* `getlabel [vnum]`  --  Returns the label or labels defined for the room with vnum. If no vnum is supplied, the current room's vnum is used.
* `gettimer`  --  Returns the amount of seconds since the mapper was started in an optimal format for triggering. This is to assist scripters who use clients with no time stamp support such as VIP Mud.
* `gettimerms`  --  Returns the amount of milliseconds since the mapper was started in an optimal format for triggering. This is to assist scripters who use clients with no time stamp support such as VIP Mud.
* `help`  --  If in emulation mode, print a summery of the available emulation commands.
* `maphelp`  --  Print a summery of the available mapper commands.
* `quit`  --  Quit the mapper when in emulation mode.
* `rinfo [vnum|label]`  --  Print info about the room with vnum or label. If no vnum or label is given, use current room.
* `sync [vnum|label]`  --  Manually sync the map to the room with vnum or label. If no vnum or label is given, mapper will be placed in an unsynced state, and will try to automatically sync to the current room.
* `tvnum [player]`  --  Tell the vnum of the current room to another player.
* `vnum`  --  Print the vnum of the current room.
* `wordwrap`  --  Toggle word wrapping of remote edited text on or off.
