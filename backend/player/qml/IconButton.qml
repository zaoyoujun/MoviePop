import QtQuick

Item {
    id: root
    width: label.length > 0 ? 50 : 38
    height: 38

    property string icon: "play"
    property string label: ""
    property bool checked: false
    signal clicked()

    opacity: enabled ? 1 : 0.38
    scale: mouse.pressed ? 0.92 : (mouse.containsMouse ? 1.08 : 1)

    Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
    Behavior on opacity { NumberAnimation { duration: 160 } }

    Canvas {
        id: canvas
        anchors.fill: parent
        opacity: mouse.containsMouse ? 1 : 0.82

        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            ctx.clearRect(0, 0, width, height)
            ctx.strokeStyle = "white"
            ctx.fillStyle = "white"
            ctx.lineWidth = 1.5
            ctx.lineCap = "round"
            ctx.lineJoin = "round"

            if (root.label.length > 0) {
                ctx.font = "12px Segoe UI"
                ctx.textAlign = "center"
                ctx.textBaseline = "middle"
                ctx.fillText(root.label, width / 2, height / 2 + 0.5)
                return
            }

            const cx = width / 2
            const cy = height / 2

            function line(points) {
                ctx.beginPath()
                ctx.moveTo(points[0][0], points[0][1])
                for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1])
                ctx.stroke()
            }

            function poly(points, fill) {
                ctx.beginPath()
                ctx.moveTo(points[0][0], points[0][1])
                for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1])
                ctx.closePath()
                fill ? ctx.fill() : ctx.stroke()
            }

            if (icon === "play") {
                poly([[cx - 5, cy - 8], [cx - 5, cy + 8], [cx + 9, cy]], true)
            } else if (icon === "pause") {
                line([[cx - 5, cy - 8], [cx - 5, cy + 8]])
                line([[cx + 5, cy - 8], [cx + 5, cy + 8]])
            } else if (icon === "prev") {
                line([[cx - 8, cy - 8], [cx - 8, cy + 8]])
                poly([[cx + 8, cy - 8], [cx - 4, cy], [cx + 8, cy + 8]], false)
            } else if (icon === "next") {
                line([[cx + 8, cy - 8], [cx + 8, cy + 8]])
                poly([[cx - 8, cy - 8], [cx + 4, cy], [cx - 8, cy + 8]], false)
            } else if (icon === "volume") {
                poly([[cx - 11, cy - 4], [cx - 6, cy - 4], [cx + 1, cy - 10], [cx + 1, cy + 10], [cx - 6, cy + 4], [cx - 11, cy + 4]], false)
                ctx.beginPath(); ctx.arc(cx + 6, cy, 5, -0.7, 0.7); ctx.stroke()
                ctx.beginPath(); ctx.arc(cx + 7, cy, 9, -0.7, 0.7); ctx.stroke()
            } else if (icon === "subtitle") {
                ctx.strokeRect(cx - 10, cy - 7, 20, 14)
                line([[cx - 6, cy + 3], [cx - 1, cy + 3]])
                line([[cx + 3, cy + 3], [cx + 7, cy + 3]])
            } else if (icon === "audio") {
                for (let i = 0; i < 4; i++) line([[cx - 9 + i * 6, cy + 6], [cx - 9 + i * 6, cy - 6 + i % 2 * 4]])
            } else if (icon === "fullscreen") {
                line([[cx - 10, cy - 4], [cx - 10, cy - 10], [cx - 4, cy - 10]])
                line([[cx + 4, cy - 10], [cx + 10, cy - 10], [cx + 10, cy - 4]])
                line([[cx - 10, cy + 4], [cx - 10, cy + 10], [cx - 4, cy + 10]])
                line([[cx + 4, cy + 10], [cx + 10, cy + 10], [cx + 10, cy + 4]])
            } else if (icon === "quality") {
                line([[cx - 11, cy - 5], [cx - 2, cy - 5]])
                line([[cx + 5, cy - 5], [cx + 11, cy - 5]])
                ctx.beginPath(); ctx.arc(cx + 1.5, cy - 5, 3.5, 0, Math.PI * 2); ctx.stroke()
                line([[cx - 11, cy + 6], [cx - 5, cy + 6]])
                line([[cx + 2, cy + 6], [cx + 11, cy + 6]])
                ctx.beginPath(); ctx.arc(cx - 1.5, cy + 6, 3.5, 0, Math.PI * 2); ctx.stroke()
            }
        }

        Connections {
            target: mouse
            function onContainsMouseChanged() { canvas.requestPaint() }
            function onPressedChanged() { canvas.requestPaint() }
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
