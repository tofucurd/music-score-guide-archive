"""Exact recording time and stable score-cohort primitives."""
from bisect import bisect_left, bisect_right

def continuous_ranges(counts):
    result, start = [], 0
    for count in counts:
        assert isinstance(count, int) and count > 0
        result.append([start, start + count])
        start += count
    return result

def sounding_cohort(events, section):
    lo, hi = section
    return {e['staff'] for e in events
            if e['range'][0] < hi and
            (e['range'][1] > lo or lo <= e['range'][0] == e['range'][1])}

def interpolate(points, position):
    i = bisect_right(points, position, key=lambda p: p[0]) - 1
    if i < 0: return points[0][1]
    if i >= len(points) - 1: return points[-1][1]
    x, y = points[i]
    nx, ny = points[i + 1]
    return y + (ny - y) * (position - x) / (nx - x)

def frame_boundaries(samples):
    return [(s + 1599) // 1600 for s in samples]

def interval_index(starts, position):
    return max(0, min(len(starts) - 1, bisect_right(starts, position) - 1))

def source_sample(points, q, onset=False):
    left = bisect_left(points, q, key=lambda p:p[1])
    right = bisect_right(points, q, key=lambda p:p[1])
    if left != right: return points[right-1 if onset else left][0]
    if left == 0: return points[0][0]
    if left == len(points): return points[-1][0]
    s,a = points[left-1]; t,b = points[left]
    return round(s + (t-s)*(q-a)/(b-a))
