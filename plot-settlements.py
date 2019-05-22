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
from matplotlib.collections import EventCollection
import numpy as np
import sys
import traceback

#
# Usage: plot-settlements <directory> <plot-title>
COLOR_RECEIVER = "green"
COLOR_SENDER = "black"
COLOR_CREDIT = "magenta"
LINE_WIDTH = 0.5

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

    # compute receiver latency and x-axis arrays
    with open(r_filename, 'r') as r_in:
        t0 = 0
        t0_processed = False
        line = r_in.readline()
        while line:
            r_id, r_send, r_recv = line.split(',')
            v_r.append( int(r_recv) - int(r_send) )
            if not t0_processed:
                t0 = int(r_send)
                t0_processed = True
            v_x.append( int(r_send) - t0)
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
    title = title + "({} messages, send rate {} messages/S)".format(n_msgs, s_per_sec)
    # plot results
    plot_latencies(v_c, v_r, v_s, v_x, folder, title, w_filebase, credit_values=False)
    plot_latencies(v_c, v_r, v_s, v_x, folder, title, w_filebase, credit_values=True)

    #plot_latencies_lines(v_c, v_r, v_s, v_x, folder, title, w_filebase, vertical_lines=False)
    plot_latencies_lines(v_c, v_r, v_s, v_x, folder, title, w_filebase, vertical_lines=True)


def plot_latencies(_v_c, _v_r, _v_s, _v_x, folder, title, w_filebase, credit_values=False):

    file_suffix = "-credit" if credit_values else ""

    # adjust credit array to expose zero credit times with a horizontal floor
    v_c, v_r, v_s, v_x = expose_zero_credit(_v_c, _v_r, _v_s, _v_x, credit_values, False)

    # write the plot data as csv
    plot_filename = "{}/plot-data{}.csv".format(folder, file_suffix)
    with open(plot_filename, 'w') as pf:
        pf.write("T uS, credit, r-latency, s-latency\n")
        for i in range(len(v_x)):
            pf.write("{}, {}, {}, {}\n".format(v_x[i], v_c[i], v_r[i], v_s[i]))

    fig, ax1 = plt.subplots()
    fig.set_size_inches(20, 6)

    if credit_values:
        ax2 = ax1.twinx()

    # plot the lines
    lr = ax1.plot(v_x, v_r, label="receiver latency", color=COLOR_RECEIVER, linewidth=LINE_WIDTH)
    ls = ax1.plot(v_x, v_s, label="sender latency", color=COLOR_SENDER, linewidth=LINE_WIDTH)
    if credit_values:
        lc = ax2.plot(v_x, v_c, label="credit", color=COLOR_CREDIT, linewidth=LINE_WIDTH)

        # credit axis and legend
        lns = lc
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
        ax2.set_ylabel('sender credit', color='black')

    plt.title(title)

    plt.ioff()  # disable interactiveness

    plt.savefig("{}{}.png".format(w_filebase, file_suffix), bbox_inches='tight')
    plt.savefig("{}{}.pdf".format(w_filebase, file_suffix), bbox_inches='tight')


def plot_latencies_lines(_v_c, _v_r, _v_s, _v_x, folder, title, w_filebase, vertical_lines=False):

    file_suffix = "-vlines" if vertical_lines else "-hlines"

    # adjust credit array to expose zero credit times with a horizontal floor
    v_c, v_r, v_s, v_x = expose_zero_credit(_v_c, _v_r, _v_s, _v_x, False, True)

    fig, ax1 = plt.subplots()
    fig.set_size_inches(20, 20)

    first = True
    # plot the lines
    if vertical_lines:
        for i in range(len(v_x)):
            x1s = v_x[i]
            x1e = x1s
            y1s = x1s
            y1e = x1s  + v_r[i]
            if first:
                lr = ax1.plot((x1s, x1e), (y1s, y1e), label="receiver latency", color=COLOR_RECEIVER, linewidth=LINE_WIDTH)
            else:
                ax1.plot((x1s, x1e), (y1s, y1e), color=COLOR_RECEIVER, linewidth=LINE_WIDTH)
            x2s = x1s
            x2e = x1s
            y2s = y1e
            y2e = y1e + v_s[i] - v_r[i]
            if first:
                ls = ax1.plot((x2s, x2e), (y2s, y2e), label="sender latency", color=COLOR_SENDER, linewidth=LINE_WIDTH)
            else:
                ax1.plot((x2s, x2e), (y2s, y2e), color=COLOR_SENDER, linewidth=LINE_WIDTH)
    else:
        for i in range(len(v_x)):
            x1s = v_x[i]
            x1e = x1s
            y1s = x1s
            y1e = x1s  + v_r[i]
            ax1.plot((y1s, y1e), (x1s, x1e), color=COLOR_RECEIVER, linewidth=LINE_WIDTH)
            x2s = x1s
            x2e = x1s
            y2s = y1e
            y2e = y1e + v_s[i] - v_r[i]
            ax1.plot((y2s, y2e), (x2s, x2e), color=COLOR_SENDER, linewidth=LINE_WIDTH)

    lc = ax1.plot(v_x, v_c, label="credit T/F", color=COLOR_CREDIT, linewidth=LINE_WIDTH)
    lns = lr + ls + lc
    labels = [l.get_label() for l in lns]
    ax1.legend(lns, labels, loc="upper left")

    ax1.set_ylim(bottom=0)

    if vertical_lines:
        ax1.set_xlabel('message transmit TOD (relative uS)')
        ax1.set_ylabel('recevier - sender completion time (relative uS)')
    else:
        ax1.set_xlabel('message transmit TOD (relative uS)')
        ax1.set_ylabel('recevier - sender completion time (relative uS)')

    ax1.grid()

    plt.title(title)

    plt.ioff()  # disable interactiveness

    plt.savefig("{}{}.png".format(w_filebase, file_suffix), bbox_inches='tight')
    plt.savefig("{}{}.pdf".format(w_filebase, file_suffix), bbox_inches='tight')


def _parse_send(line):
    _message_id, _send_time, _credit = line.split(",", 2)

    return _message_id, int(_send_time), int(_credit)


def expose_zero_credit(c, r, s, x, full_values, use_x):
    """
    Given plot values, insert extra points to highlight zero credit
    An insertion should produce

        input                    output
        1   1211   2857  9288    1   1211   2857  9288
                                 1   1063   2448  9698
        50  1063   2448  9698    50  1063   2448  9698

    This cheats the lateceny lines by one uS. The credit line is kept
    flat until the next transition.
    :param c: credit
    :param r: receive latency
    :param s: send latency
    :param x: x axis points
    :param full_values: propagate real value vs. true/false
    :return: adjusted arrays c,r,s,x
    """
    outc = list()
    outr = list()
    outs = list()
    outx = list()

    # when not propagating full credit values use these to indicate on/off
    mymax = max(x) if use_x else max(s)
    CREDIT_TRUE = 0.04 * mymax
    CREDIT_FALSE = 0.01 * mymax

    # copy first entry
    outc.append(c[0] if full_values else CREDIT_TRUE)
    outr.append(r[0])
    outs.append(s[0])
    outx.append(x[0])

    lastc = c[0]
    for inI in range(1, len(x)):
        if lastc == 1:
            outc.append(1 if full_values else CREDIT_FALSE)
            outr.append(r[inI])
            outs.append(s[inI])
            outx.append(x[inI] - 1)
        if c[inI] == 1:
            outc.append(1 if full_values else CREDIT_FALSE)
        else:
            outc.append(c[inI] if full_values else CREDIT_TRUE)
        outr.append(r[inI])
        outs.append(s[inI])
        outx.append(x[inI])
        lastc = c[inI]

    return outc, outr, outs, outx

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except:
        traceback.print_exc(file=sys.stdout)
