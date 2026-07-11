"""Battery monitor (host-simulated; maps to XIAO ADC on real HW)."""


class BatteryMonitor:
    def __init__(self, full_mv=4200, empty_mv=3300, simulation=True):
        self.full_mv = full_mv
        self.empty_mv = empty_mv
        self.simulation = simulation
        self._sim_mv = 3950

    def read_mv(self) -> int:
        if self.simulation:
            # slowly drain to show low-power behavior
            self._sim_mv = max(self.empty_mv, self._sim_mv - 1)
            return int(self._sim_mv)
        # real: analogRead(PIN_VBAT) * divider * ref
        raise NotImplementedError("wire ADC on device")

    def percent(self, mv: int | None = None) -> int:
        mv = mv if mv is not None else self.read_mv()
        pct = (mv - self.empty_mv) / (self.full_mv - self.empty_mv) * 100
        return max(0, min(100, int(pct)))

    def is_low(self, mv: int | None = None) -> bool:
        return self.percent(mv) <= 15
