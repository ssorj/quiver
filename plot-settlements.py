#!/usr/bin/python
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
import matplotlib.pyplot as plt
import matplotlib.transforms as mtransforms
import numpy as np
import datetime
import sys
import traceback

COLOR_RECEIVER = "green"
COLOR_SENDER = "black"
COLOR_CREDIT = "magenta"
LINE_WIDTH = 0.5

#
# Usage: plot-settlements <directory> <plot-title>
#
def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else 'outfoo'
    title  = sys.argv[2] if len(sys.argv) > 2 else 'Quiver Receiver/Sender Latencies'

    r_filename = "{}/receiver-transfers.csv".format(folder)
    s_filename = "{}/sender-settlement.csv".format(folder)
    c_filename = "{}/sender-transfers.csv".format(folder)

    basename = title.replace(" ", "_")
    basename = basename.replace("/", "_")
    w_filebase = "{}/{}".format(folder, basename)

    v_c = list() # send credit as message is sent (before link advance)
    v_r = list() # receive latency
    v_s = list() # send latency
    v_x = list() # send time relative to t0
    v_m = list() # message in flight for corresponding v_x time

    t0 = 0 # relative base time in unix microseconds

    # x-axis, sender latency, message-in-flight
    with open(r_filename, 'r') as r_in:
        m = 0
        t0_processed = False
        line = r_in.readline()
        while line:
            r_id, r_send, r_recv = line.split(',')
            v_r.append( int(r_recv) - int(r_send) )
            if not t0_processed:
                t0 = int(r_send)
                t0_processed = True
            v_x.append( int(r_send) - t0)
            v_m.append( m )
            m += 1
            line = r_in.readline()

    # compute sender latency array
    with open(s_filename, 'r') as s_in:
        s_in.readline() # read/discard column headings
        line = s_in.readline()
        while line:
            s_id, s_stl = line.split(',')
            v_s.append( int(s_stl) )
            line = s_in.readline()

    # compute credit array
    with open(c_filename, 'r') as c_in:
        xi = 0 # index into v_x
        line = c_in.readline()
        while line:
            while line[0] == 'S' or line[0] == 's':
                line = c_in.readline()
                if not line:
                    break
            if not line:
                break
            id, s_time, credit = _parse_send(line.strip())
            s_time -= t0
            if s_time == v_x[xi] :
                v_c.append(credit)
            else:
                print("FAIL: credit axis. s_time={}, v_x[si]={}".format(s_time, v_x[xi]))
            line = c_in.readline()
            xi += 1

    # common stats
    n_msgs = len(v_x)
    s_per_sec = int((1000000.0 * float(n_msgs)) / float(v_x[-1]))
    title = title + "({} msgs, send@ {} msg/S, sendCredit {})".format(n_msgs, s_per_sec, v_c[0])
    # plot results
    plot_latencies(v_c, v_r, v_s, v_x, v_m, folder, title, w_filebase, t0, credit_values=False)
    plot_latencies(v_c, v_r, v_s, v_x, v_m, folder, title, w_filebase, t0, credit_values=True)

    plot_latencies_lines(v_c, v_r, v_s, v_x, v_m, folder, title, w_filebase, t0, vertical_lines=True)


def plot_latencies(_v_c, _v_r, _v_s, _v_x, _v_m, folder, title, w_filebase, t0, credit_values=False):

    file_suffix = "-credit" if credit_values else ""

    # adjust credit array to expose zero credit times with a horizontal floor
    v_c, v_r, v_s, v_x, v_m, x_ic = expose_zero_credit(_v_c, _v_r, _v_s, _v_x, _v_m, credit_values, False)

    fig, ax1 = plt.subplots()
    fig.set_size_inches(20, 6)

    if credit_values:
        ax2 = ax1.twinx()

    # plot the lines
    lr = ax1.plot(v_x, v_r, label="tranfer latency", color=COLOR_RECEIVER, linewidth=LINE_WIDTH)
    ls = ax1.plot(v_x, v_s, label="settlement latency", color=COLOR_SENDER, linewidth=LINE_WIDTH)
    if credit_values:
        # credit line
        lc = ax2.plot(v_x, v_c, label="credit", color=COLOR_CREDIT, linewidth=LINE_WIDTH)

        # compute in-flight stats
        v_2r = list()
        v_2s = list()
        inflight = In_flight(_v_x, _v_r, _v_s)
        for x in _v_x:
            tnr, tns = inflight.query(x)
            v_2r.append(tnr)
            v_2s.append(tns)

        # create stretched arrays to let the in-flight numbers drain down
        sv_x = list(_v_x)
        next_time = inflight.next_event_time()
        while next_time > 0:
            tnr, tns = inflight.query(next_time)
            sv_x.append(next_time)
            v_2r.append(tnr)
            v_2s.append(tns)
            next_time = inflight.next_event_time()
        # in-flight lines
        l2r = ax2.plot(sv_x, v_2r, label="transfer in flight", color=COLOR_RECEIVER, linewidth=LINE_WIDTH, ls='dotted')
        l2s = ax2.plot(sv_x, v_2s, label="settlement in flight", color=COLOR_SENDER, linewidth=LINE_WIDTH, ls='dotted')

        # credit axis and legend
        lns = lc + l2r + l2s
        labels = [l.get_label() for l in lns]
        ax2.legend(lns, labels, loc="upper right")
    else:
        lc = ax1.plot(v_x, v_c, label="credit T/F", color=COLOR_CREDIT, linewidth=LINE_WIDTH)

    # latency axis and legend
    lns = ls + lr if credit_values else ls + lr + lc
    labels = [l.get_label() for l in lns]
    ax1.legend(lns, labels, loc="upper left")

    ax1.set_ylim(bottom=0)

    ax1.set_xlabel('message transmit TOD (relative uS)')
    ax1.set_ylabel('latency (uS)')

    if credit_values:
        ax2.set_yscale('log')
        ax2.set_ylabel('sender credit; elements in flight', color='black')

    plt.title(title)

    plt.ioff()  # disable interactiveness

    #plt.savefig("{}{}.png".format(w_filebase, file_suffix), bbox_inches='tight')
    plt.savefig("{}{}.pdf".format(w_filebase, file_suffix), bbox_inches='tight')


def plot_latencies_lines(_v_c, _v_r, _v_s, _v_x, _v_m, folder, title, w_filebase, t0, vertical_lines=False):

    file_suffix = "-vlines" if vertical_lines else "-hlines"

    fig, ax1 = plt.subplots()
    fig.set_size_inches(20, 20)
    trans_offset = mtransforms.offset_copy(ax1.transData, fig=fig, x=0.05, y=-0.04, units='inches')

    first = True
    # plot the lines
    if vertical_lines:
        for i in range(len(_v_x)):
            x1s = _v_x[i]
            x1e = x1s
            y1s = x1s
            y1e = x1s  + _v_r[i]
            if first:
                lr = ax1.plot((x1s, x1e), (y1s, y1e), label="transfer latency", color=COLOR_RECEIVER) #, linewidth=LINE_WIDTH)
            else:
                ax1.plot((x1s, x1e), (y1s, y1e), color=COLOR_RECEIVER, linewidth=LINE_WIDTH)
            x2s = x1s
            x2e = x1s
            y2s = y1e
            y2e = y1e + _v_s[i] - _v_r[i]
            if first:
                ls = ax1.plot((x2s, x2e), (y2s, y2e), label="settlement latency", color=COLOR_SENDER) #v)
            else:
                ax1.plot((x2s, x2e), (y2s, y2e), color=COLOR_SENDER, linewidth=LINE_WIDTH)
            first = False
        # identify occasional message numbers
        tickwidth = _v_x[-1]/200.0
        def plot_tick(i):
            plt.plot((_v_x[i], _v_x[i] + tickwidth), (_v_x[i], _v_x[i]), color='black', linewidth=LINE_WIDTH)
            plt.plot((_v_x[i], _v_x[i]), (_v_x[i], _v_x[i] - tickwidth), color='black', linewidth=LINE_WIDTH)
            plt.text(_v_x[i], _v_x[i] - tickwidth, str(i + 1), transform=trans_offset)
        for i in range(200, len(_v_x), 200):
            plot_tick(i - 1)
        plot_tick(len(_v_x) - 1)
    else:
        pass # not maintained...

    # adjust credit array to expose zero credit times with a horizontal floor
    v_c, v_r, v_s, v_x, v_m, v_ic = expose_zero_credit(_v_c, _v_r, _v_s, _v_x, _v_m, False, True)

    # plot the credit
    lc = ax1.plot(v_x, v_c, label="credit T/F", color=COLOR_CREDIT, linewidth=LINE_WIDTH)
    lns = ls + lr + lc
    labels = [l.get_label() for l in lns]
    ax1.legend(lns, labels, loc="upper left")

    ax1.set_ylim(bottom=0)

    if vertical_lines:
        ax1.set_xlabel('message transmit TOD (relative uS)')
        ax1.set_ylabel('transfer/settlement completion time (relative uS)')
    else:
        pass

    ax1.grid()

    ax2 = ax1.twinx()
    ax2.set_yscale('log')

    # compute in-flight stats
    v_2r = list()
    v_2s = list()
    inflight = In_flight(_v_x, _v_r, _v_s)
    for x in _v_x:
        tnr, tns = inflight.query(x)
        v_2r.append(tnr)
        v_2s.append(tns)

    # create stretched arrays to let the in-flight numbers drain down
    sv_x = list(_v_x)
    next_time = inflight.next_event_time()
    while next_time > 0:
        tnr, tns = inflight.query(next_time)
        sv_x.append(next_time)
        v_2r.append(tnr)
        v_2s.append(tns)
        next_time = inflight.next_event_time()
    # in-flight lines
    l2r = ax2.plot(sv_x, v_2r, label="transfer in flight", color=COLOR_RECEIVER, linewidth=LINE_WIDTH, ls='dotted')
    l2s = ax2.plot(sv_x, v_2s, label="settlement in flight", color=COLOR_SENDER, linewidth=LINE_WIDTH, ls='dotted')
    # credit axis and legend
    ax2.set_ylim(top=((max(v_2s)**2)))
    lns = l2s + l2r
    labels = [l.get_label() for l in lns]
    ax2.legend(lns, labels, loc="upper right")

    plt.title(title)

    #plt.savefig("{}{}.png".format(w_filebase, file_suffix), bbox_inches='tight')
    plt.savefig("{}{}.pdf".format(w_filebase, file_suffix), bbox_inches='tight')


    # write the plot data as csv
    plot_filename = "{}/plot-data{}.csv".format(folder, file_suffix)
    with open(plot_filename, 'w') as pf:
        pf.write("Point, MsgID, Time, Time uS, Trel uS, credit, r-latency, s-latency, msg-in-flight, settlement-in-flight\n")
        for i in range(len(v_x)):
            timerawus = t0 + v_x[i]
            timeraw = float(timerawus) / 1000000.0
            timeobj = datetime.datetime.fromtimestamp(timeraw)
            tod = datetime.datetime.strftime(timeobj, "%Y-%m-%d %H:%M:%S.%f")
            pf.write("{}, {}, {}, {}, {}, {}, {}, {}, {}, {}\n".format(
                i, v_m[i], tod, timerawus, v_x[i], v_ic[i], v_r[i], v_s[i], v_2r[i], v_2s[i]))

def _parse_send(line):
    _message_id, _send_time, _credit = line.split(",", 2)

    return _message_id, int(_send_time), int(_credit)


def expose_zero_credit(c, r, s, x, m, full_values, use_x):
    """
    Given plot values, insert extra points to highlight zero credit
    An insertion should produce

        input                      output
        1   1211   2857  9288 1    1   1211   2857  9288 1
                                   1   1063   2448  9698 1
        50  1063   2448  9698 2    50  1063   2448  9698 2

    This cheats the lateceny lines by one uS. The credit line is kept
    flat until the next transition.
    :param c: credit
    :param r: receive latency
    :param s: send latency
    :param x: x axis points
    :param m: message ID
    :param full_values: propagate real value vs. true/false
    :param use_x: hint for choosing settlement value or x TOD for scaling credit line
    :return: adjusted arrays c,r,s,x
    """
    outc = list()
    outr = list()
    outs = list()
    outx = list()
    outm = list()
    outicredit = list()

    # when not propagating full credit values use these to indicate on/off
    mymax = max(x) if use_x else max(s)
    CREDIT_TRUE = 0.04 * mymax
    CREDIT_FALSE = 0.01 * mymax

    # copy first entry
    outc.append(c[0] if full_values else CREDIT_TRUE)
    outr.append(r[0])
    outs.append(s[0])
    outx.append(x[0])
    outm.append(m[0])
    outicredit.append(c[0])

    lastc = c[0]
    for inI in range(1, len(x)):
        if lastc == 1:
            outc.append(1 if full_values else CREDIT_FALSE)
            outr.append(r[inI])
            outs.append(s[inI])
            outx.append(x[inI] - 1)
            outm.append(m[inI - 1])
            outicredit.append(c[inI])
        if c[inI] == 1:
            outc.append(1 if full_values else CREDIT_FALSE)
        else:
            outc.append(c[inI] if full_values else CREDIT_TRUE)
        outr.append(r[inI])
        outs.append(s[inI])
        outx.append(x[inI])
        outm.append(m[inI])
        outicredit.append(c[inI])
        lastc = c[inI]

    return outc, outr, outs, outx, outm, outicredit

class In_flight:
    """
    This class tracks now many messages are in flight.
    It is inited with three arrays:
     * X sample times relative to test start. Time message was transmitted
     * R receiver latency. Receiver accepts message at X + R
     * S sender latency. Sender settles message at X + S
    Compute messages-to-receiver and settlements-to-sender in-flight timeline.
    Later the counts may be queried.
    Note that the queries are in strictly time-ascending order.
    """
    @staticmethod
    def custom_sort(event):
        return event[1]

    def __init__(self, x, r, s):
        # event enum
        self.EVENT_TX = 1  # message is transmitted: msg-to-rcvr in flight
        self.EVENT_RX = 2  # message accepted: msg-to-rcvr done, settle-to-sndr in flight
        self.EVENT_DN = 3  # message settled: settle-to-sndr done
        self.events = []
        for i in range(len(x)):
            self.events.append((self.EVENT_TX, x[i]))
            self.events.append((self.EVENT_RX, x[i] + r[i]))
            self.events.append((self.EVENT_DN, x[i] + s[i]))
        self.events.sort(key=In_flight.custom_sort)
        self.n_r = 0    # msg-to-rcvr in flight
        self.n_s = 0    # settle-to-sndr in flight

    def query(self, t):
        while len(self.events) > 0 and t >= self.events[0][1]:
            ev, _t = self.events.pop(0)
            if ev == self.EVENT_TX:
                self.n_r += 1
            elif ev == self.EVENT_RX:
                self.n_r -= 1
                self.n_s += 1
            elif ev == self.EVENT_DN:
                self.n_s -= 1
            else:
                print("Alas, Babylon")
        return self.n_r, self.n_s

    def next_event_time(self):
        return self.events[0][1] if len(self.events) > 0 else 0

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except:
        traceback.print_exc(file=sys.stdout)
        pass
