from __future__ import print_function, division
from abc import ABCMeta, abstractmethod
import random
import numpy as np
import copy
import numbers
import cv2

try:
    xrange
except NameError:  # python3
    xrange = range

ALL = "ALL"

# We instantiate a current/global random state here once.
# One can also call np.random, but that is (in contrast to np.random.RandomState)
# a module and hence cannot be copied via deepcopy. That's why we use RandomState
# here (and in all augmenters) instead of np.random.
CURRENT_RANDOM_STATE = np.random.RandomState(42)

def is_np_array(val):
    return isinstance(val, (np.ndarray, np.generic))

def is_single_integer(val):
    return isinstance(val, numbers.Integral)

def is_single_float(val):
    return isinstance(val, numbers.Real) and not is_single_integer(val)

def is_single_number(val):
    return is_single_integer(val) or is_single_float(val)

def is_iterable(val):
    return isinstance(val, (tuple, list))

def is_string(val):
    return isinstance(val, str) or isinstance(val, unicode)

def is_integer_array(val):
    return issubclass(val.dtype.type, np.integer)

"""
def current_np_random_state():
    return np.random

def new_np_random_state(seed=None):
    if seed is None:
        # sample manually a seed instead of just RandomState(), because the latter one
        # is way slower.
        return np.random.RandomState(np.random.randint(0, 10**6, 1)[0])
    else:
        return np.random.RandomState(seed)

def dummy_np_random_state():
    return np.random.RandomState(1)

def copy_np_random_state(random_state, force_copy=False):
    if random_state == np.random and not force_copy:
        return random_state
    else:
        rs_copy = dummy_np_random_state()
        print("random_state", random_state)
        print("rs_copy", rs_copy)
        orig_state = random_state.get_state()
        rs_copy.set_state(orig_state)
        return rs_copy

def current_random_state():
    return AugmenterRandomState(None)

def new_random_state(seed=None):
    rs = new_np_random_state(seed=seed)
    return AugmenterRandomState(rs)

def dummy_random_state():
    return new_random_state(1)

def copy_random_state(random_state, force_copy=False):
    assert isinstance(random_state, AugmenterRandomState)
    return AugmenterRandomState(copy_np_random_state(random_state))
"""

def current_random_state():
    return CURRENT_RANDOM_STATE

def new_random_state(seed=None, fully_random=False):
    if seed is None:
        if not fully_random:
            # sample manually a seed instead of just RandomState(), because the latter one
            # is way slower.
            seed = CURRENT_RANDOM_STATE.randint(0, 10**6, 1)[0]
    return np.random.RandomState(seed)

def dummy_random_state():
    return np.random.RandomState(1)

def copy_random_state(random_state, force_copy=False):
    if random_state == np.random and not force_copy:
        return random_state
    else:
        rs_copy = dummy_random_state()
        orig_state = random_state.get_state()
        rs_copy.set_state(orig_state)
        return rs_copy

def from_json(json_str):
    #TODO
    pass

def imresize_many_images(images, sizes=None, interpolation=None):
    s = images.shape
    assert len(s) == 4, s
    nb_images = s[0]
    im_height, im_width = s[1], s[2]
    nb_channels = s[3]
    height, width = sizes[0], sizes[1]

    if height == im_height and width == im_width:
        return np.copy(images)

    ip = interpolation
    assert ip is None or ip in ["linear", "area", "cubic", cv2.INTER_LINEAR, cv2.INTER_AREA, cv2.INTER_CUBIC]
    if ip is None:
        if height > im_height or width > im_width:
            ip = cv2.INTER_AREA
        else:
            ip = cv2.INTER_LINEAR
    elif ip in ["linear", cv2.INTER_LINEAR]:
        ip = cv2.INTER_LINEAR
    elif ip in ["area", cv2.INTER_AREA]:
        ip = cv2.INTER_AREA
    elif ip in ["cubic", cv2.INTER_CUBIC]:
        ip = cv2.INTER_CUBIC
    else:
        raise Exception("Invalid interpolation order")

    result = np.zeros((nb_images, height, width, nb_channels), dtype=np.uint8)
    for img_idx in range(nb_images):
        result_img = cv2.resize(images[img_idx], (width, height), interpolation=ip)
        if len(result_img.shape) == 2:
            result_img = result_img[:, :, np.newaxis]
        result[img_idx] = result_img
    return result

def imresize_single_image(image, sizes, interpolation=None):
    grayscale = False
    if image.shape == 2:
        grayscale = True
        image = image[:, :, np.newaxis]
    assert len(image.shape) == 3, image.shape
    rs = imresize_many_images(image[np.newaxis, :, :, :], sizes, interpolation=interpolation)
    if grayscale:
        return np.squeeze(rs[0, :, :, 0])
    else:
        return rs[0, ...]

class HooksImages(object):
    def __init__(self, activator=None, propagator=None, preprocessor=None, postprocessor=None):
        self.activator = activator
        self.propagator = propagator
        self.preprocessor = preprocessor
        self.postprocessor = postprocessor

    def is_activated(self, images, augmenter, parents):
        if self.activator is None:
            return augmenter.activated
        else:
            return self.activator(images, augmenter, parents)

    def is_propagating(self, images, augmenter, parents, default=True):
        if self.propagator is None:
            if default is None:
                return True
            else:
                return default
        else:
            return self.propagator(images, augmenter, parents, default)

    def preprocess(self, images, augmenter, parents):
        if self.preprocessor is None:
            return images
        else:
            return self.preprocessor(images, augmenter, parents)

    def postprocess(self, images, augmenter, parents):
        if self.postprocessor is None:
            return images
        else:
            return self.postprocessor(images, augmenter, parents)

class HooksKeypoints(HooksImages):
    pass

class Keypoint(object):
    def __init__(self, x, y):
        #assert isinstance(x, int), type(x)
        #assert isinstance(y, int), type(y)
        assert is_single_integer(x), type(x)
        assert is_single_integer(y), type(y)
        self.x = x
        self.y = y

    def project(self, from_shape, to_shape):
        from_height, from_width = from_shape[0:2]
        to_height, to_width = to_shape[0:2]
        x = int(round((self.x / from_width) * to_width))
        y = int(round((self.y / from_height) * to_height))
        return Keypoint(x=x, y=y)

    def shift(self, x, y):
        return Keypoint(self.x + x, self.y + y)

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "Keypoint(x=%d, y=%d)" % (self.x, self.y)

class KeypointsOnImage(object):
    def __init__(self, keypoints, shape):
        self.keypoints = keypoints
        if is_np_array(shape):
            self.shape = shape.shape
        else:
            assert isinstance(shape, (tuple, list))
            self.shape = tuple(shape)

    @property
    def height(self):
        return self.shape[0]

    @property
    def width(self):
        return self.shape[1]

    def on(self, image):
        if ia.is_np_array:
            shape = image.shape
        else:
            shape = image

        keypoints = [kp.project(self.shape, shape) for kp in self.keypoints]
        return KeypointsOnImage(keypoints, shape)

    def shift(self, x, y):
        keypoints = [keypoint.shift(x=x, y=y) for keypoint in self.keypoints]
        return KeypointsOnImage(keypoints, self.shape)

    def get_coords_array(self):
        result = np.zeros((len(self.keypoints), 2), np.int32)
        for i, keypoint in enumerate(self.keypoints):
            result[i, 0] = keypoint.x
            result[i, 1] = keypoint.y
        return result

    @staticmethod
    def from_coords_array(coords, shape):
        assert is_integer_array(coords), coords.dtype
        keypoints = [Keypoint(x=coords[i, 0], y=coords[i, 1]) for i in xrange(coords.shape[0])]
        return KeypointsOnImage(keypoints, shape)

    def to_keypoint_image(self):
        assert len(self.keypoints) > 0
        height, width = self.shape[0:2]
        image = np.zeros((height, width, len(self.keypoints)), dtype=np.uint8)
        for i, keypoint in enumerate(self.keypoints):
            y = keypoint.y
            x = keypoint.x
            if 0 <= y < height and 0 <= x < width:
                image[y, x, i] = 255
        return image

    @staticmethod
    def from_keypoint_image(self, image, if_not_found_coords={"x": -1, "y": -1}, threshold=1):
        assert len(image.shape) == 3
        height, width, nb_keypoints = image.shape

        drop_if_not_found = False
        if if_not_found_coords is None:
            drop_if_not_found = True
            if_not_found_x = -1
            if_not_found_y = -1
        elif isinstance(if_not_found_coords, (tuple, list)):
            assert len(if_not_found_coords) == 2
            if_not_found_x = if_not_found_coords[0]
            if_not_found_y = if_not_found_coords[1]
        elif isinstance(if_not_found_coords, dict):
            if_not_found_x = if_not_found_coords["x"]
            if_not_found_y = if_not_found_coords["y"]
        else:
            raise Exception("Expected if_not_found_coords to be None or tuple or list or dict, got %s." % (type(if_not_found_coords),))

        keypoints = []
        for i in range(nb_keypoints):
            maxidx_flat = np.argmax(image[..., i])
            maxidx_ndim = np.unravel_index(maxidx_flat, (height, width))
            found = (image[maxidx_ndim[0], maxidx_ndim[1], i] >= threshold)
            if found:
                keypoints.append(Keypoint(x=maxidx_ndim[1], y=maxidx_ndim[0]))
            else:
                if drop_if_not_found:
                    pass # dont add the keypoint to the result list, i.e. drop it
                else:
                    keypoints.append(Keypoint(x=if_not_found_x, y=if_not_found_y))

        return KeypointsOnImage(keypoints, shape=(height, width))

    def copy(self):
        return copy.copy(self)

    def deepcopy(self):
        return copy.deepcopy(self)

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        #print(type(self.keypoints), type(self.shape))
        return "KeypointOnImage(%s, shape=%s)" % (str(self.keypoints), self.shape)

"""
class AugmenterRandomState(object):
    def __init__(self, random_state=None):
        assert random_state is None or isinstance(random_state, np.random.RandomState)
        self.random_state = random_state

    def __getattr__(self, attr, *args, **kwargs):
        print("__gettr__", attr)
        if self.random_state is None:
            rs = np.random
        else:
            rs = self.random_state
        print("rs", rs)

        if attr == "random_state":
            print("attr == random_state")
            return self.random_state
        else:
            orig_attr = rs.__getattribute__(attr)
            print("orig_attr", orig_attr)
            if callable(orig_attr):
                print("callable")
                return orig_attr(*args, **kwargs)
            else:
                print("attribute")
                return orig_attr

    def __deepcopy__(self, memo):
        not_there = []
        existing = memo.get(self, not_there)
        if existing is not not_there:
            return existing
        else:
            if self.random_state is None:
                return AugmenterRandomState()
            else:
                return AugmenterRandomState(copy_np_random_state(self.random_state))
"""

"""
class AugJob(object):
    def __init__(self, images, routes=None, preprocessor=None, postprocessor=None, activator=None, track_history=False, history=None):
        self.images = images
        self.routes = routes if routes is not None else []
        self.preprocessor = preprocessor
        self.postprocessor = postprocessor
        self.activator = activator
        self.track_history = track_history
        self.history = history if history is not None else []

    @property
    def nb_images(self):
        return self.images.shape[0]

    @property
    def height(self):
        return self.images.shape[1]

    @property
    def width(self):
        return self.images.shape[2]

    @property
    def nb_channels(self):
        return self.images.shape[3]

    def add_to_history(self, augmenter, changes, before, after):
        if self.track_history:
            self.history.append((augmenter, changes, np.copy(before), np.copy(after)))

    def copy(self, images=None):
        job = copy.copy(self)
        if images is not None:
            job.images = images
        return job

    def deepcopy(self, images=None):
        job = copy.deepcopy(self)
        if images is not None:
            job.images = images
        return job
"""

class BackgroundAugmenter(object):
    def __init__(self, image_source, augmenter, maxlen, nb_workers=1):
        self.augmenter = augmenter
        self.maxlen = maxlen
        self.result_queue = multiprocessing.Queue(maxlen)
        self.batch_workers = []
        for i in range(nb_workers):
            worker = multiprocessing.Process(target=self._augment, args=(image_source, augmenter, self.result_queue))
            worker.daemon = True
            worker.start()
            self.batch_workers.append(worker)

    def join(self):
        for worker in self.batch_workers:
            worker.join()

    def get_batch(self):
        return self.result_queue.get()

    def _augment(self, image_source, augmenter, result_queue):
        batch = next(image_source)
        self.result_queue.put(augmenter.transform(batch))