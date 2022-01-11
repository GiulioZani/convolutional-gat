import torch as t
from threading import Thread
import os
import numpy as np
import ipdb
from enum import Enum, unique
from tqdm import tqdm
import json

# todo: shuffling
# todo: fix the fist batch is empty


class DataLoader:
    def __init__(
        self,
        batch_size: int,
        folder: str,
        device,
        *,
        time_steps: int = 4,
        norm_max=None,
        norm_min=None,
        crop=None,
        shuffle: bool = True
    ):
        self.crop = crop
        self.device = device
        self.batch_size = batch_size
        self.file_index = 0
        self.folder = folder
        self.files = tuple(
            os.path.join(folder, fn) for fn in sorted(os.listdir(folder))
        )
        self.shuffle = shuffle
        if self.shuffle:
            rand_indices = t.randperm(len(self.files))
            tmp = tuple(self.files[i] for i in rand_indices)
            self.files = tmp
        self.remainder = self.__read_next_file()
        self.file_length = self.remainder.shape[0] * self.remainder.shape[1]
        self.normalizing_constant = 270

    """
    def __len__(self) -> int:
        return int(
            np.ceil(len(self.files) * self.file_length / self.batch_size)
        )
    """

    def __read_next_file(self) -> t.Tensor:
        if self.file_index == len(self.files):
            raise StopIteration
        data = t.load(self.files[self.file_index])
        self.file_index += 1
        result = self.__segmentify(data)
        return result

    def __segmentify(self, data: t.Tensor) -> t.Tensor:
        data = data[: (len(data) // 8) * 8]
        try:
            segments = t.stack(
                tuple(
                    el
                    for el in tuple(data[i : i + 8] for i in range(len(data)))
                    if len(el) == 8
                )
            )
        except Exception:
            ipdb.set_trace()
        """
        segments = data.view(
            -1, 8, data.shape[1], data.shape[2], data.shape[3]
        )
        """
        split_segments = t.stack(
            tuple(t.stack((s[:4], s[4:])) for s in segments)
        ).transpose(0, 1)
        return split_segments

    def __next__(self) -> tuple[t.Tensor, t.Tensor]:
        # ipdb.set_trace()
        if self.remainder.shape[1] == 0:
            data = self.__read_next_file()
            # data = t.cat((self.remainder, new_data), dim=1)
        else:
            data = self.remainder
        self.remainder = data[:, self.batch_size :]
        result = data[:, : self.batch_size].to(self.device)
        rand_indices = (
            t.randperm(result.shape[1])
            if self.shuffle
            else t.arange(result.shape[1])
        )
        results = (
            result[0][rand_indices].permute(0, 3, 4, 1, 2)
            / self.normalizing_constant,
            result[1][rand_indices].permute(0, 3, 4, 1, 2)
            / self.normalizing_constant,
        )
        if self.crop is not None:
            results = (
                results[0][:, : self.crop, : self.crop, :, :],
                results[1][:, : self.crop, : self.crop, :, :],
            )
        return results

    def __iter__(self):
        return self


def get_loaders(
    train_batch_size: int,
    test_batch_size: int,
    data_folder: str,
    device,
    crop: int = None,
    shuffle: bool = True,
):
    train_loader = DataLoader(
        train_batch_size,
        os.path.join(data_folder, "train"),
        device,
        crop=crop,
        shuffle=shuffle,
    )

    val_loader = DataLoader(
        test_batch_size,
        os.path.join(data_folder, "test"),
        device,
        crop=crop,
        shuffle=shuffle,
    )
    test_loader = DataLoader(
        test_batch_size,
        os.path.join(data_folder, "test"),
        device,
        crop=crop,
        shuffle=shuffle,
    )
    return train_loader, val_loader, test_loader


def test():
    data_loader = DataLoader(
        batch_size=32,
        folder="/mnt/kmni_dataset/preprocessed/",
        device=t.device("cuda" if t.cuda.is_available() else "cpu"),
    )
    # print(f"{len(data_loader)}")
    for x, y in tqdm(data_loader):
        pass


@unique
class Task(Enum):
    predict_next = "predict_next"


'''

class DataLoader:
    def __init__(
        self,
        batch_size: int,
        folder: str,
        device,
        *,
        total_length: int,
        n_regions: int = 5,
        task: Task = Task.predict_next,
        time_steps: int = 4,
        norm_max=None,
        norm_min=None,
        downsample_size: tuple[int, int] = (
            256,
            256,
        ),  # by default, don't downsample
    ):
        self.total_length = total_length
        self.n_regions = n_regions
        self.downsample_size = downsample_size
        self.folder = folder
        self.task = task
        self.device = device
        self.__is_first = True
        self.norm_max = norm_max
        self.norm_min = norm_min
        self.batch_size = batch_size
        self.time_steps = time_steps
        self.__batch_size = batch_size
        self.__next_batch = (t.tensor([]), t.tensor([]))
        self.__remainder = (t.tensor([]), t.tensor([]))
        self.file_index = 0
        self.should_stop_iteration = False
        self.files = sorted(
            [f for f in os.listdir(folder)], key=lambda x: int(x.split(".")[0])
        )
        max_file = max(int(f.split(".")[0]) for f in self.files)
        # print(f"{max_file=}")
        self.item_count = 86 * len(self.files)
        self.thread = Thread(target=self.__get_batch)
        # print(f"{self.files=}")
        # print(f"{self.item_count=}")

    def __len__(self):
        tot = self.total_length - (self.time_steps - 1) * (len(self.files) + 1)
        return tot // self.__batch_size

    def __batchify(self, data: t.Tensor) -> tuple[t.Tensor, t.Tensor]:
        result = (t.tensor([]), t.tensor([]))
        """
        shifted = t.stack(
            tuple(
                data[i : i + self.time_steps]
                for i in range(len(data) - (self.time_steps - 1))
            )
        )
        even_mask = t.arange(len(shifted)) % 2 == 0
        xs = shifted[even_mask]
        labels = shifted[t.logical_not(even_mask)]
        min_len = min(len(xs), len(labels))
        result = (xs[:min_len], labels[:min_len])
        """
        chunks = tuple(
            data[i : i + 2 * self.time_steps]
            for i in range(len(data) - (2 * self.time_steps - 1))
        )
        xs = []
        ys = []
        for chunk in chunks:
            xs.append(chunk[: self.time_steps])
            ys.append(chunk[self.time_steps :])
        tensor_xs = t.stack(xs)
        tensor_ys = t.stack(ys)

        return (tensor_xs, tensor_ys)

    def fix_sizes(self, tensor1: t.Tensor, tensor2: t.Tensor):
        tensor1 = tensor1.squeeze(3)  # same
        # print(current_time_step.shape)
        tensor1 = tensor1.permute(0, 3, 4, 1, 2)
        tensor2 = tensor2.squeeze(3)  # same
        # print(current_time_step.shape)
        tensor2 = tensor2.permute(0, 3, 4, 1, 2)
        return tensor1, tensor2

    def __iter__(self):
        return self

    def __next__(self) -> tuple[t.Tensor, t.Tensor]:
        if self.should_stop_iteration:
            # print(f"Number of files read: {self.file_index} out of {len(self.files)}")
            raise StopIteration

        if self.thread.is_alive():
            self.thread.join()
        if self.__is_first:
            self.__is_first = False
            self.__get_batch()
        current_batch = self.__next_batch
        self.__next_batch = None
        if not self.should_stop_iteration:
            try:
                self.thread.start()
            except:
                self.thread = Thread(target=self.__get_batch)
                self.thread.start()
        # print(f"{result[0].shape=}")
        return self.fix_sizes(
            current_batch[0].to(self.device), current_batch[1].to(self.device),
        )

    def __read_next_file(self) -> t.Tensor:
        if self.file_index == len(self.files):
            self.should_stop_iteration = True
        # tensor = t.tensor([[]])
        # while (
        #    tensor.shape[1] < 5
        # ):  # TODO: some files have apparently only 5 in the second dimension, could mean there is a bug in the preprocessing or the data is not perfect
        # while tensor.shape[1] < 5:
        tensor = t.load(
            os.path.join(self.folder, f"{self.files[self.file_index]}")
        )
        # assert (
        #    tensor.shape[1] == self.n_regions
        # ), f"Found a tensor that is not of the right shape {tensor.shape=}"
        # print(f"{tensor.shape=}")
        # if len(tensor.shape) > 5:
        #    ipdb.set_trace()
        tensor = tensor[
            :, :, :, : self.downsample_size[0], : self.downsample_size[1]
        ]
        # print(f"{tensor.shape=}")
        # if tensor.shape[1] < 5:
        # print("skipping")
        # ipdb.set_trace()
        #    pass

        # print(self.file_index)
        # print(self.files[self.file_index])
        self.file_index += 1
        if self.file_index == len(self.files):
            self.should_stop_iteration = True
        return tensor

    def __get_batch(self):
        # accumulator = self.__remainder
        if len(self.__remainder[0]) > 0:
            self.__next_batch = (
                self.__remainder[0][: self.__batch_size],
                self.__remainder[1][: self.__batch_size],
            )
            self.__remainder = (
                self.__remainder[0][self.__batch_size :],
                self.__remainder[1][self.__batch_size :],
            )
        else:
            data = self.__batchify(self.__read_next_file())
            self.__remainder = (
                data[0][self.__batch_size :],
                data[1][self.__batch_size :],
            )
            self.__next_batch = (
                data[0][: self.__batch_size],
                data[1][: self.__batch_size],
            )
        """ 
        while (
            len(accumulator) < self.__batch_size
            and not self.should_stop_iteration
        ):
            to_be_gained = self.__batch_size - len(accumulator)
            next_batch = self.__read_next_file()
            new_data = next_batch[:to_be_gained]
            # print(f"{new_data.shape=}")
            # print(f"{accumulator.shape=}")
            accumulator = (
                new_data
                if len(accumulator) == 0
                else t.cat((accumulator, new_data))
            )
            self.__remainder = next_batch[to_be_gained:]
        self.__next_batch = accumulator
        """


def get_loaders(
    train_batch_size: int,
    test_batch_size: int,
    preprocessed_folder: str,
    device,
    *,
    task: Task,
    downsample_size: tuple[int, int] = (256, 256),
):
    with open(os.path.join(preprocessed_folder, "metadata.json")) as f:
        metadata = json.load(f)
    return (
        DataLoader(
            train_batch_size,
            os.path.join(preprocessed_folder, "training"),
            device,
            total_length=metadata["training"]["length"],
            task=task,
            downsample_size=downsample_size,
            n_regions=metadata["n_regions"],
        ),
        DataLoader(
            test_batch_size,
            os.path.join(preprocessed_folder, "validation"),
            device,
            total_length=metadata["validation"]["length"],
            task=task,
            downsample_size=downsample_size,
            n_regions=metadata["n_regions"],
        ),
        DataLoader(
            test_batch_size,
            os.path.join(preprocessed_folder, "validation"),
            device,
            total_length=metadata["validation"]["length"],
            task=task,
            downsample_size=downsample_size,
            n_regions=metadata["n_regions"],
        ),
    )


def test():
    device = t.device("cuda" if t.cuda.is_available() else "cpu")
    train_loader, val_loader, test_loader = get_loaders(
        train_batch_size=32,
        test_batch_size=100,
        preprocessed_folder="/mnt/preprocessed2",
        device=device,
        task=Task.predict_next,
        downsample_size=(16, 16),
    )
    i = 0
    total_length = 0
    print(f"{len(train_loader)=}")
    for x, y in tqdm(train_loader):
        # print(f"{x.shape=}")
        # print(f"{y.shape=}")
        # assert (
        #    x.shape[1] == 4 and y.shape[1] == 4
        # ), f"error, {x.shape=} {y.shape=}"
        assert y.tolist() != x.tolist(), f"error, these are the same! {i}"
        total_length += len(x)
        i += 1
    for x, y in tqdm(train_loader):
        # print(f"{x.shape=}")
        # print(f"{y.shape=}")
        assert (
            x.shape[1] == 4 and y.shape[1] == 4
        ), f"error, {x.shape=} {y.shape=}"
        total_length += len(x)
        i += 1
    print(f"{total_length=}")
    print(f"Iterated {i} times")
'''

if __name__ == "__main__":
    test()
