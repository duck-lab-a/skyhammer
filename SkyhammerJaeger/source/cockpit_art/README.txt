ODIN cockpit overlay assets
Game files:
 SJ_Cockpit_Visor.png 1920x1080 RGBA
 SJ_Cockpit_Glass.png 1920x1080 RGBA
 SJ_Cockpit_HUD.png 1920x1080 RGBA
 SJ_Cockpit_Emblem.png 512x512 RGBA
 SJ_Cockpit_layout.json

PNG alpha is straight/unassociated. Transparent pixels have zero RGB.
Draw layers in order: Visor, Glass, HUD, Lua dynamic values, transient Emblem.
Keep texture color white and opacity 1 when drawing; each image already encodes its own alpha.
Glass alpha never exceeds 38/255 (14.91 percent).
The central visor and all four dynamic regions are completely transparent.
For any screen aspect ratio, scale x and w by screenWidth/1920 and y and h by screenHeight/1080.
The emblem can be drawn temporarily at the desired center size, using the layout preview rectangle as an example.
All HUD slots lie inside the 10-percent safe zone. No text or numerals are baked in.
The emblem uses a circular reactor, triangle and paired notches instead of literal 07 digits.

Source:
 SJ_Cockpit_Visor_source.blend: original editable 3D visor armor and lights.
 SJ_Cockpit_HUD_source.svg and SJ_Cockpit_Emblem_source.svg: editable geometry paths.
 *_highres.png: high-resolution masters.
 build_visor.py: Blender Cycles visor render.
 build_layers.py: HUD, glass, emblem and coordinate layout.
 finish_cockpit.py: charcoal/orange finishing, alpha, PNG size checks and previews.
 preview.png: all layers on a neutral dark background.
 aspect_ratio_check.png: 16:9, 16:10 and 21:9 stretch previews.

Rebuild in order: build_visor.py, build_layers.py, finish_cockpit.py.
Run build_visor.py with Blender; other scripts require Python, Pillow and NumPy.
The finish step color-grades the fresh high-resolution visor, so rebuild it before repeating the finish step.
No Lua, mod.info, gameplay code or other mods were modified.
