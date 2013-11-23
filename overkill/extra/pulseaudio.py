##
#    This file is part of Overkill-pulseaudio.
#
#    Overkill-pulseaudio is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Overkill-pulseaudio is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Overkill-pulseaudio.  If not, see <http://www.gnu.org/licenses/>.
##

from overkill.sinks import PipeSink
from overkill.sources import Source
import subprocess
import re

class PulseaudioSource(Source, PipeSink):
    matcher = re.compile(r"^Event '(new|remove|change)' on sink #([0-9]+)$")
    cmd = ["pactl", "subscribe"]
    restart = True
    def __init__(self):
        super().__init__()

    def is_publishing(self, subscription):
        try:
            if subscription in ("volume", "muted", "sinks", "playing"):
                return True
            if not (hasattr(subscription, "__getitem__") and len(subscription) == 2):
                return False
            if subscription[0] in ("volume", "muted", "playing"):
                dev = subscription[1]
            else:
                return False
            return dev in self.get('sinks', ())
        except:
            return False

    def handle_input(self, line):
        match = self.matcher.match(line)
        if not match:
            return
        event, sink = match.groups()
        updates = self._get_sink_updates()
        updates.update(self._get_updates_for_sink(sink))

        self.push_updates(updates)


    def on_start(self):
        self.published_data.update(self._get_all())

    def _get_sink_updates(self):
        playing_proc = subprocess.Popen(["pactl", "list", "short", "sinks"], stdout=subprocess.PIPE)
        updates = {}
        sinks = set()
        updates = {}
        for line in playing_proc.stdout:
            pieces = line[:-1].decode('utf-8').split('\t')
            updates["playing:"+pieces[0]] = (pieces[4] == "RUNNING")
            sinks.add(pieces[0])
        updates["playing"] = any(updates.values())
        updates["sinks"] = sinks
        playing_proc.wait(1) # Close process.
        return updates

    def _get_all(self):
        updates = self._get_sink_updates()
        updates.update(*(self._get_updates_for_sink(s) for s in updates["sinks"]))
        return updates

    def _get_updates_for_sink(self, sink):
        volume = int(subprocess.check_output(
            ["ponymix", "--sink", "-d", sink, "get-volume"]
        ).strip())
        muted = subprocess.call(["ponymix", "--sink", "-d", sink, "is-muted"]) == 0
        updates = {
            "volume:"+sink: volume,
            "muted:"+sink: muted
        }

        # FIXME: Don't assume only one sink
        updates["volume"] = volume
        updates["muted"] = muted
        return updates


