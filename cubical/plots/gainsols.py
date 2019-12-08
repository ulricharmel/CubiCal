#!/usr/bin/env python
from __future__ import print_function
from cubical.tools import logger
from collections import OrderedDict
import matplotlib.patches as mpatches
from pylab import *
import re

log = logger.getLogger("gain_plots")


class PlotLimits(object):
    def __init__(self):
        self.max_reim = None
        self.max_reim_1 = None
        self.max_phase = None
        self.min_ampl = None
        self.max_ampl = None
        self.min_ampl_1 = None
        self.max_ampl_1 = None
        self.min_freq = None
        self.max_freq = None
        self.min_time = None
        self.max_time = None

class PlotOptions(PlotLimits):
    """This holds a set of common plotting options"""
    def __init__(self):
        self.dpi = 150
        self.font_size = 10
        self.ncol = 4
        self.nrow = 8
        self.width = 4
        self.height = 3

    @staticmethod
    def populate_argparse(parser):
        parser.add_argument("--nrow", type=int, default=7, help="Plot rows")
        parser.add_argument("--ncol", type=int, default=4, help="Plot columns")
        parser.add_argument("--width", type=float, metavar="INCHES", default=4, help="Plot width")
        parser.add_argument("--height", type=float, metavar="INCHES", default=3, help="Plot height")
        parser.add_argument("--dpi", type=int, default=150, help="Plot DPI")
        parser.add_argument("--font-size", type=int, default=6, help="Font size")
        parser.add_argument("--min-freq", type=float, metavar="MHz", default=None, help="Start frequency")
        parser.add_argument("--max-freq", type=float, metavar="MHz", default=None, help="End frequency")
        parser.add_argument("--min-time", type=float, metavar="s", default=None, help="Start time")
        parser.add_argument("--max-time", type=float, metavar="s", default=None, help="End time")

        parser.add_argument("--max-reim", type=float, metavar="VALUE", default=None, help="Sets re/im axis limits")
        parser.add_argument("--max-reim-1", type=float, metavar="VALUE", default=None, help="Sets re/im axis limits for off-diagonals")
        parser.add_argument("--max-phase", type=float, metavar="DEG", default=None, help="Sets phase axis limits")
        parser.add_argument("--min-ampl", type=float, metavar="AMPL", default=None, help="Sets ampl axis limits")
        parser.add_argument("--max-ampl", type=float, metavar="AMPL", default=None, help="Sets ampl axis limits")
        parser.add_argument("--min-ampl-1", type=float, metavar="AMPL", default=None, help="Sets ampl axis limits for off-diagonals")
        parser.add_argument("--max-ampl-1", type=float, metavar="AMPL", default=None, help="Sets ampl axis limits for off-diagonals")

options = PlotOptions()

def get_plot_limits(options, sols, time0=0):
    # get global plot limits
    auto_limits = PlotLimits()
    auto_limits.min_time = 0
    auto_limits.max_time = (max([max(time) for time,_,_,_,_,_ in sols.values() if len(time)] or [0]) - time0)/3600.
    auto_limits.min_freq = min([min(freq) for _,freq,_,_,_,_ in sols.values() if len(freq)] or [0])*1e-6
    auto_limits.max_freq = max([max(freq) for _,freq,_,_,_,_ in sols.values() if len(freq)] or [0])*1e-6
    if auto_limits.max_time == auto_limits.min_time:
        auto_limits.max_time += 1
    if auto_limits.max_freq == auto_limits.min_freq:
        auto_limits.max_freq += 1

    auto_limits.max_ampl = max([ max(abs(g00).max(), abs(g11).max()) for _, _, g00, g01, g10, g11 in sols.values()])
    auto_limits.max_ampl_1 = max([ max(abs(g01).max(), abs(g10).max()) for _, _, g00, g01, g10, g11 in sols.values()])
    auto_limits.min_ampl = min([ min(abs(g00).min(), abs(g11).min()) for _, _, g00, g01, g10, g11 in sols.values()])
    auto_limits.min_ampl_1 = min([ min(abs(g01).min(), abs(g10).min()) for _, _, g00, g01, g10, g11 in sols.values()])
    auto_limits.max_phase = max([ max([abs(np.angle(g)).max() for g in ggs[2:]]) for ggs in sols.values()])*180/np.pi
    auto_limits.max_reim = max([ max(abs(g00.real).max(), abs(g00.imag).max(), abs(g11.real).max(), abs(g11.imag).max())
                                 for _, _, g00, g01, g10, g11 in sols.values()])
    auto_limits.max_reim_1 = max([ max(abs(g01.real).max(), abs(g01.imag).max(), abs(g10.real).max(), abs(g10.imag).max())
                                   for _, _, g00, g01, g10, g11 in sols.values()])
    # override with options
    for attr in dir(auto_limits):
        if attr.startswith("min") or attr.startswith("max"):
            val = getattr(options, attr)
            if val is not None:
                setattr(auto_limits, attr, val)

    return auto_limits

def get_plot_counts(nsols, plots_per_sol):
    num_plots = nsols*plots_per_sol
    rows_needed = int(math.ceil(num_plots / float(options.ncol)))
    log.info("{}x{} plots in {} columns need {} rows".format(nsols, plots_per_sol,options.ncol, rows_needed))
    if rows_needed > options.nrow:
        max_sols = options.nrow * options.ncol // plots_per_sol
        log.warn("Not enough rows specified, displaying only first {} solutions".format(max_sols))
    else:
        max_sols = nsols
    return max_sols, max_sols*plots_per_sol, rows_needed



def plot_bandpass(sols, plot_diag='ap', plot_offdiag='', gaintype=("Bandpass", "Offdiag bandpass"), figtitle=None):
    """
    Makes leakage plots given by sols dict
    """
    fig = figure(figsize=(options.ncol*options.width, options.nrow*options.height), dpi=options.dpi)
    tight_layout()
    subplots_adjust(left=0.05, bottom=0.05, right=0.95, top=0.95)
    if figtitle:
        fig.suptitle(figtitle, fontsize=options.font_size*2)
    fontdict = dict(fontsize=options.font_size)
    fontdict_title = dict(weight='bold', fontsize=options.font_size * 1.2)

    nplot = 0

    lim = get_plot_limits(options, sols)
    x1 = sols.values()[0][2]
    if x1.shape[0] > 100:
        log.warn("making bandpass plot for {} time slices, this better be intentional!".format(x1.shape[0]))

    all_ri = 'ap' not in set([plot_diag, plot_offdiag])  # do we have only re/im plots?
    all_ap = 'ri' not in set([plot_diag, plot_offdiag])  # do we have only phase plots?
    max_sols, max_plots, rows_needed = get_plot_counts(len(sols), int(plot_diag in ('ap', 'ri')) + int(plot_offdiag in ('ap', 'ri')))

    def _prep_plot(nplot, ant, num_gaintype, plot_type):
        nplot += 1
        ax = subplot(options.nrow, options.ncol, nplot)
        last_row = (max_plots - nplot) < options.ncol

        title("{} antenna {}".format(gaintype[num_gaintype], ant), fontdict=fontdict_title)

        ax.set_xlim(lim.min_freq, lim.max_freq)
        ax.tick_params("both", direction="in", labelsize=options.font_size)
        ax2 = ax.twinx()
        ax2.set_ylim(-lim.max_phase, lim.max_phase)
        #ax2.set_xticks([])
        ax2.tick_params("y", direction="in", labelsize=options.font_size)
        if last_row:
            ax.set_xlabel("Frequency (MHz)", fontdict=fontdict)
        else:
            ax.set_xticklabels([])
        # label phase axis if needed
        if not all_ri and nplot % options.ncol == 0:
            ax2.set_ylabel("Phase (deg)", fontdict=fontdict)
        else:
            ax2.set_yticklabels([])
            if plot_type != 'ap':
                ax2.set_yticks([])
        for axis in ax.xaxis, ax.yaxis:
            for tick in axis.get_major_ticks():
                tick.label.set_fontsize(options.font_size)
        ax.get_yaxis().get_major_formatter().set_useOffset(False)
        return nplot, ax, ax2

    def _make_reim_plot(ax, freq, x1, x2, corrs, legend):
        re1, im1, re2, im2 = "Re "+corrs[0], "Im "+corrs[0], "Re "+corrs[1], "Im "+corrs[1]
        for ts in xrange(x1.shape[0]):
            ax.plot(freq, x1[ts].real, '+r', ms=2, label=re1 if not ts else None)
            ax.plot(freq, x1[ts].imag, '+b', ms=2, label=im1 if not ts else None)
        for ts in xrange(x2.shape[0]):
            ax.plot(freq, x2[ts].real, '+c', ms=2, label=re1 if not ts else None)
            ax.plot(freq, x2[ts].imag, '+y', ms=2, label=im2 if not ts else None)
        if legend:
            ax.legend(handles=[mpatches.Patch(color=col, label=label) for col, label in
                                   ("r", re1), ("b", im1),
                                   ("c", re2), ("y", im2)
                               ], loc="upper center", ncol=2, fontsize=options.font_size)

    def _make_ap_plot(ax, ax2, freq, x1, x2, corrs, legend):
        amp1, ph1, amp2, ph2 = "|"+corrs[0]+"|", corrs[0]+ " phase", "|"+corrs[1]+"|", corrs[1]+" phase"
        for ts in range(x1.shape[0]):
            ax2.plot(freq, np.angle(x1[ts]) * 180 / math.pi, '.c', ms=0.5,
                     label=ph1 if not ts else None)
            ax2.plot(freq, np.angle(x2[ts]) * 180 / math.pi, '.y', ms=0.5,
                     label=ph2 if not ts else None)
            ax.plot(freq, abs(x1[ts]), '+r', ms=2, label=amp1 if not ts else None)
            ax.plot(freq, abs(x2[ts]), '+b', ms=2, label=amp2 if not ts else None)
        if legend:
            ax.legend(handles=[mpatches.Patch(color=col, label=label) for col, label in
                                   ("r", amp1), ("b", amp2),
                                   ("c", ph1),  ("y", ph2)
                               ], loc="upper center", ncol=2, fontsize=options.font_size)

    for iant, (ant, (time, freq, g00, g01, g10, g11)) in enumerate(sols.items()[:max_sols]):
        #    print "shape is {}, grid span is {} {}".format(d00.shape, time[[0,-1]], freq[[0,-1]])
        freq = freq * 1e-6

        if plot_diag in ('ap', 'ri'):
            nplot, ax, ax2 = _prep_plot(nplot, ant, 0, plot_diag)

            if plot_diag == 'ap':
                if nplot % options.ncol == 1:
                    ax.set_ylabel("Amplitude", fontdict=fontdict)
                ax.set_ylim(lim.min_ampl, lim.max_ampl)
                _make_ap_plot(ax, ax2, freq, g00, g11, ("RR", "LL"), legend=not iant)
                # label axis if needed
                #if all_ap and nplot % options.ncol > 1:
                #    ax.set_yticklabels([])
            else:
                ax.set_ylim(-lim.max_reim, lim.max_reim)
                _make_reim_plot(ax, freq, g00, g11, ("RR", "LL"), legend=not iant)
                # label axis if needed
                #if all_ri and nplot % options.ncol > 1:
                #    ax.set_yticklabels([])

        if plot_offdiag in ('ap', 'ri'):
            nplot, ax, ax2 = _prep_plot(nplot, ant, 1,  plot_offdiag)

            if plot_offdiag == 'ap':
                if nplot % options.ncol == 1:
                    ax.set_ylabel("Amplitude", fontdict=fontdict)
                ax.set_ylim(lim.min_ampl_1, lim.max_ampl_1)
                _make_ap_plot(ax, ax2, freq, g01, g10, ("RL", "LR"), legend=not iant)
            else:
                ax.set_ylim(-lim.max_reim_1, lim.max_reim_1)
                _make_reim_plot(ax, freq, g01, g10, ("RL", "LR"), legend=not iant)
                # label axis if needed
                #if all_ri and nplot % options.ncol > 1:
                #    ax.set_yticklabels([])


    log.print("{} plots generated ({} rows and {} columns)".format(nplot, options.nrow, options.ncol))
    return fig

def plot_gain(sols, plot_diag='ap', plot_offdiag='', gaintype=("Gain", "Offdiag gain"), figtitle=None):
    """
    Makes leakage plots given by sols dict
    """
    fig = figure(figsize=(options.ncol*options.width, options.nrow*options.height), dpi=options.dpi)
    tight_layout()
    subplots_adjust(left=0.05, bottom=0.05, right=0.95, top=0.95)
    if figtitle:
        fig.suptitle(figtitle, fontsize=options.font_size*2)
    fontdict = dict(fontsize=options.font_size)
    fontdict_title = dict(weight='bold', fontsize=options.font_size * 1.2)

    nplot = 0

    time0 = min([time.min() for time,_,_,_,_,_ in sols.values()])

    lim = get_plot_limits(options, sols, time0=time0)

    x1 = sols.values()[0][2]
    if x1.shape[1] > 100:
        log.warn("making gain plot for {} frequency slices, this better be intentional!".format(x1.shape[1]))

    all_ri = 'ap' not in set([plot_diag, plot_offdiag])  # do we have only re/im plots?
    all_ap = 'ri' not in set([plot_diag, plot_offdiag])  # do we have only phase plots?
    max_sols, max_plots, rows_needed = get_plot_counts(len(sols), int(plot_diag in ('ap', 'ri')) + int(plot_offdiag in ('ap', 'ri')))

    def _prep_plot(nplot, ant, num_gaintype, plot_type):
        nplot += 1
        ax = subplot(options.nrow, options.ncol, nplot)
        last_row = (max_plots - nplot) < options.ncol

        title("{} antenna {}".format(gaintype[num_gaintype], ant), fontdict=fontdict_title)

        ax.set_xlim(lim.min_time, lim.max_time)
        ax.tick_params("both", direction="in", labelsize=options.font_size)
        ax2 = ax.twinx()
        ax2.set_ylim(-lim.max_phase, lim.max_phase)
        #ax2.set_xticks([])
        ax2.tick_params("y", direction="in", labelsize=options.font_size)
        if last_row:
            ax.set_xlabel("Time (h since start)", fontdict=fontdict)
        else:
            ax.set_xticklabels([])
        # label phase axis if needed
        if not all_ri and nplot % options.ncol == 0:
            ax2.set_ylabel("Phase (deg)", fontdict=fontdict)
        else:
            ax2.set_yticklabels([])
            if plot_type != 'ap':
                ax2.set_yticks([])
        for axis in ax.xaxis, ax.yaxis:
            for tick in axis.get_major_ticks():
                tick.label.set_fontsize(options.font_size)
        ax.get_yaxis().get_major_formatter().set_useOffset(False)
        return nplot, ax, ax2

    def _make_reim_plot(ax, time, x1, x2, corrs, legend):
        re1, im1, re2, im2 = "Re "+corrs[0], "Im "+corrs[0], "Re "+corrs[1], "Im "+corrs[1]
        for fs in xrange(x1.shape[1]):
            ax.plot(time, x1[:, fs].real, '+r', ms=2, label=re1 if not fs else None)
            ax.plot(time, x1[:, fs].imag, '+b', ms=2, label=im1 if not fs else None)
        for fs in xrange(x2.shape[1]):
            ax.plot(time, x2[:, fs].real, '+c', ms=2, label=re1 if not fs else None)
            ax.plot(time, x2[:, fs].imag, '+y', ms=2, label=im2 if not fs else None)
        if legend:
            ax.legend(handles=[mpatches.Patch(color=col, label=label) for col, label in
                                   ("r", re1), ("b", im1),
                                   ("c", re2), ("y", im2)
                               ], loc="upper center", ncol=2, fontsize=options.font_size)

    def _make_ap_plot(ax, AX2, time, x1, x2, corrs, legend):
        amp1, ph1, amp2, ph2 = "|"+corrs[0]+"|", corrs[0]+ " phase", "|"+corrs[1]+"|", corrs[1]+" phase"
        for fs in range(x1.shape[1]):
            ax2.plot(time, np.angle(x1[:, fs]) * 180 / math.pi, '.c', ms=0.5,
                     label=ph1 if not fs else None)
            ax2.plot(time, np.angle(x2[:, fs]) * 180 / math.pi, '.y', ms=0.5,
                     label=ph2 if not fs else None)
            ax.plot(time, abs(x1[:, fs]), '+r', ms=2, label=amp1 if not fs else None)
            ax.plot(time, abs(x2[:, fs]), '+b', ms=2, label=amp2 if not fs else None)
        if legend:
            ax.legend(handles=[mpatches.Patch(color=col, label=label) for col, label in
                                   ("r", amp1), ("b", amp2),
                                   ("c", ph1),  ("y", ph2)
                               ], loc="upper center", ncol=2, fontsize=options.font_size)

    for iant, (ant, (time, freq, g00, g01, g10, g11)) in enumerate(sols.items()):
        #    print "shape is {}, grid span is {} {}".format(d00.shape, time[[0,-1]], freq[[0,-1]])
        time = (time-time0)/3600.

        if plot_diag in ('ap', 'ri'):
            nplot, ax, ax2 = _prep_plot(nplot, ant, 0, plot_diag)

            if plot_diag == 'ap':
                if nplot % options.ncol == 1:
                    ax.set_ylabel("Amplitude", fontdict=fontdict)
                ax.set_ylim(lim.min_ampl, lim.max_ampl)
                _make_ap_plot(ax, ax2, time, g00, g11, ("RR", "LL"), legend=not iant)
            else:
                ax.set_ylim(-lim.max_reim, lim.max_reim)
                _make_reim_plot(ax, time, g00, g11, ("RR", "LL"), legend=not iant)

        if plot_offdiag in ('ap', 'ri'):
            nplot, ax, ax2 = _prep_plot(nplot, ant, 1,  plot_offdiag)

            if plot_offdiag == 'ap':
                if nplot % options.ncol == 1:
                    ax.set_ylabel("Amplitude", fontdict=fontdict)
                ax.set_ylim(lim.min_ampl_1, lim.max_ampl_1)
                _make_ap_plot(ax, ax2, time, g01, g10, ("RL", "LR"), legend=not iant)
            else:
                ax.set_ylim(-lim.max_reim_1, lim.max_reim_1)
                _make_reim_plot(ax, time, g01, g10, ("RL", "LR"), legend=not iant)

    log.print("{} plots generated ({} rows and {} columns)".format(nplot, options.nrow, options.ncol))
    return fig


def get_freq_slice(FS, all_freqs):
    if FS is None:
        if0 = if1 = None
        if options.min_freq is not None:
            wh = np.where(all_freqs >= options.min_freq*1e+6)[0]
            if0 = wh[0] if len(wh) else None
        if options.max_freq is not None:
            wh = np.where(all_freqs >= options.max_freq*1e+6)[0]
            if1 = wh[0] if len(wh) else None
        if if0 is not None or if1 is not None:
            FS = slice(if0 or 0, if1)
        else:
            FS = slice(None)
    return FS

def get_time_slice(TS, all_times):
    if TS is None:
        return slice(None)
    return TS

def prepare_sols_dict(G, FS=None, TS=None, ANTS=slice(None)):
    """
    Extract solutions slices into a dict
    """
    FS = get_freq_slice(FS, G.grid[G.ax.freq])
    TS = get_freq_slice(TS, G.grid[G.ax.time])

    sols = OrderedDict()

    # get valid solutions
    if isinstance(ANTS, (list, tuple)):
        ANTS = [(ant, G.grid[G.ax.ant][ant]) for ant in ANTS]
    else:
        ANTS = enumerate(G.grid[G.ax.ant][ANTS])
    for iant, ant in ANTS:
        # this gets the "raw" solutions for a given slice (antenna, correlation, etc.), and also the grid they're defined on,
        # which could be a subset of the full grid given by the description
        g00, (time, freq) = G.get_slice(ant=iant, corr1=0, corr2=0)
        if g00 is None:
            continue
        g01, (time, freq) = G.get_slice(ant=iant, corr1=0, corr2=1)
        g10, (time, freq) = G.get_slice(ant=iant, corr1=1, corr2=0)
        g11, (time, freq) = G.get_slice(ant=iant, corr1=1, corr2=1)
        sols[ant] = time[TS], freq[FS], g00[TS, FS], g01[TS, FS], g10[TS, FS], g11[TS, FS]

    return sols

def plot_bandpass_cc(G, FS=None, TS=None, ANTS=slice(None),
                        plot_diag='ap', plot_offdiag='', figtitle=None):
    """Plots G solutions from a CubiCal database"""
    sols = prepare_sols_dict(G, FS, TS, ANTS)
    return plot_bandpass(sols, plot_diag=plot_diag, plot_offdiag=plot_offdiag, figtitle=figtitle)

def plot_gain_cc(G, FS=None, TS=None, ANTS=slice(None),
                        plot_diag='ap', plot_offdiag='', figtitle=None):
    """Plots G solutions from a CubiCal database"""
    sols = prepare_sols_dict(G, FS, TS, ANTS)
    return plot_gain(sols, plot_diag=plot_diag, plot_offdiag=plot_offdiag, figtitle=figtitle)


def read_cubical_gains(filename, label=None):
    """
    Reads cCubiCal leakage solutions from a CubiCal DB
    """
    import cubical
    from cubical.database import pickled_db
    db = pickled_db.PickledDatabase()
    db._load(filename)
    log.print("{} contains solutions for {}".format(filename, " ".join(db.names())))
    # try to auto-pick a label
    if label is None:
        for name in db.names():
            match = re.match("(\w+):gain", name)
            if match:
                label = match.group(1)
                log.print("  gain label is {}".format(label))
                break
        else:
            log.error("no gain entries found in database")
            return None

    gg = db['{}:gain'.format(label)]
    log.print("  axes are: {}; shape is {}".format(", ".join(gg.axis_labels), gg.shape))  # axis info
    log.print("  can be interpolated over axes {}".format(" ".join([gg.axis_labels[i] for i in gg.interpolation_axes])))
    time, freq = gg.grid[gg.ax.time], gg.grid[gg.ax.freq]  # grid info
    log.print("    time span {} h (start {:f}), freq span {} to {} MHz".format(
                    (time[-1]-time[0])/3600, time[0], freq[0]*1e-6, freq[-1]*1e-6))

    valid_ants = set([ant for iant, ant in enumerate(gg.grid[gg.ax.ant])
                      if gg.is_slice_valid(ant=iant, corr1=0, corr2=0)])

    log.print("  valid antennas:", " ".join([ant for ant in gg.grid[gg.ax.ant] if ant in valid_ants]))
    log.print("  missing antennas:", " ".join([ant for ant in gg.grid[gg.ax.ant] if ant not in valid_ants] or ["none"]))
    return gg