import torch as t
import torch.nn as nn
from torchinfo import summary
import os
from tqdm import tqdm
import json
import ipdb
from argparse import ArgumentParser
from .data_loaders.get_loaders import get_loaders
from .model import SpatialModel, TemporalModel
import matplotlib.pyplot as plt
<<<<<<< HEAD
from .utils import thresholded_mask_metrics, MSE_denormalized
=======
from .unet_model import UnetModel
from .utils import thresholded_mask_metrics, update_history
>>>>>>> d6f12686d59b3b47b2389106576981d0f9e4a8e1

# todo: add that it saves the best performing model


def plot_history(
    history: dict[str, list[float]],
    title: str = "Training History",
    save=False,
    filename="history",
):
    plt.clf()
    plt.plot(
        history["train_loss"], label="Train loss",
    )
    plt.plot(
        history["val_loss"], label="Val loss",
    )
    plt.legend()
    plt.title(title)
    if save:
        plt.savefig(filename)
    else:
        plt.show()
    plt.close()


<<<<<<< HEAD
def test(model: nn.Module, device, val_test_loader, label="val", binarize_thresh=0):
    thresh_metrics = thresholded_mask_metrics(threshold=binarize_thresh, var=val_test_loader.normalizing_var, mean=val_test_loader.normalizing_mean)
    # denorm_mse = MSE_denormalized(val_test_loader)
=======
def accuracy(y, y_hat, mean):
    y = t.clone(y.cpu())
    y_hat = t.clone(y_hat.cpu())
    y[y < mean] = 0
    y[y >= mean] = 1
    y_hat[y_hat < mean] = 0
    y_hat[y_hat >= mean] = 1
    correct = y == y_hat
    result = t.sum(correct) / y[0].numel()
    return result


def test(model: nn.Module, device, val_test_loader, flag="val"):
    binarize_thresh = t.mean(val_test_loader.normalizing_mean)
    thresh_metrics = thresholded_mask_metrics(
        threshold=binarize_thresh,
        var=t.mean(val_test_loader.normalizing_var),
        mean=t.mean(val_test_loader.normalizing_mean),
    )
>>>>>>> d6f12686d59b3b47b2389106576981d0f9e4a8e1
    model.eval()  # We put the model in eval mode: this disables dropout for example (which we didn't use)
    with t.no_grad():  # Disables the autograd engine
        running_loss = t.tensor(0.0)
        running_acc = t.tensor(0.0)
        running_prec = t.tensor(0.0)
        running_recall = t.tensor(0.0)
        running_denorm_mse = t.tensor(0.0)
        total_length = 0
        for x, y in tqdm(val_test_loader):
            if len(x) > 1:
                y_hat = model(x)
                running_loss += (
                    t.sum((y - y_hat) ** 2)
                    / t.prod(t.tensor(y.shape[1:]).to(device))
                ).cpu()
                total_length += len(x)
<<<<<<< HEAD
                
                running_acc += thresh_metrics.acc(y, y_hat)
                running_prec += thresh_metrics.precision(y, y_hat)
                running_recall += thresh_metrics.recall(y, y_hat)
                # running_denorm_mse += denorm_mse.mse_denormalized_per_pixel(y, y_hat)

    model.train()
    return (running_loss / total_length).item(), \
            (running_acc.numpy() / total_length).item(), \
            (running_prec.numpy() / total_length).item(), \
            (running_recall.numpy() / total_length).item() \
            # (running_denorm_mse / total_length).item()
            
=======
                running_acc += accuracy(y, y_hat, 0.04011)
                # running_acc += thresh_metrics.acc(y, y_hat).numpy()
                running_prec += thresh_metrics.precision(
                    y, y_hat
                ).numpy() * len(x)
                running_recall += thresh_metrics.recall(
                    y, y_hat
                ).numpy() * len(x)

    model.train()
    return {
        "val_loss": (running_loss / total_length).item(),
        "val_acc": (running_acc / total_length).item(),
        "val_prec": (running_prec / total_length).item(),
        "val_rec": (running_recall / total_length).item(),
    }
>>>>>>> d6f12686d59b3b47b2389106576981d0f9e4a8e1


def visualize_predictions(
    model,
    epoch=1,
    path="",
    downsample_size=(256, 256),
    preprocessed_folder: str = "",
    dataset="kmni",
):
    plt.clf()
    with t.no_grad():
        device = t.device("cuda" if t.cuda.is_available() else "cpu")
        merge_nodes = issubclass(UnetModel, type(model))
        loader, _, _ = get_loaders(
            train_batch_size=2,
            test_batch_size=2,
            preprocessed_folder=preprocessed_folder,
            device=device,
            downsample_size=downsample_size,
            dataset=dataset,
            merge_nodes=merge_nodes,
        )
        model.eval()
        N_COLS = 4  # frames
        N_ROWS = 3  # x, y, preds
        plt.title(f"Epoch {epoch}")
        _fig, ax = plt.subplots(nrows=N_ROWS, ncols=N_COLS)
        for x, y in loader:
            for k in range(len(x)):
                raininess = t.sum(x[k] != 0) / t.prod(t.tensor(x[k].shape))
                if raininess >= 0.5:
                    preds = model(x)
                    to_plot = [x[k], y[k], preds[k]]
                    for i, row in enumerate(ax):
                        for j, col in enumerate(row):
                            # ipdb.set_trace()
                            col.imshow(
                                to_plot[i].cpu().detach().numpy()[:, :, j, 1]
                                if not merge_nodes
                                else to_plot[i]
                                .cpu()
                                .detach()
                                .numpy()[
                                    j,
                                    : downsample_size[0],
                                    : downsample_size[1],
                                ]
                            )

                    row_labels = ["x", "y", "preds"]
                    for ax_, row in zip(ax[:, 0], row_labels):
                        ax_.set_ylabel(row)

                    col_labels = ["frame1", "frame2", "frame3", "frame4"]
                    for ax_, col in zip(ax[0, :], col_labels):
                        ax_.set_title(col)

                    plt.savefig(os.path.join(path, f"pred_{epoch}.png"))
                    plt.close()
                    model.train()
                    return


def train_single_epoch(
    epoch: int,
    optimizer,
    criterion,
    scheduler,
    model,
    train_batch_size,
    test_batch_size,
    preprocessed_folder,
    device,
    dataset,
    downsample_size,
    history,
    output_path,
):
    merge_nodes = issubclass(UnetModel, type(model))
    train_loader, val_loader, test_loader = get_loaders(
        train_batch_size=train_batch_size,
        test_batch_size=test_batch_size,
        preprocessed_folder=preprocessed_folder,
        device=device,
        dataset=dataset,
        downsample_size=downsample_size,
        merge_nodes=merge_nodes,
    )

    model.train()
    print(f"\nEpoch: {epoch}")
    running_loss = t.tensor(0.0)
    total_length = 0
    __total_length = 0
    for param_group in optimizer.param_groups:  # Print the updated LR
        print(f"LR: {param_group['lr']}")
    for x, y in tqdm(train_loader):
        __total_length += len(x)
        if len(x) > 1:
            # N(batch size), H,W(feature number) = 256,256, T(time steps) = 4, V(vertices, # of cities) = 5
            optimizer.zero_grad()
            y_hat = model(x)  # Implicitly calls the model's forward function
            loss = criterion(y_hat, y)
            loss.backward()  # Update the gradients
            optimizer.step()  # Adjust model parameters
            total_length += len(x)
            running_loss += (
                (
                    t.sum((y_hat - y) ** 2)
                    / t.prod(t.tensor(y.shape[1:]).to(device))
                )
                .detach()
                .cpu()
            )
    # print(f"{__total_length=}")
    scheduler.step()
    train_loss = (running_loss / total_length).item()
    print(f"Train loss: {round(train_loss, 6)}")
<<<<<<< HEAD
    # val_loss, val_acc, val_prec, val_rec, val_denorm_mse = test(model, device, val_loader, binarize_thresh)
    val_loss, val_acc, val_prec, val_rec = test(model, device, val_loader, binarize_thresh)
    # ipdb.set_trace()
    print(f"Val loss: {round(val_loss, 6)}")
    history["train_loss"].append(train_loss)
    history["val_loss"].append(val_loss)

    # history["denorm_mse"].append(denorm_mse)
    history["val_acc"].append(val_acc)
    history["val_prec"].append(val_prec)
    history["val_rec"].append(val_rec)
    # history["val_denorm_mse"].append(val_denorm_mse)

=======
    history["train_loss"].append(train_loss)
    test_result = test(model, device, val_loader)
    # print(f"Val loss: {round(test_result['val_loss'], 6)}")
    print(json.dumps(test_result, indent=4))
    update_history(history, test_result)
>>>>>>> d6f12686d59b3b47b2389106576981d0f9e4a8e1
    with open(output_path + "/history.json", "w") as f:
        json.dump(history, f, indent=4)
    if len(history["val_loss"]) > 1 and test_result["val_loss"] < min(
        history["val_loss"][:-1]
    ):
        t.save(model.state_dict(), output_path + "/model.pt")


def get_number_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def train(
    *,
    model_class,
    optimizer_class,
    mapping_type,
    train_batch_size=1,
    test_batch_size=100,
    epochs=10,
    lr=0.001,
    lr_step=1,
    gamma=1.0,
    plot=True,
    criterion=nn.MSELoss(),
    downsample_size=(256, 256),
    output_path=".",
    preprocessed_folder="",
    dataset="kmni",
    test_first=True,
):
<<<<<<< HEAD
    device = t.device(
        "cuda" if t.cuda.is_available() else "cpu"
    )  # Select the GPU device, if there is one available.
    #
    # device = t.device('cpu')
    # optimizer = the procedure for updating the weights of our neural network
    # optimizer = t.optim.Adam(model.parameters(), lr=lr)
    # criterion = nn.MSELoss()
    # criterion = nn.BCELoss()  tested but didn't improve significantly
    history = {"train_loss": [], "val_loss": [], "val_acc": [], "val_prec": [], "val_rec": [], "val_denorm_mse": []}
=======
    device = t.device("cuda" if t.cuda.is_available() else "cpu")
    history = {"train_loss": []}
>>>>>>> d6f12686d59b3b47b2389106576981d0f9e4a8e1
    print(f"Using device: {device}")
    merge_nodes = model_class == UnetModel
    train_loader, val_loader, test_loader = get_loaders(
        train_batch_size=train_batch_size,
        test_batch_size=test_batch_size,
        preprocessed_folder=preprocessed_folder,
        device=device,
        dataset=dataset,
        downsample_size=downsample_size,
        merge_nodes=merge_nodes,
    )
    for x, y in val_loader:
        if not merge_nodes:
            _, image_width, image_height, steps, n_vertices = x.shape
        else:
            _, image_width, image_height, _ = x.shape
            n_vertices = 6  # unused in this case
        break
    model = model_class(
        image_width=image_width,
        image_height=image_height,
        n_vertices=n_vertices,
        mapping_type=mapping_type,
    ).to(device)
    print(f"Number of parameters: {get_number_parameters(model)}")
    print(f"Using mapping: {model.mapping_type}")

    # summary(model, input_size=x.shape)

    optimizer = optimizer_class(model.parameters(), lr=lr, weight_decay=0.01)
    scheduler = t.optim.lr_scheduler.StepLR(
        optimizer, step_size=lr_step, gamma=gamma
    )
    if test_first:
<<<<<<< HEAD
        # test_loss, test_acc, test_prec, test_rec, test_denorm_mse = test(model, device, test_loader, "test", binarize_thresh)
        test_loss, test_acc, test_prec, test_rec = test(model, device, test_loader, "test", binarize_thresh)
        print(f"Test loss (without any training): {test_loss}")
        history["val_loss"].append(test_loss)

        # train_loss, train_acc, train_prec, train_rec, train_denorm_mse = test(model, device, train_loader, "test", binarize_thresh)
        train_loss, train_acc, train_prec, train_rec = test(model, device, train_loader, "test", binarize_thresh)
        print(f"Train loss (without any training): {train_loss}")
        history["train_loss"].append(train_loss)
=======
        result = test(model, device, train_loader,)
        history["train_loss"].append(result["val_loss"])
        result = test(model, device, test_loader,)
        print(f"Test loss (without any training): {result['val_loss']:.6f}")
        update_history(history, result)
        print(json.dumps(result, indent=4))
>>>>>>> d6f12686d59b3b47b2389106576981d0f9e4a8e1

    for epoch in range(1, epochs + 1):
        train_single_epoch(
            epoch,
            optimizer,
            criterion,
            scheduler,
            model,
            train_batch_size,
            test_batch_size,
            preprocessed_folder,
            device,
            dataset,
            downsample_size,
            history,
            output_path,
        )
        visualize_predictions(
            model,
            epoch=epoch,
            path=output_path,
            downsample_size=downsample_size,
            preprocessed_folder=preprocessed_folder,
            dataset=dataset,
        )
        plot_history(
            history,
            title="Training History",
            save=True,
            filename=os.path.join(output_path, f"history_{epoch}.png"),
        )
<<<<<<< HEAD
    # test_loss, test_acc, test_prec, test_rec, test_denorm_mse = test(model, device, test_loader, "test", binarize_thresh)
    test_loss, test_acc, test_prec, test_rec = test(model, device, test_loader, "test", binarize_thresh)
    print(f"Test loss: {round(test_loss, 6)}")
=======
    # test_loss = test(model, device, test_loader, "test")
    # print(f"Test loss: {round(test_loss['val_loss'], 6)}")
>>>>>>> d6f12686d59b3b47b2389106576981d0f9e4a8e1

    # if plot:
    #   plot_history(history)
    return history  # , test_loss


if __name__ == "__main__":
    parser = ArgumentParser()
    train()
