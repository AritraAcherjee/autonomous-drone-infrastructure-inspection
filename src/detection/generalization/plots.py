"""Optional matplotlib plots; callers own saving/closing returned figures."""


def confidence_plot(calibration):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.hist([calibration['TP_confidences'], calibration['FP_confidences']], bins=[i/10 for i in range(11)], label=['TP', 'FP'])
    ax.set(xlabel='Prediction confidence', ylabel='Detection count')
    ax.legend()
    return fig


def reliability_plot(calibration):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    rows = [r for r in calibration['bins'] if r['count']]
    ax.plot([0, 1], [0, 1], '--', color='gray')
    ax.plot([r['mean_confidence'] for r in rows], [r['accuracy'] for r in rows], 'o-')
    ax.set(xlabel='Mean confidence', ylabel='Matched fraction', xlim=(0, 1), ylim=(0, 1))
    return fig
