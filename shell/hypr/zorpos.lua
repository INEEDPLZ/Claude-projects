-- ZorpOS Hyprland base config (Hyprland >= 0.57 Lua format).
-- Installed at /usr/share/zorpos/hypr/zorpos.lua and loaded by ~/.config/hypr/hyprland.lua.
-- Put personal tweaks in ~/.config/hypr/hyprland.lua AFTER the require line; don't edit this file.
--
-- Escape hatches that always work: Super+Shift+E (Earthling Mode), Super+D (plain launcher),
-- Ctrl+Alt+F3 (text console), Super+Shift+Q (leave Hyprland).

package.path = "/usr/share/zorpos/hypr/?.lua;" .. package.path
local Z = require("zorpos_tokens")
local function c(name, a) return "rgba(" .. Z[name] .. (a or "ff") .. ")" end

local terminal = "foot"
local hivectl  = "zorp-hivectl "

hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

hl.env("XCURSOR_SIZE", "28")
hl.env("HYPRCURSOR_SIZE", "28")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
hl.env("ZORP_SESSION", "hive")

hl.on("hyprland.start", function()
    hl.exec_cmd("zorp-hive")
    hl.exec_cmd("mako")
    hl.exec_cmd("systemctl --user start hyprpolkitagent")
end)

hl.config({
    general = {
        gaps_in = 8, gaps_out = 22, border_size = 3,
        col = {
            active_border   = { colors = { c("aqua"), c("acid"), c("zorp-lilac") }, angle = 45 },
            inactive_border = c("chrome-dark", "aa"),
        },
        resize_on_border = true,
        layout = "dwindle",
    },
    decoration = {
        rounding = 18, rounding_power = 3,
        active_opacity = 1.0, inactive_opacity = 0.94,
        shadow = { enabled = true, range = 22, render_power = 2, color = c("aqua", "55") },
        blur = { enabled = true, size = 6, passes = 2, vibrancy = 0.2 },
    },
    animations = { enabled = true },
    input = { kb_layout = "us", follow_mouse = 1, sensitivity = 0, touchpad = { natural_scroll = true } },
    misc = { disable_hyprland_logo = true, disable_splash_rendering = true, force_default_wallpaper = 0 },
})

-- Jelly: an underdamped spring overshoots and wobbles back. Gelatinous, but it settles fast.
hl.curve("jelly",    { type = "spring", mass = 1, stiffness = 170, damping = 10 })
hl.curve("wobble",   { type = "spring", mass = 1, stiffness = 260, damping = 14 })
hl.curve("beamOut",  { type = "bezier", points = { {0.6, -0.4}, {0.9, 0.6} } })
hl.curve("glide",    { type = "bezier", points = { {0.23, 1}, {0.32, 1} } })
hl.curve("linear",   { type = "bezier", points = { {0, 0}, {1, 1} } })

hl.animation({ leaf = "global",      enabled = true, speed = 8,   bezier = "glide" })
hl.animation({ leaf = "windows",     enabled = true, speed = 5,   spring = "jelly" })
hl.animation({ leaf = "windowsIn",   enabled = true, speed = 5,   spring = "jelly",   style = "popin 70%" })
hl.animation({ leaf = "windowsMove", enabled = true, speed = 5,   spring = "wobble" })
-- dematerialize: the window sucks inward and fades, like a reverse tractor beam
hl.animation({ leaf = "windowsOut",  enabled = true, speed = 2.2, bezier = "beamOut", style = "popin 20%" })
hl.animation({ leaf = "fadeOut",     enabled = true, speed = 2.2, bezier = "beamOut" })
hl.animation({ leaf = "border",      enabled = true, speed = 6,   bezier = "glide" })
hl.animation({ leaf = "borderangle", enabled = true, speed = 60,  bezier = "linear",  style = "loop" })
hl.animation({ leaf = "workspaces",  enabled = true, speed = 4,   bezier = "glide",   style = "fade" })
hl.animation({ leaf = "layersIn",    enabled = true, speed = 4,   spring = "wobble",  style = "popin 80%" })
hl.animation({ leaf = "layersOut",   enabled = true, speed = 2,   bezier = "glide",   style = "fade" })

-- Hive surfaces
hl.layer_rule({ name = "zorp-glass",  match = { namespace = "^zorp-(dock|jars|media|clock|vitals)$" }, blur = true, ignore_alpha = 0.05 })
hl.layer_rule({ name = "zorp-instant", match = { namespace = "^zorp-(corner|trail|wallpaper)$" }, no_anim = true })
hl.layer_rule({ name = "zorp-planets", match = { namespace = "^zorp-planets$" }, no_anim = true })

hl.window_rule({ name = "zorp-organism", match = { class = "^os\\.zorp\\.PersonalizeOrganism$" }, float = true })
hl.window_rule({ name = "zorp-welcome",  match = { title = "^Welcome to ZorpOS$" }, float = true })

-- Apps asking to minimize go into a specimen jar instead.
hl.on("window.minimize", function(w)
    pcall(function()
        hl.dispatch(hl.dsp.window.move({ workspace = "special:jar", follow = false, window = w }))
    end)
end)

local mod = "SUPER"
-- The Hive
hl.bind(mod .. " + SUPER_L",     hl.dsp.exec_cmd(hivectl .. "eye"), { release = true, description = "Mothership Eye" })
hl.bind(mod .. " + SPACE",       hl.dsp.exec_cmd(hivectl .. "eye"), { description = "Mothership Eye" })
hl.bind(mod .. " + SHIFT + E",   hl.dsp.exec_cmd(hivectl .. "earthling"), { description = "Toggle Earthling Mode" })
hl.bind(mod .. " + J",           hl.dsp.exec_cmd(hivectl .. "jar"), { description = "Put window in a specimen jar" })
hl.bind(mod .. " + TAB",         hl.dsp.exec_cmd(hivectl .. "starmap"), { description = "Star map" })
for i = 1, 5 do
    hl.bind(mod .. " + " .. i,           hl.dsp.exec_cmd(hivectl .. "planet " .. i))
    hl.bind(mod .. " + SHIFT + " .. i,   hl.dsp.window.move({ workspace = i }))
end
-- Ordinary Earth stuff (works in both modes)
hl.bind(mod .. " + RETURN",      hl.dsp.exec_cmd(terminal))
hl.bind(mod .. " + D",           hl.dsp.exec_cmd("fuzzel"), { description = "Plain app launcher" })
hl.bind(mod .. " + E",           hl.dsp.exec_cmd("zorp-specimen-archive"))
hl.bind(mod .. " + Q",           hl.dsp.window.close())
hl.bind(mod .. " + F",           hl.dsp.window.fullscreen())
hl.bind(mod .. " + V",           hl.dsp.window.float({ action = "toggle" }))
hl.bind(mod .. " + SHIFT + Q",   hl.dsp.exit(), { description = "Leave Hyprland" })
hl.bind(mod .. " + left",        hl.dsp.focus({ direction = "left" }))
hl.bind(mod .. " + right",       hl.dsp.focus({ direction = "right" }))
hl.bind(mod .. " + up",          hl.dsp.focus({ direction = "up" }))
hl.bind(mod .. " + down",        hl.dsp.focus({ direction = "down" }))
hl.bind(mod .. " + mouse:272",   hl.dsp.window.drag(),   { mouse = true })
hl.bind(mod .. " + mouse:273",   hl.dsp.window.resize(), { mouse = true })
hl.bind("Print",                 hl.dsp.exec_cmd("sh -c 'grim -g \"$(slurp)\" - | wl-copy'"))
hl.bind("XF86AudioRaiseVolume",  hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"), { locked = true, repeating = true })
hl.bind("XF86AudioLowerVolume",  hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"),      { locked = true, repeating = true })
hl.bind("XF86AudioMute",         hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"),     { locked = true })
hl.bind("XF86MonBrightnessUp",   hl.dsp.exec_cmd("brightnessctl set 5%+"), { locked = true, repeating = true })
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("brightnessctl set 5%-"), { locked = true, repeating = true })
hl.bind("XF86AudioPlay",         hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioPause",        hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioNext",         hl.dsp.exec_cmd("playerctl next"), { locked = true })
hl.bind("XF86AudioPrev",         hl.dsp.exec_cmd("playerctl previous"), { locked = true })
