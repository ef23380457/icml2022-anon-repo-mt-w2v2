################################################################################
#
# This file defines batch data classes and how to collate
# AudioDataSample's into the specific batches.
#
# Author(s): Anonymous
################################################################################

from dataclasses import dataclass
from typing import Dict, List, Union

import torch as t

from torch.utils.data._utils.collate import default_collate as torch_default_collate

from .pipeline.debug import BatchDebugInfo
from .pipeline.base import AudioDataSample
from .audio_collate_pad import collate_append_constant

################################################################################
# implement a batch for speaker recognition


@dataclass
class SpeakerClassificationDataBatch:
    # the number of samples this batch contains
    batch_size: int

    # list of strings with length BATCH_SIZE where each index matches
    # a unique identifier to the ground_truth or input tensor at the
    # particular batch dimension
    keys: List[str]

    # tensor of floats with shape [BATCH_SIZE, NUM_FRAMES, NUM_FEATURES]
    audio_input: t.Tensor

    # list of length of audio before padding,where each value contains the
    # audio sequence length (before padding was added) of the respective batch dimension.
    audio_input_lengths: List[int]

    # tensor of integers with shape [BATCH_SIZE]
    ground_truth: t.Tensor

    # the side information per sample based on a mapping
    # between a key at a particular index of `keys` and the corresponding
    # network_input at that index of the BATCH_SIZE dimension
    debug_info: Dict[str, Union[BatchDebugInfo, None]]

    def __len__(self):
        return self.batch_size

    def to(self, device: t.device) -> "SpeakerClassificationDataBatch":
        return SpeakerClassificationDataBatch(
            batch_size=self.batch_size,
            keys=self.keys,
            audio_input=self.audio_input.to(device),
            audio_input_lengths=self.audio_input_lengths,
            ground_truth=self.ground_truth.to(device),
            debug_info=self.debug_info,
        )

    @staticmethod
    def set_gt_container(sample: AudioDataSample, speaker_id_idx: t.Tensor):
        sample.ground_truth_container["speaker_id_idx"] = speaker_id_idx

    @staticmethod
    def get_gt_container(sample: AudioDataSample):
        if "speaker_id_idx" in sample.ground_truth_container:
            return sample.ground_truth_container["speaker_id_idx"]
        else:
            raise ValueError("expected key `speaker_id_idx` in data sample object")

    @classmethod
    def default_collate_fn(
        cls,
        lst: List[AudioDataSample],
    ) -> "SpeakerClassificationDataBatch":
        batch_size = len(lst)
        keys = torch_default_collate([sample.key for sample in lst])

        # assume all audio has equal number of frames
        audio_input = torch_default_collate([sample.audio for sample in lst])
        input_lengths = [sample.audio.shape[-1] for sample in lst]
        ground_truth = torch_default_collate(
            [cls.get_gt_container(sample) for sample in lst]
        )
        debug_info = {sample.key: sample.debug_info for sample in lst}

        return SpeakerClassificationDataBatch(
            batch_size=batch_size,
            keys=keys,
            audio_input=audio_input,
            audio_input_lengths=input_lengths,
            ground_truth=ground_truth,
            debug_info=debug_info,
        )

    @classmethod
    def pad_right_collate_fn(
        cls,
        lst: List[AudioDataSample],
    ) -> "SpeakerClassificationDataBatch":
        batch_size = len(lst)
        keys = torch_default_collate([sample.key for sample in lst])
        audio_input = collate_append_constant(
            [sample.audio.squeeze() for sample in lst]
        )
        input_lengths = [sample.audio.shape[-1] for sample in lst]
        ground_truth = torch_default_collate(
            [cls.get_gt_container(sample) for sample in lst]
        )

        debug_info = {sample.key: sample.debug_info for sample in lst}

        return SpeakerClassificationDataBatch(
            batch_size=batch_size,
            keys=keys,
            audio_input=audio_input,
            audio_input_lengths=input_lengths,
            ground_truth=ground_truth,
            debug_info=debug_info,
        )


########################################################################################
# implement a batch for speech recognition


@dataclass
class SpeechRecognitionDataBatch:
    # the number of samples this batch contains
    batch_size: int

    # list of strings with length BATCH_SIZE where each index matches
    # a unique identifier to the ground_truth or input tensor at the
    # particular batch dimension
    keys: List[str]

    # tensor of floats with shape [BATCH_SIZE, NUM_FRAMES, NUM_FEATURES]
    audio_input: t.Tensor

    # tensor of transcription strings with length [BATCH_SIZE, MAX_SEQUENCE_LENGTH]
    # each transcription is an inner dimension with integers representing characters
    # due to variable length padding ('0') is added which should be ignored
    # by the CTC loss implementation
    ground_truth: t.Tensor

    # list of length of audio before padding,where each value contains the
    # audio sequence length (before padding was added) of the respective batch dimension.
    audio_input_lengths: List[int]

    # list of length of ground truth before padding, of shape [BATCH_SIZE,] where each
    # value contains the sequence length (before padding was added) of the respective
    # batch dimension.
    ground_truth_sequence_length: List[int]

    # transcriptions in string format
    ground_truth_strings: List[str]

    # the debug information per sample based on a mapping
    # between a key at a particular index of `keys` and the corresponding
    # network_input at that index of the BATCH_SIZE dimension
    debug_info: Dict[str, Union[BatchDebugInfo, None]]

    def __len__(self):
        return self.batch_size

    def to(self, device: t.device) -> "SpeechRecognitionDataBatch":
        return SpeechRecognitionDataBatch(
            batch_size=self.batch_size,
            keys=self.keys,
            audio_input=self.audio_input.to(device),
            audio_input_lengths=self.audio_input_lengths,
            ground_truth=self.ground_truth.to(device),
            ground_truth_strings=self.ground_truth_strings,
            ground_truth_sequence_length=self.ground_truth_sequence_length,
            debug_info=self.debug_info,
        )

    @staticmethod
    def set_gt_container(
        sample: AudioDataSample,
        transcription: str,
        transcription_int_sequence: t.Tensor,
    ):
        assert transcription_int_sequence.shape == (len(transcription),)

        sample.ground_truth_container["transcription"] = transcription
        sample.ground_truth_container[
            "transcription_int_sequence"
        ] = transcription_int_sequence

    @staticmethod
    def get_gt_container(sample: AudioDataSample):
        if "transcription" in sample.ground_truth_container:
            transcription = sample.ground_truth_container["transcription"]
        else:
            raise ValueError("expected key `transcription` in data sample object")

        if "transcription_int_sequence" in sample.ground_truth_container:
            transcription_int_sequence = sample.ground_truth_container[
                "transcription_int_sequence"
            ]
        else:
            raise ValueError(
                "expected key `transcription_int_sequence` in data sample object"
            )

        return transcription, transcription_int_sequence

    @classmethod
    def default_collate_fn(
        cls,
        lst: List[AudioDataSample],
    ) -> "SpeechRecognitionDataBatch":
        # batch size is equal to the length of the list
        batch_size = len(lst)

        # simple lists which can be concatenated with list comprehension
        keys = [sample.key for sample in lst]
        debug_info = {sample.key: sample.debug_info for sample in lst}
        input_lengths = [sample.audio.shape[-1] for sample in lst]

        # ground truth which we extract from the dictionary
        ground_truth_strings = [cls.get_gt_container(sample)[0] for sample in lst]
        ground_truth_sequence_length = [
            cls.get_gt_container(sample)[1].shape[-1] for sample in lst
        ]

        # tensors which the collate with padding
        network_input = collate_append_constant(
            [sample.audio.squeeze() for sample in lst],
        )
        ground_truth = collate_append_constant(
            [cls.get_gt_container(sample)[1] for sample in lst]
        )

        return SpeechRecognitionDataBatch(
            batch_size=batch_size,
            keys=keys,
            audio_input=network_input,
            audio_input_lengths=input_lengths,
            ground_truth=ground_truth,
            ground_truth_strings=ground_truth_strings,
            ground_truth_sequence_length=ground_truth_sequence_length,
            debug_info=debug_info,
        )
