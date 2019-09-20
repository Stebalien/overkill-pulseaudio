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


SINK_MATCHER = re.compile(r"^Event '(new|remove|change)' on sink #([0-9]+)$")
SOURCE_MATCHER = re.compile(r"^Event '(new|remove|change)' on source #([0-9]+)$")

def _process_sinks(line):
    match = SINK_MATCHER.match(line)
    if not match:
        return {}
    event, sink = match.groups()
    updates = _get_sink_updates()
    sink_update = _get_updates_for_sink(sink)
    if sink_update is not None:
        updates.update(sink_update)
    return updates

def _process_sources(line):
    match = SOURCE_MATCHER.match(line)
    if not match:
        return {}
    event, source = match.groups()
    updates = _get_source_updates()
    source_update = _get_updates_for_source(source)
    if source_update is not None:
        updates.update(source_update)
    return updates

def _get_updates_for_source(source):
    try:
        volume = int(subprocess.check_output(
            ["ponymix", "--source", "-d", source, "get-volume"]
        ).strip())
        muted = subprocess.call(["ponymix", "--source", "-d", source, "is-muted"]) == 0
    except subprocess.CalledProcessError:
        return None

    updates = {
        "mic_volume:"+source: volume,
        "mic_muted:"+source: muted
    }

    # FIXME: Don't assume only one sink
    updates["mic_volume"] = volume
    updates["mic_muted"] = muted
    return updates

def _get_updates_for_sink(sink):
    try:
        volume = int(subprocess.check_output(
            ["ponymix", "--sink", "-d", sink, "get-volume"]
        ).strip())
        muted = subprocess.call(["ponymix", "--sink", "-d", sink, "is-muted"]) == 0
    except subprocess.CalledProcessError:
        return None

    updates = {
        "volume:"+sink: volume,
        "muted:"+sink: muted
    }

    # FIXME: Don't assume only one sink
    updates["volume"] = volume
    updates["muted"] = muted
    return updates

def _get_sink_updates():
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

def _get_source_updates():
    recording_proc = subprocess.Popen(["pactl", "list", "short", "sources"], stdout=subprocess.PIPE)
    updates = {}
    sources = set()
    updates = {}
    for line in recording_proc.stdout:
        pieces = line[:-1].decode('utf-8').split('\t')
        updates["recording:"+pieces[0]] = (pieces[4] == "RUNNING")
        sources.add(pieces[0])
    updates["recording"] = any(updates.values())
    updates["sources"] = sources
    recording_proc.wait(1) # Close process.
    return updates


class PulseaudioSource(Source, PipeSink):
    cmd = ["pactl", "subscribe"]
    restart = True
    def __init__(self):
        super().__init__()

    def is_publishing(self, subscription):
        try:
            if subscription in ("mic_volume", "mic_muted", "volume", "muted", "sinks", "playing", "sources", "recording"):
                return True
            if not (hasattr(subscription, "__getitem__") and len(subscription) == 2):
                return False
            if subscription[0] in ("volume", "muted", "playing"):
                return subscription[1] in self.get('sinks', ())
            if subscription[0] in ("mic_volume", "mic_muted", "recording"):
                return subscription[1] in self.get('sources', ())
            return False
        except:
            return False

    def handle_input(self, line):
        updates = {}
        updates.update(_process_sinks(line))
        updates.update(_process_sources(line))
        if updates:
            self.push_updates(updates)

    def on_start(self):
        self.published_data.update(self._get_all())

    def _get_all(self):
        updates = {}
        updates.update(_get_sink_updates())
        updates.update(_get_source_updates())
        for s in updates["sinks"]:
            update = _get_updates_for_sink(s)
            updates.update()
            if update is not None:
                updates.update(update)
        for s in updates["sources"]:
            update = _get_updates_for_source(s)
            if update is not None:
                updates.update(update)
        return updates
