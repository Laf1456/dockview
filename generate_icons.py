#!/usr/bin/env python3
"""Generate simple SVG-based PNG icons for DockView PWA."""
import os

# Inline SVG → PNG using cairosvg or fallback to a simple script
svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="96" fill="#0d0d14"/>
  <text x="256" y="340" font-size="280" text-anchor="middle" fill="#7c6cf0">⬡</text>
</svg>"""

os.makedirs("app/static/icons", exist_ok=True)

try:
    import cairosvg
    for size in [192, 512]:
        cairosvg.svg2png(bytestring=svg.encode(), write_to=f"app/static/icons/icon-{size}.png", output_width=size, output_height=size)
    print("Icons generated with cairosvg")
except ImportError:
    # Fallback: write the SVG directly as placeholder
    for size in [192, 512]:
        with open(f"app/static/icons/icon-{size}.svg", "w") as f:
            f.write(svg)
    print("SVG icons written (install cairosvg for PNG)")
