/*
    SPDX-License-Identifier: GPL-3.0-or-later
    Part of Konsole Matrix Digital Rain.

    Minimal configuration form. The full workflow (live preview, exact hue
    capture, history, undo) is provided by the matrix-lock command.
*/

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.FormLayout {
    id: root
    twinFormLayouts: parentLayout
    property alias formLayout: root

    property alias cfg_FixedColor: fixedColorField.text
    property alias cfg_BackgroundColor: backgroundField.text
    property alias cfg_ColorCycle: colorCycleBox.checked
    property alias cfg_CyclePeriod: cyclePeriodBox.value
    property alias cfg_Speed: speedBox.value
    property alias cfg_Density: densityBox.value
    property alias cfg_WhiteHeadRate: headsBox.value
    property alias cfg_FpsCap: fpsBox.value
    property alias cfg_GlyphSize: glyphBox.value
    property alias cfg_ReducedMotion: reducedBox.checked

    // Entries not shown in this form still need declared cfg_ properties.
    property double cfg_CyclePhase
    property bool cfg_CycleDirectionReverse
    property double cfg_CycleEpoch
    property int cfg_TrailMin
    property int cfg_TrailMax
    property int cfg_FadeLevels
    property double cfg_MutationRate
    property bool cfg_Flashers
    property bool cfg_Asynchronous
    property double cfg_RenderScale
    property string cfg_RenderMode

    QQC2.TextField {
        id: fixedColorField
        Kirigami.FormData.label: "Rain color (#rrggbb):"
        validator: RegularExpressionValidator { regularExpression: /#[0-9a-fA-F]{6}/ }
    }

    QQC2.TextField {
        id: backgroundField
        Kirigami.FormData.label: "Background (#rrggbb):"
        validator: RegularExpressionValidator { regularExpression: /#[0-9a-fA-F]{6}/ }
    }

    QQC2.CheckBox {
        id: colorCycleBox
        Kirigami.FormData.label: "Hue cycling:"
        text: "Cycle the rain color automatically"
    }

    QQC2.SpinBox {
        id: cyclePeriodBox
        Kirigami.FormData.label: "Cycle period (s):"
        from: 2; to: 3600
    }

    QQC2.SpinBox {
        id: speedBox
        Kirigami.FormData.label: "Speed:"
        from: 1; to: 100
    }

    QQC2.SpinBox {
        id: densityBox
        Kirigami.FormData.label: "Density:"
        from: 1; to: 100
    }

    QQC2.SpinBox {
        id: headsBox
        Kirigami.FormData.label: "White heads (%):"
        from: 0; to: 100
    }

    QQC2.SpinBox {
        id: fpsBox
        Kirigami.FormData.label: "FPS cap:"
        from: 1; to: 60
    }

    QQC2.SpinBox {
        id: glyphBox
        Kirigami.FormData.label: "Glyph size (px):"
        from: 10; to: 72
    }

    QQC2.CheckBox {
        id: reducedBox
        Kirigami.FormData.label: "Reduced motion:"
        text: "Disable cycling, flashes, and mutation"
    }

    QQC2.Label {
        Kirigami.FormData.isSection: true
        text: "Tip: use the matrix-lock command for live preview, exact hue capture, presets, and undo."
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
}
