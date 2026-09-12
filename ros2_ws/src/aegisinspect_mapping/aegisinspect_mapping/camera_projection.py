"""Camera-only projection and bounded exact-observation lookup; no ROS imports."""
from collections import Counter, OrderedDict
from dataclasses import dataclass
from enum import IntEnum
from math import isfinite
import struct
from time import perf_counter

from .depth_geometry import pixel_to_camera_xyz, sample_roi_depth

FRAME = 'camera_optical_frame'


class Status(IntEnum):
    SUCCESS = 0
    NO_VALID_DEPTH = 1
    INSUFFICIENT_DEPTH = 2
    INVALID_CAMERA_MODEL = 3
    OUT_OF_BOUNDS = 4
    TIMESTAMP_MISMATCH = 5
    FRAME_MISMATCH = 6
    INVALID_DEPTH_IMAGE = 7
    INVALID_REQUEST = 8
    NUMERICAL_ERROR = 9


@dataclass(frozen=True)
class Result:
    status: Status
    detail: str
    stamp: tuple[int, int]
    xyz: tuple[float, float, float] | None = None
    pixel: tuple[float, float] | None = None

    @property
    def frame_id(self):
        return FRAME if self.xyz is not None else ''


def stamp_of(header):
    return header.stamp.sec, header.stamp.nanosec


def decode_depth(message):
    """Decode optical Z unchanged, respecting row padding and endianness."""
    if (message.encoding != '32FC1' or message.width <= 0 or message.height <= 0
            or message.step < message.width * 4
            or len(message.data) != message.step * message.height
            or message.is_bigendian not in (0, 1)):
        raise ValueError('expected nonempty 32FC1 with valid stride and payload')
    fmt = ('>' if message.is_bigendian else '<') + str(message.width) + 'f'
    return [struct.unpack_from(fmt, message.data, row * message.step)
            for row in range(message.height)]


def validate_camera(info, depth):
    """Accept only aligned, uncropped, unbinned, undistorted pinhole images."""
    if (info.width <= 0 or info.height <= 0
            or (info.width, info.height) != (depth.width, depth.height)):
        raise ValueError('CameraInfo and depth dimensions must agree')
    k = info.k
    if (len(k) != 9 or not all(isfinite(x) for x in k)
            or k[0] <= 0 or k[4] <= 0
            or any(k[i] != value for i, value in ((1, 0), (3, 0), (6, 0), (7, 0), (8, 1)))):
        raise ValueError('invalid pinhole K')
    if info.distortion_model not in ('', 'plumb_bob', 'rational_polynomial'):
        raise ValueError('unsupported distortion model')
    if any(not isfinite(x) or x != 0 for x in info.d):
        raise ValueError('distorted images are not supported')
    if info.binning_x not in (0, 1) or info.binning_y not in (0, 1):
        raise ValueError('binned images are not supported')
    roi = info.roi
    if (roi.x_offset or roi.y_offset or roi.do_rectify
            or (roi.width, roi.height) not in ((0, 0), (info.width, info.height))):
        raise ValueError('cropped or rectified CameraInfo ROI is not supported')
    # All-zero R/P mean unspecified. Otherwise require the same monocular geometry.
    identity = (1, 0, 0, 0, 1, 0, 0, 0, 1)
    expected_p = (k[0], 0, k[2], 0, 0, k[4], k[5], 0, 0, 0, 1, 0)
    for values, expected in ((info.r, identity), (info.p, expected_p)):
        if len(values) != len(expected) or not all(isfinite(x) for x in values):
            raise ValueError('malformed R/P')
        if any(values) and any(abs(a - b) > 1e-6 for a, b in zip(values, expected)):
            raise ValueError('R/P disagree with unrectified monocular K')
    return dict(fx=k[0], fy=k[4], cx=k[2], cy=k[5])


def project(request, depth, info, *, central_fraction=0.5, min_valid_fraction=0.5):
    """Project ROS-shaped inputs; return absent XYZ for every failure."""
    stamp = stamp_of(request.header)

    def fail(status, detail):
        return Result(status, detail, stamp)

    if (not isfinite(central_fraction) or not 0 < central_fraction <= 1
            or not isfinite(min_valid_fraction) or not 0 <= min_valid_fraction <= 1):
        return fail(Status.INVALID_REQUEST, 'invalid ROI sampling configuration')
    if stamp != stamp_of(depth.header) or stamp != stamp_of(info.header):
        return fail(Status.TIMESTAMP_MISMATCH, 'request/depth/CameraInfo stamps must match exactly')
    if any(h.frame_id != FRAME for h in (request.header, depth.header, info.header)):
        return fail(Status.FRAME_MISMATCH, 'all input frames must be camera_optical_frame')
    if not 0 <= stamp[1] < 1_000_000_000:
        return fail(Status.INVALID_REQUEST, 'invalid timestamp nanoseconds')
    try:
        intrinsics = validate_camera(info, depth)
    except ValueError as exc:
        return fail(Status.INVALID_CAMERA_MODEL, str(exc))
    try:
        rows = decode_depth(depth)
    except (ValueError, struct.error, TypeError) as exc:
        return fail(Status.INVALID_DEPTH_IMAGE, str(exc))
    if request.mode == 0:
        u, v = request.u, request.v
        if type(u) is not int or type(v) is not int:
            return fail(Status.INVALID_REQUEST, 'pixel coordinates must be integers')
        if not (0 <= u < depth.width and 0 <= v < depth.height):
            return fail(Status.OUT_OF_BOUNDS, 'pixel outside image')
        z = rows[v][u]
        if not isfinite(z) or z <= 0:
            return fail(Status.NO_VALID_DEPTH, 'pixel has no positive finite depth')
    elif request.mode == 1:
        bounds = (request.left, request.top, request.right, request.bottom)
        if any(type(x) is not int for x in bounds):
            return fail(Status.INVALID_REQUEST, 'ROI bounds must be integers')
        left, top, right, bottom = bounds
        if left >= right or top >= bottom:
            return fail(Status.INVALID_REQUEST, 'ROI must be nonempty with ordered bounds')
        if not (0 <= left < right <= depth.width and 0 <= top < bottom <= depth.height):
            return fail(Status.OUT_OF_BOUNDS, 'ROI outside image; clipping is disabled')
        # The sampler owns all central-region selection/filtering/median math.
        try:
            z = sample_roi_depth(rows, bounds, central_fraction=central_fraction,
                                 min_valid_fraction=0)
        except ValueError as exc:
            return fail(Status.NO_VALID_DEPTH, str(exc))
        try:
            z = sample_roi_depth(rows, bounds, central_fraction=central_fraction,
                                 min_valid_fraction=min_valid_fraction)
        except ValueError as exc:
            return fail(Status.INSUFFICIENT_DEPTH, str(exc))
        # Geometric center of the requested pixel centers; may be half-integral.
        u, v = (left + right - 1) / 2, (top + bottom - 1) / 2
    else:
        return fail(Status.INVALID_REQUEST, 'mode must be PIXEL=0 or ROI=1')
    try:
        xyz = pixel_to_camera_xyz(u, v, z, **intrinsics)
    except ValueError as exc:
        return fail(Status.NUMERICAL_ERROR, str(exc))
    return Result(Status.SUCCESS, 'ok', stamp, xyz, (float(u), float(v)))


class ProjectionCache:
    """Single-executor cache, bounded per stream by observation count.

    Missing, late, evicted or mismatched observations fail immediately. The caller
    may retry the SAME timestamp after delivery; there is no latest fallback.
    """
    def __init__(self, capacity=30, central_fraction=0.5, min_valid_fraction=0.5):
        if type(capacity) is not int or capacity <= 0:
            raise ValueError('cache_size must be a positive integer')
        if not isfinite(central_fraction) or not 0 < central_fraction <= 1:
            raise ValueError('central_fraction must be in (0, 1]')
        if not isfinite(min_valid_fraction) or not 0 <= min_valid_fraction <= 1:
            raise ValueError('min_valid_fraction must be in [0, 1]')
        self.capacity = capacity
        self.options = dict(central_fraction=central_fraction, min_valid_fraction=min_valid_fraction)
        self.depth = OrderedDict()
        self.info = OrderedDict()
        self.counts = Counter()
        self.last_latency_ms = 0.0

    def _put(self, cache, message):
        key = stamp_of(message.header)
        cache[key] = message
        cache.move_to_end(key)
        while len(cache) > self.capacity:
            cache.popitem(last=False)

    def add_depth(self, message):
        self._put(self.depth, message)

    def add_info(self, message):
        self._put(self.info, message)

    def handle(self, request):
        started = perf_counter()
        key = stamp_of(request.header)
        if key not in self.depth or key not in self.info:
            result = Result(Status.TIMESTAMP_MISMATCH, 'exact observation pair is not cached', key)
        else:
            result = project(request, self.depth[key], self.info[key], **self.options)
        self.counts[result.status.name] += 1
        self.last_latency_ms = (perf_counter() - started) * 1000
        return result


def fill_response(result, response, latency_ms):
    """ROS wire failures use NaNs, never the generated Point's default zeros."""
    response.status = int(result.status)
    response.detail = result.detail
    response.header.stamp.sec, response.header.stamp.nanosec = result.stamp
    response.header.frame_id = result.frame_id
    response.point.x, response.point.y, response.point.z = result.xyz or (float('nan'),) * 3
    response.sample_u, response.sample_v = result.pixel or (float('nan'),) * 2
    response.latency_ms = latency_ms
    return response
