-- ZorpOS MacBook edition: overrides on top of zorpos.lua (loaded at its end).
-- Tuned for 2013-2015 MacBook Pro: Intel Iris / Iris Pro driving a 2560x1600 or 2880x1800 Retina panel.
-- The look stays (glass, jelly springs, glow); the expensive parts get cheaper.

-- Retina panel: exact 2x. Hyprland's "auto" can pick a fractional scale, which is slower and blurrier.
local function panel_width()
    local p = io.popen("cat /sys/class/drm/card*-eDP-*/modes 2>/dev/null | head -n1")
    if not p then return 0 end
    local line = p:read("*l") or ""
    p:close()
    return tonumber(line:match("^(%d+)x")) or 0
end
if panel_width() >= 2560 then
    hl.monitor({ output = "eDP-1", mode = "preferred", position = "auto", scale = 2 })
end

hl.config({
    decoration = {
        inactive_opacity = 1.0,                 -- no translucent blending of every unfocused window
        shadow = { enabled = true, range = 10, render_power = 3 },
        -- xray: glass blurs only the wallpaper, which Hyprland blurs once and caches, instead of
        -- re-blurring whatever windows are underneath every frame. Biggest single win on Iris.
        blur = { enabled = true, size = 5, passes = 1, xray = true, new_optimizations = true },
    },
    render = { cm_enabled = false },            -- skip color-management shaders (sRGB panel anyway)
    misc = { render_unfocused_fps = 10 },
    input = {
        touchpad = {
            natural_scroll = true,
            tap_to_click = true,
            clickfinger_behavior = true,        -- two-finger click = right click, like macOS
            disable_while_typing = true,
            scroll_factor = 0.6,
        },
    },
})

-- The rotating border gradient repaints every window border on every frame; keep it still.
hl.animation({ leaf = "borderangle", enabled = false })
-- Jelly stays, just a touch quicker so it settles in fewer frames.
hl.animation({ leaf = "windows",     enabled = true, speed = 6, spring = "jelly" })
hl.animation({ leaf = "windowsIn",   enabled = true, speed = 6, spring = "jelly", style = "popin 70%" })

-- Trackpad: three-finger swipe between planets (workspaces)
hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })

-- Mac keyboard: Cmd is Super, so Cmd+Q closes, Cmd+Space opens the Eye. Backlight keys:
local kbd = "brightnessctl --device='smc::kbd_backlight' set "
hl.bind("XF86KbdBrightnessUp",   hl.dsp.exec_cmd(kbd .. "10%+"), { locked = true, repeating = true })
hl.bind("XF86KbdBrightnessDown", hl.dsp.exec_cmd(kbd .. "10%-"), { locked = true, repeating = true })
-- Mission Control / Launchpad keys (F3/F4) open the star map and the Eye
hl.bind("XF86LaunchA", hl.dsp.exec_cmd("zorp-hivectl starmap"))
hl.bind("XF86LaunchB", hl.dsp.exec_cmd("zorp-hivectl eye"))
