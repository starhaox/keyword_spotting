# encoding: utf-8

'''

@author: ZiqiLiu


@file: stft.py

@time: 2017/7/11 下午12:47

@desc:
'''
import tensorflow as tf
import librosa
import numpy as np
from tensorflow.python.framework import dtypes
from tensorflow.python.framework import ops

from tensorflow.python.ops import array_ops
from tensorflow.python.ops import math_ops
from tensorflow.python.framework import ops
from tensorflow.python.framework import tensor_util


def tf_frame(signal, frame_length, frame_step, name=None):
    """Frame a signal into overlapping frames.
    May be used in front of spectral functions.
    For example:
    ```python
    pcm = tf.placeholder(tf.float32, [None, 9152])
    frames = tf.contrib.signal.frames(pcm, 512, 180)
    magspec = tf.abs(tf.spectral.rfft(frames, [512]))
    image = tf.expand_dims(magspec, 3)
    ```
    Args:
      signal: A `Tensor` of shape `[batch_size, signal_length]`.
      frame_length: An `int32` or `int64` `Tensor`. The length of each frame.
      frame_step: An `int32` or `int64` `Tensor`. The step between frames.
      name: A name for the operation (optional).
    Returns:
      A `Tensor` of frames with shape `[batch_size, num_frames, frame_length]`.
    Raises:
      ValueError: if signal does not have rank 2.
    """
    with ops.name_scope(name, "frames", [signal, frame_length, frame_step]):
        signal = ops.convert_to_tensor(signal, name="signal")
        frame_length = ops.convert_to_tensor(frame_length, name="frame_length")
        frame_step = ops.convert_to_tensor(frame_step, name="frame_step")

        signal_rank = signal.shape.ndims

        if signal_rank != 2:
            raise ValueError(
                "expected signal to have rank 2 but was " + signal_rank)

        signal_length = array_ops.shape(signal)[1]

        num_frames = math_ops.ceil((signal_length - frame_length) / frame_step)
        num_frames = 1 + math_ops.cast(num_frames, dtypes.int32)

        pad_length = (num_frames - 1) * frame_step + frame_length
        pad_signal = array_ops.pad(signal, [[0, 0], [0,
                                                     pad_length - signal_length]])

        indices_frame = array_ops.expand_dims(math_ops.range(frame_length), 0)
        indices_frames = array_ops.tile(indices_frame, [num_frames, 1])

        indices_step = array_ops.expand_dims(
            math_ops.range(num_frames) * frame_step, 1)
        indices_steps = array_ops.tile(indices_step, [1, frame_length])

        indices = indices_frames + indices_steps

        # TODO(androbin): remove `transpose` when `gather` gets `axis` support
        pad_signal = array_ops.transpose(pad_signal)
        signal_frames = array_ops.gather(pad_signal, indices)
        signal_frames = array_ops.transpose(signal_frames, perm=[2, 0, 1])

        return signal_frames


def ceil(a):
    temp = tf.cast(tf.cast(a, tf.int32), tf.float64)
    c = tf.where(tf.equal(a, temp), tf.cast(a, tf.int32),
                 tf.cast(a, tf.int32) + 1)
    return c


def frame(y, n_fft=400, hop_length=160, win_length=400, window='hann',
          dtype=tf.complex64):
    if win_length is None:
        win_length = n_fft

        # Set the default hop, if it's not already specified
    if hop_length is None:
        hop_length = int(win_length // 4)

    fft_window = librosa.filters.get_window(window, win_length, fftbins=True)
    print(fft_window.shape)

    # Pad the window out to n_fft size
    fft_window = librosa.util.pad_center(fft_window, n_fft)
    print(fft_window.shape)

    # Reshape so that the window can be broadcast
    fft_window = fft_window.reshape((-1, 1))

    # Pad the time series so that frames are centered

    # Window the time series.
    y_frames = librosa.util.frame(y, frame_length=n_fft, hop_length=hop_length)

    return (y_frames * fft_window).T


def _infer_frame_shape(signal, frame_length, frame_step, pad_end, axis):
    """Infers the shape of the return value of `frame`."""
    frame_length = tensor_util.constant_value(frame_length)
    frame_step = tensor_util.constant_value(frame_step)
    axis = tensor_util.constant_value(axis)
    if signal.shape.ndims is None:
        return None
    if axis is None:
        return [None] * (signal.shape.ndims + 1)

    signal_shape = signal.shape.as_list()
    num_frames = None
    frame_axis = signal_shape[axis]
    outer_dimensions = signal_shape[:axis]
    inner_dimensions = signal_shape[axis:][1:]
    if signal_shape and frame_axis is not None:
        if frame_step and frame_length is not None:
            if pad_end:
                # Double negative is so that we round up.
                num_frames = -(-frame_axis // frame_step)
            else:
                num_frames = (
                             frame_axis - frame_length + frame_step) // frame_step
            num_frames = max(0, num_frames)
    return outer_dimensions + [num_frames, frame_length] + inner_dimensions


def tf_frame2(signal, frame_length, frame_step, pad_end=False, pad_value=0,
              axis=-1,
              name=None):
    """Expands `signal`'s `axis` dimension into frames of `frame_length`.
    Slides a window of size `frame_length` over `signal`'s `axis` dimension
    with a stride of `frame_step`, replacing the `axis` dimension with
    `[frames, frame_length]` frames.
    If `pad_end` is True, window positions that are past the end of the `axis`
    dimension are padded with `pad_value` until the window moves fully past the
    end of the dimension. Otherwise, only window positions that fully overlap the
    `axis` dimension are produced.
    For example:
    ```python
    pcm = tf.placeholder(tf.float32, [None, 9152])
    frames = tf.contrib.signal.frame(pcm, 512, 180)
    magspec = tf.abs(tf.spectral.rfft(frames, [512]))
    image = tf.expand_dims(magspec, 3)
    ```
    Args:
      signal: A `[..., samples, ...]` `Tensor`. The rank and dimensions
        may be unknown. Rank must be at least 1.
      frame_length: The frame length in samples. An integer or scalar `Tensor`.
      frame_step: The frame hop size in samples. An integer or scalar `Tensor`.
      pad_end: Whether to pad the end of `signal` with `pad_value`.
      pad_value: An optional scalar `Tensor` to use where the input signal
        does not exist when `pad_end` is True.
      axis: A scalar integer `Tensor` indicating the axis to frame. Defaults to
        the last axis. Supports negative values for indexing from the end.
      name: An optional name for the operation.
    Returns:
      A `Tensor` of frames with shape `[..., frames, frame_length, ...]`.
    Raises:
      ValueError: If `frame_length`, `frame_step`, `pad_value`, or `axis` are not
        scalar.
    """
    with ops.name_scope(name, "frame", [signal, frame_length, frame_step,
                                        pad_value]):
        signal = ops.convert_to_tensor(signal, name="signal")
        frame_length = ops.convert_to_tensor(frame_length, name="frame_length")
        frame_step = ops.convert_to_tensor(frame_step, name="frame_step")
        axis = ops.convert_to_tensor(axis, name="axis")

        signal.shape.with_rank_at_least(1)
        frame_length.shape.assert_has_rank(0)
        frame_step.shape.assert_has_rank(0)
        axis.shape.assert_has_rank(0)

        result_shape = _infer_frame_shape(signal, frame_length, frame_step,
                                          pad_end,
                                          axis)

        # Axis can be negative. Convert it to positive.
        signal_rank = array_ops.rank(signal)
        axis = math_ops.range(signal_rank)[axis]

        signal_shape = array_ops.shape(signal)
        outer_dimensions, length_samples, inner_dimensions = array_ops.split(
            signal_shape, [axis, 1, signal_rank - 1 - axis])
        length_samples = array_ops.reshape(length_samples, [])
        num_outer_dimensions = array_ops.size(outer_dimensions)
        num_inner_dimensions = array_ops.size(inner_dimensions)

        # If padding is requested, pad the input signal tensor with pad_value.
        if pad_end:
            pad_value = ops.convert_to_tensor(pad_value, signal.dtype)
            pad_value.shape.assert_has_rank(0)

            # Calculate number of frames, using double negatives to round up.
            num_frames = -(-length_samples // frame_step)

            # Pad the signal by up to frame_length samples based on how many samples
            # are remaining starting from last_frame_position.
            pad_samples = math_ops.maximum(
                0,
                frame_length + frame_step * (num_frames - 1) - length_samples)

            # Pad the inner dimension of signal by pad_samples.
            paddings = array_ops.concat(
                [array_ops.zeros([num_outer_dimensions, 2],
                                 dtype=pad_samples.dtype),
                 [[0, pad_samples]],
                 array_ops.zeros([num_inner_dimensions, 2],
                                 dtype=pad_samples.dtype)],
                0)
            signal = array_ops.pad(signal, paddings, constant_values=pad_value)

            signal_shape = array_ops.shape(signal)
            length_samples = signal_shape[axis]
        else:
            num_frames = math_ops.maximum(
                0, 1 + (length_samples - frame_length) // frame_step)

        subframe_length = util_ops.gcd(frame_length, frame_step)
        subframes_per_frame = frame_length // subframe_length
        subframes_per_hop = frame_step // subframe_length
        num_subframes = length_samples // subframe_length

        slice_shape = array_ops.concat([outer_dimensions,
                                        [num_subframes * subframe_length],
                                        inner_dimensions], 0)
        subframe_shape = array_ops.concat([outer_dimensions,
                                           [num_subframes, subframe_length],
                                           inner_dimensions], 0)
        subframes = array_ops.reshape(array_ops.strided_slice(
            signal, array_ops.zeros_like(signal_shape),
            slice_shape), subframe_shape)

        # frame_selector is a [num_frames, subframes_per_frame] tensor
        # that indexes into the appropriate frame in subframes. For example:
        # [[0, 0, 0, 0], [2, 2, 2, 2], [4, 4, 4, 4]]
        frame_selector = array_ops.reshape(
            math_ops.range(num_frames) * subframes_per_hop, [num_frames, 1])

        # subframe_selector is a [num_frames, subframes_per_frame] tensor
        # that indexes into the appropriate subframe within a frame. For example:
        # [[0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3]]
        subframe_selector = array_ops.reshape(
            math_ops.range(subframes_per_frame), [1, subframes_per_frame])

        # Adding the 2 selector tensors together produces a [num_frames,
        # subframes_per_frame] tensor of indices to use with tf.gather to select
        # subframes from subframes. We then reshape the inner-most
        # subframes_per_frame dimension to stitch the subframes together into
        # frames. For example: [[0, 1, 2, 3], [2, 3, 4, 5], [4, 5, 6, 7]].
        selector = frame_selector + subframe_selector

        frames = array_ops.reshape(
            array_ops.gather(subframes, selector, axis=axis),
            array_ops.concat([outer_dimensions, [num_frames, frame_length],
                              inner_dimensions], 0))

        if result_shape:
            frames.set_shape(result_shape)
        return frames
