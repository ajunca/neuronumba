# --------------------------------------------------------------------------
# COMPUTE POWER SPECTRA FOR
# NARROWLY FILTERED DATA WITH LOW BANDPASS (0.04 to 0.07 Hz)
# not # WIDELY FILTERED DATA (0.04 Hz to justBelowNyquistFrequency)
#     # [justBelowNyquistFrequency depends on TR,
#     # for a TR of 2s this is 0.249 Hz]
# #--------------------------------------------------------------------------
import numpy as np


def conv(u, v):  # python equivalent to matlab conv 'same' method
    # from https://stackoverflow.com/questions/38194270/matlab-convolution-same-to-numpy-convolve
    npad = len(v) - 1
    full = np.convolve(u, v, 'full')
    first = npad - npad // 2
    return full[first:first + len(u)]


def gaussfilt(t, z, sigma):
    # Apply a Gaussian filter to a time series
    #    Inputs: t = independent variable, z = data at points t, and
    #        sigma = standard deviation of Gaussian filter to be applied.
    #    Outputs: zfilt = filtered data.
    #
    #    based on the code by James Conder. Aug 22, 2013
    #    (partial) translation by Gustavo Patow
    n = z.size  # number of data
    a = 1 / (np.sqrt(2 * np.pi) * sigma)  # height of Gaussian
    sigma2 = sigma * sigma

    # check for uniform spacing
    # if so, use convolution. if not use numerical integration
    # uniform = false;
    dt = np.diff(t)
    dt = dt[0]
    # ddiff = max(abs(diff(diff(t))));
    # if ddiff/dt < 1.e-4
    #     uniform = true;
    # end

    # Only the uniform option is considered
    filter = dt * a * np.exp(-0.5 * ((t - np.mean(t)) ** 2) / sigma2)
    i = filter < dt * a * 1.e-6
    filter = np.delete(filter, i)  # filter[i] = []
    zfilt = conv(z, filter)
    onesToFilt = np.ones(np.size(z))  # remove edge effect from conv
    onesFilt = conv(onesToFilt, filter)
    zfilt = zfilt / onesFilt

    return zfilt


def filt_pow_spetra(signal, TR, bpf):
    nNodes, Tmax = signal.shape  # Here we are assuming we receive only ONE subject...
    # idxMinFreq = np.argmin(np.abs(freqs-0.04))
    # idxMaxFreq = np.argmin(np.abs(freqs-0.07))
    # nFreqs = freqs.size

    # delt = 2                                   # sampling interval
    # fnq = 1/(2*delt)                           # Nyquist frequency
    # k = 2                                      # 2nd order butterworth filter

    # =================== WIDE BANDPASS
    # flp = .04                                  # lowpass frequency of filter
    # fhi = fnq-0.001  #.249                     # highpass needs to be limited by Nyquist frequency, which in turn depends on TR
    # ts_filt_wide =zscore(filtfilt(bfilt_wide,afilt_wide,x))
    # pw_filt_wide = abs(fft(ts_filt_wide))
    # PowSpect_filt_wide(:,seed) = pw_filt_wide[1:np.floor(TT/2)] ** 2 / (TT/2)

    # =================== NARROW LOW BANDPASS
    # print(f'BOLD Filters: low={BOLDFilters.flp}, hi={BOLDFilters.fhi}')
    # ts_filt_narrow = zscore(BOLDFilters.BandPassFilter(signal, removeStrongArtefacts=False), axis=0)  # Here we used the zscore to "normalize" the values... not really needed, but makes things easier to follow! ;-)
    # TODO: move all shapes to (n_time_samples, n_rois)
    ts_filt_narrow = bpf.filter(signal.T).T
    pw_filt_narrow = np.abs(np.fft.fft(ts_filt_narrow, axis=1))
    PowSpect_filt_narrow = pw_filt_narrow[:, 0:int(np.floor(Tmax / 2))].T ** 2 / (Tmax / TR)

    # Power_Areas_filt_narrow_unsmoothed = PowSpect_filt_narrow  # By now, do nothing...
    return PowSpect_filt_narrow


def filt_pow_spetra_multiple_subjects(signal, tr, bpf):
    if type(signal) is dict:
        n_subjects = len(signal.keys())
        n_nodes, tmax = next(iter(signal.values())).shape
        PowSpect_filt_narrow = np.zeros((n_subjects, n_nodes, int(np.floor(tmax / 2))))
        for i, s in enumerate(signal.keys()):
            PowSpect_filt_narrow[i] = filt_pow_spetra(signal[s][:, :tmax], tr, bpf).T
        Power_Areas_filt_narrow_unsmoothed = np.mean(PowSpect_filt_narrow, axis=0).T
    elif signal.ndim == 2:
        n_subjects = 1
        n_nodes, tmax = signal.shape  # Here we are assuming we receive only ONE subject...
        Power_Areas_filt_narrow_unsmoothed = filt_pow_spetra(signal, tr)
    else:
        # In case we receive more than one subject, we do a mean...
        n_subjects, n_nodes, tmax = signal.shape
        PowSpect_filt_narrow = np.zeros((n_subjects, n_nodes, int(np.floor(tmax / 2))))
        for s in range(n_subjects):
            PowSpect_filt_narrow[s] = filt_pow_spetra(signal[s, :, :], tr, bpf).T
        Power_Areas_filt_narrow_unsmoothed = np.mean(PowSpect_filt_narrow, axis=0).T
        # Power_Areas_filt_wide_unsmoothed = mean(PowSpect_filt_wide,3);

    Power_Areas_filt_narrow_smoothed = np.zeros_like(Power_Areas_filt_narrow_unsmoothed)
    # Power_Areas_filt_wide_smoothed = zeros(nFreqs, nNodes);
    # vsig = zeros(1, nNodes);
    Ts = tmax * tr
    freqs = np.arange(0, tmax / 2 - 1) / Ts
    for seed in np.arange(n_nodes):
        Power_Areas_filt_narrow_smoothed[:, seed] = gaussfilt(freqs, Power_Areas_filt_narrow_unsmoothed[:, seed], 0.01)
        # Power_Areas_filt_wide_smoothed(:,seed)=gaussfilt(freq,Power_Areas_filt_wide_unsmoothed(:,seed)',0.01);

        # relative power in frequencies of interest (.04 - .07 Hz) with respect
        # to entire power of bandpass-filtered data (.04 - just_below_nyquist)
        #  vsig(seed) =...
        #         sum(Power_Areas_filt_wide_smoothed(idxMinFreq:idxMaxFreq,seed))/sum(Power_Areas_filt_wide_smoothed(:,seed));

    # a-minimization seems to only work if we use the indices for frequency of
    # maximal power from the narrowband-smoothed data
    idxFreqOfMaxPwr = np.argmax(Power_Areas_filt_narrow_smoothed, axis=0)
    f_diff = freqs[idxFreqOfMaxPwr]
    return f_diff
