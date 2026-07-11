from __future__ import annotations

from dataclasses import dataclass

from renderer.dtypes import PanelAssignment, PlotCommand


@dataclass(slots=True)
class _Panel:
    """
    Internal representation of one mplfinance lower panel.

    A panel can host up to two independent indicator scales:
    one on the primary y-axis and one on the secondary y-axis.
    Indicators that need both axes mark the panel as exclusive.

    Attributes
    ----------
    number:
        mplfinance panel number. Panel 0 is the main price panel, so
        lower indicator panels start at 1.

    primary:
        Indicator key assigned to the primary y-axis, or None if the
        primary axis is still available.

    secondary:
        Indicator key assigned to the secondary y-axis, or None if the
        secondary axis is still available.

    exclusive:
        True when this panel is reserved for a single indicator that
        consumes the full panel, usually because it uses both y-axes
        internally. Example: MACD line/signal on one axis and histogram
        on the other.

    is_volume:
        True when this panel is the dedicated volume panel. Volume is
        always assigned to panel 1, but compatible indicators may still
        share its secondary y-axis.
    """

    number: int
    primary: str | None = None
    secondary: str | None = None
    exclusive: bool = False
    is_volume: bool = False


class PanelAllocator:
    def __init__(self) -> None:
        self.panels: list[_Panel] = list()
        self.assignments: dict[str, PanelAssignment] = dict()
        self.next_panel = 1

    def reserve_volume_panel(self) -> None:
        panel = _Panel(
            number=1,
            primary="volume",
            is_volume=True,
        )

        self.panels.append(panel)
        self.assignments["volume"] = PanelAssignment(panel=1, secondary_y=False)
        self.next_panel += 1

    def assign_volume_overlay(self, key: str) -> None:
        self.assignments[key] = PanelAssignment(panel=1, secondary_y=False)

    def assign_price_overlay(self, key: str) -> None:
        self.assignments[key] = PanelAssignment(panel=0, secondary_y=False)

    def assign_exclusive(self, key: str) -> None:
        panel = _Panel(
            number=self.next_panel,
            primary=key,
            secondary=key,
            exclusive=True,
        )
        self.panels.append(panel)
        self.assignments[key] = PanelAssignment(
            panel=panel.number,
            secondary_y=None,
        )
        self.next_panel += 1
        self.slots = 2

    def assign_shareable(
        self,
        key: str,
        *,
        allow_volume_panel: bool = True,
        preferred_axis: str = "any",
    ) -> None:
        for panel in self.panels:
            if panel.exclusive:
                continue

            if panel.is_volume and not allow_volume_panel:
                continue

            if preferred_axis in ("primary", "any") and panel.primary is None:
                panel.primary = key
                self.assignments[key] = PanelAssignment(
                    panel=panel.number,
                    secondary_y=False,
                )
                return

            if preferred_axis in ("secondary", "any") and panel.secondary is None:
                panel.secondary = key
                self.assignments[key] = PanelAssignment(
                    panel=panel.number,
                    secondary_y=True,
                )
                return

        panel = _Panel(
            number=self.next_panel,
            primary=key,
        )
        self.panels.append(panel)
        self.assignments[key] = PanelAssignment(
            panel=panel.number,
            secondary_y=False,
        )
        self.next_panel += 1


def allocate_indicator_panels(cmd: PlotCommand) -> dict[str, PanelAssignment]:
    allocator = PanelAllocator()

    if cmd.volume:
        allocator.reserve_volume_panel()

    if cmd.vol_sma:
        if cmd.volume:
            allocator.assign_volume_overlay("vol_sma")
        else:
            allocator.assign_shareable("vol_sma")

    if cmd.rs:
        allocator.assign_shareable("rs")

    if cmd.mansfield_rs:
        allocator.assign_shareable("m_rs")

    for plugin_key, plugin_config in cmd.plugins.items():
        assignment_key = f"plugin:{plugin_key}"
        panel_config = plugin_config.get("panel", dict())

        if isinstance(panel_config, str):
            panel_config = dict(kind=panel_config)

        kind = str(panel_config.get("kind", "lower")).lower()

        if kind in ("price", "main", "overlay"):
            allocator.assign_price_overlay(assignment_key)
            continue

        axes = int(panel_config.get("axes", panel_config.get("y_axes", 1)))
        share = bool(panel_config.get("share", axes == 1))
        preferred_axis = str(panel_config.get("preferred_axis", "any")).lower()
        allow_volume_panel = bool(panel_config.get("allow_volume_panel", True))

        if axes >= 2 or not share:
            allocator.assign_exclusive(assignment_key)
            continue

        allocator.assign_shareable(
            assignment_key,
            allow_volume_panel=allow_volume_panel,
            preferred_axis=preferred_axis,
        )

    return allocator.assignments
