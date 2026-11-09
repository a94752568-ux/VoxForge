"""Themes package for VoxForge Local.

This package contains visual themes for the VoxForge Local application.

Available themes:
- nova_premium: Cyberpunk-inspired professional theme with electric blue accents

Usage:
    from voxforge.themes import NOVA_THEME, apply_nova_theme, NOVA_CLI_Theme
    
    # Apply to Qt application
    apply_nova_theme(app)
    
    # Or set stylesheet directly
    app.setStyleSheet(NOVA_THEME)
    
    # For CLI output
    print(NOVA_CLI_Theme.header("VoxForge Local"))
"""

from __future__ import annotations

from voxforge.themes.nova_premium import (
    NOVA_THEME,
    NOVA_THEME_INFO,
    NOVA_CLI_Theme,
    NOVA_ACCENT_PRIMARY,
    NOVA_ACCENT_SECONDARY,
    NOVA_BG_PRIMARY,
    NOVA_BG_SECONDARY,
    NOVA_BG_TERTIARY,
    NOVA_TEXT_PRIMARY,
    NOVA_TEXT_SECONDARY,
    apply_nova_theme,
    create_nova_palette,
)

__all__ = [
    "NOVA_THEME",
    "NOVA_THEME_INFO",
    "NOVA_CLI_Theme",
    "NOVA_ACCENT_PRIMARY",
    "NOVA_ACCENT_SECONDARY",
    "NOVA_BG_PRIMARY",
    "NOVA_BG_SECONDARY",
    "NOVA_BG_TERTIARY",
    "NOVA_TEXT_PRIMARY",
    "NOVA_TEXT_SECONDARY",
    "apply_nova_theme",
    "create_nova_palette",
]
