/* Abduction Sequence slideshow (original text + ZorpOS art). Calamares slideshow API 2. */
import QtQuick 2.15
import calamares.slideshow 1.0

Presentation {
    id: presentation
    function nextSlide() { presentation.goToNextSlide(); }
    Timer { interval: 7000; running: presentation.activatedInCalamares; repeat: true; onTriggered: nextSlide() }

    component ZSlide: Slide {
        property string art: ""
        property string head: ""
        property string body: ""
        Rectangle { anchors.fill: parent; gradient: Gradient {
            GradientStop { position: 0.0; color: "#@TEAL_DEEP@" } GradientStop { position: 1.0; color: "#@VOID@" } } }
        Image { id: pic; source: art; height: parent.height * 0.48; fillMode: Image.PreserveAspectFit
                anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top; anchors.topMargin: parent.height * 0.06 }
        Text { id: h; text: head; color: "#@AQUA_GLOW@"; font.pixelSize: 30; font.bold: true; font.family: "Doto"
               anchors.horizontalCenter: parent.horizontalCenter; anchors.top: pic.bottom; anchors.topMargin: 18 }
        Text { text: body; color: "#@TEXT@"; font.pixelSize: 17; font.family: "Comfortaa"; wrapMode: Text.WordWrap
               horizontalAlignment: Text.AlignHCenter; width: parent.width * 0.8
               anchors.horizontalCenter: parent.horizontalCenter; anchors.top: h.bottom; anchors.topMargin: 12 }
    }

    ZSlide { art: "ufo.png"; head: "ABDUCTION IN PROGRESS"
             body: "Hold still. ZorpOS is being copied onto your machine. Nothing is uploaded anywhere; the mothership is a metaphor." }
    ZSlide { art: "zorp.png"; head: "THE HIVE"
             body: "No taskbar. Tap Super to summon the Mothership Eye. Workspaces are planets, minimized windows live in jars, and labels translate when you hover." }
    ZSlide { art: "zorp.png"; head: "EARTHLING MODE"
             body: "Super+Shift+E switches to English labels, a normal dock and normal workspaces, anytime. Ctrl+Alt+F3 always gives you a text console." }
    ZSlide { art: "ufo.png"; head: "XENOSCRIBE"
             body: "Write transmissions in the alien word processor. It still opens and saves .docx, .odt, .pdf and .md for Earth." }
    ZSlide { art: "ufo.png"; head: "GAMER HIVE"
             body: "Pick 'Gamer Hive' at login to boot straight into Steam Big Picture. Proton-GE, gamemode and the MangoHud vitals overlay are ready." }

    function onActivate() { presentation.currentSlide = 0; }
    function onLeave() { }
}
