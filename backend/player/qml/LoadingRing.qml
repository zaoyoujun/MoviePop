import QtQuick

Item {
    id: root
    width: 72
    height: 72

    property int percent: 0

    Canvas {
        id: canvas
        anchors.fill: parent
        rotation: 0

        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            ctx.clearRect(0, 0, width, height)
            const cx = width / 2
            const cy = height / 2
            const r = Math.min(width, height) / 2 - 8

            ctx.lineWidth = 2
            ctx.lineCap = "round"
            ctx.strokeStyle = "rgba(255,255,255,0.22)"
            ctx.beginPath()
            ctx.arc(cx, cy, r, 0, Math.PI * 2)
            ctx.stroke()

            ctx.strokeStyle = "white"
            ctx.beginPath()
            const end = -Math.PI / 2 + Math.PI * 2 * Math.max(0.08, root.percent / 100)
            ctx.arc(cx, cy, r, -Math.PI / 2, end)
            ctx.stroke()

            ctx.fillStyle = "white"
            ctx.font = "600 12px Segoe UI"
            ctx.textAlign = "center"
            ctx.textBaseline = "middle"
            ctx.fillText(root.percent + "%", cx, cy)
        }

        NumberAnimation on rotation {
            running: root.visible
            from: 0
            to: 360
            loops: Animation.Infinite
            duration: 1100
        }
    }

    onPercentChanged: canvas.requestPaint()
}
