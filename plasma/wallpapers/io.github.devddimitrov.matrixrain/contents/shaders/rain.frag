#version 440
// SPDX-License-Identifier: GPL-3.0-or-later
// Part of Konsole Matrix Digital Rain.
//
// Matrix rain cell renderer. The CPU side uploads a tiny state texture
// (one texel per character cell: R = glyph atlas index, G = color level)
// and a single-row atlas of white glyphs; this shader paints every cell at
// native resolution. Level codes: 0 empty, 1..6 fade ramp bright->dark,
// 7 white/contrast head.
//
// Rebuild rain.frag.qsb with scripts/build-shaders.sh after editing.

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec4 ramp0;
    vec4 ramp1;
    vec4 ramp2;
    vec4 ramp3;
    vec4 ramp4;
    vec4 ramp5;
    vec4 headTint;
    vec4 grid;      // x = cols, y = rows, z = atlas glyph count, w = unused
} ubuf;

layout(binding = 1) uniform sampler2D stateTex;
layout(binding = 2) uniform sampler2D atlasTex;

void main() {
    vec2 cellPos = qt_TexCoord0 * ubuf.grid.xy;
    vec2 cellIndex = floor(cellPos);
    vec2 inCell = cellPos - cellIndex;
    vec4 state = texture(stateTex, (cellIndex + vec2(0.5)) / ubuf.grid.xy);
    float level = floor(state.g * 255.0 + 0.5);
    if (level < 0.5) {
        fragColor = vec4(0.0);
        return;
    }
    float glyph = floor(state.r * 255.0 + 0.5);
    vec2 atlasUV = vec2((glyph + inCell.x) / ubuf.grid.z, inCell.y);
    float glyphAlpha = texture(atlasTex, atlasUV).a;
    vec4 tint = level < 1.5 ? ubuf.ramp0
              : level < 2.5 ? ubuf.ramp1
              : level < 3.5 ? ubuf.ramp2
              : level < 4.5 ? ubuf.ramp3
              : level < 5.5 ? ubuf.ramp4
              : level < 6.5 ? ubuf.ramp5
              : ubuf.headTint;
    fragColor = vec4(tint.rgb, 1.0) * glyphAlpha * ubuf.qt_Opacity;
}
