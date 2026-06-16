from __future__ import annotations
import numpy as np
from sklearn.metrics import f1_score


def find_best_f1_threshold(y_true, probabilities, start: float = 0.05, stop: float = 0.95, step: float = 0.005):
    thresholds = np.arange(start, stop + step, step)
    scores = [f1_score(y_true, np.asarray(probabilities) >= threshold) for threshold in thresholds]
    index = int(np.argmax(scores))
    return float(thresholds[index]), float(scores[index])
