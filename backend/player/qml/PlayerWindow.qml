import QtQuick
import QtQuick.Window
import JmhModernPlayer 1.0

Window {
    id: root
    width: 1280
    height: 720
    visible: true
    color: "black"
    title: player.title

    property bool controlsVisible: true
    property real progressValue: player.duration > 0 ? player.position / player.duration : 0

    function formatTime(seconds) {
        seconds = Math.max(0, Math.floor(seconds || 0))
        const h = Math.floor(seconds / 3600)
        const m = Math.floor((seconds % 3600) / 60)
        const s = seconds % 60
        function pad(v) { return v < 10 ? "0" + v : "" + v }
        return h > 0 ? pad(h) + ":" + pad(m) + ":" + pad(s) : pad(m) + ":" + pad(s)
    }

    function revealControls() {
        controlsVisible = true
        hideTimer.restart()
    }

    Timer {
        id: hideTimer
        interval: 2600
        repeat: false
        running: true
        onTriggered: if (!bottomMouse.containsMouse && !progressMouse.containsMouse) controlsVisible = false
    }

    MpvVideoItem {
        id: video
        anchors.fill: parent
        controller: player
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        onPositionChanged: root.revealControls()
        onClicked: root.revealControls()
        onDoubleClicked: player.toggleFullscreen()
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 92
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#8a000000" }
            GradientStop { position: 1.0; color: "#00000000" }
        }
        opacity: controlsVisible ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
    }

    Row {
        id: titleRow
        anchors.left: parent.left
        anchors.leftMargin: 18
        anchors.top: parent.top
        anchors.topMargin: 13
        spacing: 12
        opacity: controlsVisible ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 180 } }

        Text {
            text: player.title
            color: "white"
            font.pixelSize: 14
            font.weight: Font.DemiBold
        }

        Text {
            text: player.stateText
            color: "#b9c0cc"
            font.pixelSize: 12
        }
    }

    LoadingRing {
        anchors.centerIn: parent
        percent: player.buffering > 0 ? player.buffering : 0
        visible: player.loading
        opacity: visible ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 160 } }
    }

    Rectangle {
        id: bottomShade
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 160
        opacity: controlsVisible ? 1 : 0
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#00000000" }
            GradientStop { position: 0.55; color: "#50000000" }
            GradientStop { position: 1.0; color: "#dd000000" }
        }
        Behavior on opacity { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }
    }

    Item {
        id: bottomBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 118
        opacity: controlsVisible ? 1 : 0
        y: controlsVisible ? 0 : 12
        Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
        Behavior on y { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

        MouseArea {
            id: bottomMouse
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.NoButton
            onPositionChanged: root.revealControls()
        }

        Item {
            id: progress
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 64
            anchors.rightMargin: 64
            y: 62
            height: 18

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width
                height: progressMouse.containsMouse ? 3 : 2
                radius: height / 2
                color: "#55ffffff"
                Behavior on height { NumberAnimation { duration: 120 } }
            }

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: progress.width * root.progressValue
                height: progressMouse.containsMouse ? 3 : 2
                radius: height / 2
                color: "#ffffff"
                Behavior on height { NumberAnimation { duration: 120 } }
            }

            Rectangle {
                width: progressMouse.containsMouse || progressMouse.pressed ? 10 : 7
                height: width
                radius: width / 2
                color: "white"
                x: Math.max(0, Math.min(progress.width - width, progress.width * root.progressValue - width / 2))
                anchors.verticalCenter: parent.verticalCenter
                Behavior on width { NumberAnimation { duration: 120 } }
            }

            MouseArea {
                id: progressMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                function seekAt(mouseX) { player.seekRatio(Math.max(0, Math.min(1, mouseX / Math.max(1, progress.width)))) }
                onPressed: seekAt(mouse.x)
                onPositionChanged: {
                    root.revealControls()
                    if (pressed) seekAt(mouse.x)
                }
            }
        }

        Text {
            anchors.right: progress.left
            anchors.rightMargin: 12
            anchors.verticalCenter: progress.verticalCenter
            text: root.formatTime(player.position)
            color: "white"
            font.pixelSize: 12
        }

        Text {
            anchors.left: progress.right
            anchors.leftMargin: 12
            anchors.verticalCenter: progress.verticalCenter
            text: root.formatTime(player.duration)
            color: "white"
            font.pixelSize: 12
        }

        Rectangle {
            id: controlPill
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 24
            width: controlsRow.width + 34
            height: 48
            radius: 24
            color: "#3c1d1f24"
            border.color: "#20ffffff"
            border.width: 1

            Rectangle {
                anchors.fill: parent
                radius: parent.radius
                color: "#18ffffff"
                visible: true
            }

            Row {
                id: controlsRow
                anchors.centerIn: parent
                spacing: 7

                IconButton { icon: "prev"; onClicked: player.seekRelative(-10) }
                IconButton { icon: player.paused ? "play" : "pause"; onClicked: player.togglePlay() }
                IconButton { icon: "next"; onClicked: player.seekRelative(10) }
                IconButton { icon: "volume"; onClicked: player.toggleMute(); opacity: player.muted ? 0.45 : 1 }
                Rectangle { width: 92; height: 4; radius: 2; color: "#3a6dff"; anchors.verticalCenter: parent.verticalCenter
                    Rectangle { width: parent.width * player.volume / 100; height: parent.height; radius: parent.radius; color: "white" }
                    MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onPressed: player.setVolume(Math.round(mouse.x / width * 100)); onPositionChanged: if (pressed) player.setVolume(Math.round(mouse.x / width * 100)) }
                }
                Text { text: player.volume + "%"; color: "white"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                IconButton { label: player.speedText; onClicked: player.cycleSpeed() }
                Text { text: root.formatTime(player.position) + " / " + root.formatTime(player.duration); color: "white"; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter }
                IconButton { icon: "audio"; onClicked: player.cycleAudio() }
                IconButton { icon: "subtitle"; onClicked: player.toggleSubtitle() }
                IconButton { label: "原画" }
                IconButton { icon: "quality" }
                IconButton { icon: "fullscreen"; onClicked: player.toggleFullscreen() }
            }
        }
    }

    Shortcut { sequence: "Space"; onActivated: player.togglePlay() }
    Shortcut { sequence: "Left"; onActivated: player.seekRelative(-5) }
    Shortcut { sequence: "Right"; onActivated: player.seekRelative(5) }
    Shortcut { sequence: "Esc"; onActivated: if (root.visibility === Window.FullScreen) root.showNormal() }

    onClosing: player.stop()
}
